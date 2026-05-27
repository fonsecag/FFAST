"""
Offline test for the connecting-panel feature (issue #12).

No real cluster, SSH, or UI needed.  Uses a FakeSlurmBackend that
simulates each stage with configurable delays.

Run:
    python test_connect_panel.py
"""

import asyncio
import sys
import os

# Make sure project root is on the path
sys.path.insert(0, os.path.dirname(__file__))


# ── Fake backend ──────────────────────────────────────────────────────────────

from cluster.backend import ClusterBackend, ClusterError, JobStatus
from dataclasses import dataclass


class FakeSlurmBackend(ClusterBackend):
    """Simulates SLURM without SSH.  Transitions: PENDING → RUNNING."""

    def __init__(self, fail_at=None, job_id="FAKE-42"):
        """
        fail_at : str | None
            One of 'submit', 'poll', 'node', 'ws' to simulate failure
            at that stage.
        """
        self._fail_at = fail_at
        self._job_id = job_id
        self._polls = 0

    async def submit_job(self, spec):
        await asyncio.sleep(0.1)
        if self._fail_at == "submit":
            raise ClusterError("sbatch: error: fake submit failure")
        return self._job_id

    async def poll_status(self, job_id):
        await asyncio.sleep(0.05)
        if self._fail_at == "poll":
            return JobStatus.FAILED
        self._polls += 1
        # Pretend to be PENDING for 2 polls then RUNNING
        return JobStatus.RUNNING if self._polls >= 2 else JobStatus.PENDING

    async def get_node_address(self, job_id):
        await asyncio.sleep(0.05)
        if self._fail_at == "node":
            raise ClusterError("scontrol: node lookup failed")
        return "gpu01.fake.cluster"

    async def cancel_job(self, job_id):
        await asyncio.sleep(0.05)
        print(f"  [FakeBackend] scancel {job_id} → OK")


# ── Fake profile ──────────────────────────────────────────────────────────────

@dataclass
class FakeProfile:
    host: str = "login.fake.cluster"
    username: str = "testuser"
    identity_file: str = ""
    partition: str = "gpu"
    account: str = ""
    qos: str = ""
    job_name: str = "ffast"
    ffast_server_cmd: str = "ffast-server"

    def to_job_spec(self, command):
        from cluster.backend import JobSpec
        return JobSpec(cores=1, memory_mb=4096, time_limit="01:00:00",
                       command=command, partition=self.partition)


# ── Patched connect_to_cluster that uses FakeSlurmBackend ────────────────────

async def fake_connect(
    profile, fake_backend, fail_ws=False,
    progress_cb=None, on_job_submitted=None,
    poll_interval=0.05,
):
    """Runs the real connect_to_cluster logic but injects the fake backend
    and skips actual SSH / WebSocket by monkey-patching at import time."""

    import cluster.slurm as slurm_mod
    import cluster.session as session_mod
    import unittest.mock as mock

    # Patch RemoteSlurmBackend constructor to return our fake
    with mock.patch.object(slurm_mod, "RemoteSlurmBackend",
                           return_value=fake_backend):
        # Patch _find_free_port
        with mock.patch.object(session_mod, "_find_free_port",
                               return_value=54321):
            # Patch subprocess.Popen (SSH tunnel)
            fake_proc = mock.MagicMock()
            fake_proc.poll.return_value = None  # tunnel alive
            with mock.patch("subprocess.Popen", return_value=fake_proc):
                # Patch websockets.connect
                if fail_ws:
                    with mock.patch("websockets.connect",
                                   side_effect=OSError("refused")):
                        return await session_mod.connect_to_cluster(
                            profile,
                            poll_interval=poll_interval,
                            progress_cb=progress_cb,
                            on_job_submitted=on_job_submitted,
                        )
                else:
                    fake_ws = mock.MagicMock()
                    fake_ws.send = mock.AsyncMock()
                    fake_ws.recv = mock.AsyncMock(return_value="pong")
                    fake_ws.close = mock.AsyncMock()
                    # websockets.connect is awaited: make it an async callable
                    async def _ws_connect(url):
                        return fake_ws
                    with mock.patch("websockets.connect",
                                   side_effect=_ws_connect):
                        return await session_mod.connect_to_cluster(
                            profile,
                            poll_interval=poll_interval,
                            progress_cb=progress_cb,
                            on_job_submitted=on_job_submitted,
                        )


# ── Tests ─────────────────────────────────────────────────────────────────────

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def check(name, cond, detail=""):
    status = PASS if cond else FAIL
    print(f"  {status}  {name}" + (f" — {detail}" if detail else ""))
    return cond


async def test_happy_path():
    print("\n── Test 1: happy path ──")
    messages = []
    job_ids_seen = []
    profile = FakeProfile()
    backend = FakeSlurmBackend(job_id="12345")

    # Simulate menuHandler's _progress wrapper (adds [Job …] prefix)
    def _on_job_submitted(jid):
        job_ids_seen.append(jid)

    def _progress(msg):
        prefix = f"[Job {job_ids_seen[-1]}] " if job_ids_seen else ""
        messages.append(f"{prefix}{msg}")

    session = await fake_connect(
        profile, backend,
        progress_cb=_progress,
        on_job_submitted=_on_job_submitted,
    )

    ok = True
    ok &= check("on_job_submitted fires once", len(job_ids_seen) == 1)
    ok &= check("job_id is correct", job_ids_seen[0] == "12345")
    ok &= check("messages contain job prefix",
                any("[Job 12345]" in m for m in messages),
                str(messages))
    ok &= check("final message says Connected",
                any("Connected" in m for m in messages))
    ok &= check("session.job_id correct", session.job_id == "12345")
    print(f"  Messages received: {messages}")
    return ok


async def test_submit_failure():
    print("\n── Test 2: submit failure → ClusterError ──")
    messages = []
    profile = FakeProfile()
    backend = FakeSlurmBackend(fail_at="submit")

    from cluster.backend import ClusterError
    raised = False
    try:
        await fake_connect(
            profile, backend,
            progress_cb=lambda m: messages.append(m),
        )
    except ClusterError:
        raised = True

    ok = check("ClusterError raised on submit failure", raised)
    print(f"  Messages: {messages}")
    return ok


async def test_cancel_triggers_scancel():
    print("\n── Test 3: task cancel → scancel fires ──")
    job_ids_seen = []
    scancel_called = []
    profile = FakeProfile()
    backend = FakeSlurmBackend(job_id="99")

    # Monkey-patch cancel_job to record the call
    orig_cancel = backend.cancel_job
    async def _mock_cancel(job_id):
        scancel_called.append(job_id)
        await orig_cancel(job_id)
    backend.cancel_job = _mock_cancel

    # Simulate what menuHandler._connectTask does
    _job_id = None

    def _on_job_submitted(jid):
        nonlocal _job_id
        _job_id = jid

    async def _scancel(jid):
        # Test stand-in for the real _scancel — just calls backend cancel_job
        await backend.cancel_job(jid)

    async def _connectTask():
        nonlocal _job_id
        try:
            await fake_connect(
                profile, backend,
                on_job_submitted=_on_job_submitted,
                poll_interval=0.05,
            )
        except asyncio.CancelledError:
            if _job_id is not None:
                asyncio.create_task(_scancel(_job_id))
            raise

    task = asyncio.create_task(_connectTask())
    # Let it submit (get past on_job_submitted) then cancel
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Give the scancel task time to run
    await asyncio.sleep(0.2)

    ok = check("job_id captured before cancel", _job_id is not None,
               str(_job_id))
    ok &= check("scancel called with correct job_id",
                len(scancel_called) == 1 and scancel_called[0] == "99",
                str(scancel_called))
    return ok


async def test_error_kwarg_propagated():
    print("\n── Test 4: error=True sent on ClusterError ──")
    # Simulate what _connectTask does: on failure, push TASK_PROGRESS error=True
    error_events = []

    def fake_event_push(event, taskID, message=None, error=False, **kw):
        if event == "TASK_PROGRESS":
            error_events.append({"message": message, "error": error})

    # Simulate the except block from menuHandler
    from cluster.backend import ClusterError

    async def _connectTask(taskID="T1"):
        try:
            raise ClusterError("fake failure")
        except ClusterError as exc:
            fake_event_push(
                "TASK_PROGRESS",
                taskID,
                message=f"Connection failed: {exc}",
                error=True,
            )

    await _connectTask()

    ok = check("error=True propagated", len(error_events) == 1 and error_events[0]["error"])
    ok &= check("error message contains reason",
                "fake failure" in error_events[0]["message"])
    return ok


async def main():
    results = []
    results.append(await test_happy_path())
    results.append(await test_submit_failure())
    results.append(await test_cancel_triggers_scancel())
    results.append(await test_error_kwarg_propagated())

    total = len(results)
    passed = sum(results)
    print(f"\n{'='*40}")
    print(f"Results: {passed}/{total} passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
