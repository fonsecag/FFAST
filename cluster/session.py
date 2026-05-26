"""
RemoteSession and connect_to_cluster() — end-to-end remote connection flow.

Flow
----
1. Build JobSpec with command = "ffast-server --port <remote_port>"
2. SlurmBackend.submit_job() → job_id
3. Poll poll_status() until RUNNING (timeout → cancel + raise)
4. get_node_address() → node hostname
5. Spawn ssh -N -L local_port:node:remote_port user@host  (key auth only)
6. Retry websockets.connect() until tunnel is ready
7. Verify with ping/pong
8. Return RemoteSession

Cleanup
-------
RemoteSession.disconnect() closes the WebSocket and kills the SSH process.
The SLURM job keeps running until its time limit (server lifetime policy).
"""

import asyncio
import logging
import os
import socket
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger("FFAST")

_DEFAULT_REMOTE_PORT = 8765
_POLL_INTERVAL = 5        # seconds between squeue polls
_POLL_TIMEOUT = 300       # seconds to wait for RUNNING state
_TUNNEL_RETRIES = 12      # WebSocket connect attempts after tunnel spawn
_TUNNEL_RETRY_DELAY = 3   # seconds between WebSocket connect retries


def _find_free_port() -> int:
    """Return an available local TCP port."""
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@dataclass
class RemoteSession:
    """Holds all resources for one live remote connection."""

    job_id: str
    ssh_proc: subprocess.Popen
    websocket: object          # websockets.ClientConnection
    profile: object            # cluster.config.ClusterProfile
    local_port: int
    remote_port: int

    async def ping(self) -> bool:
        """Send ping, return True if pong received within 5 s."""
        try:
            await asyncio.wait_for(self.websocket.send("ping"), timeout=5)
            reply = await asyncio.wait_for(self.websocket.recv(), timeout=5)
            return reply == "pong"
        except Exception as exc:
            logger.warning("Ping failed: %s", exc)
            return False

    async def push_event(
        self, event: str, *args, **kwargs
    ) -> None:
        """Serialize and send an event to the remote ffast-server.

        Args must be msgpack-serializable primitives (str, int, float,
        list, dict, None).  Qt objects and numpy arrays must not be passed.

        Example::

            await session.push_event(
                "LOAD_DATASET",
                "/cluster/data/mol.xyz",
                "ase (auto)",
                slice_num=0,
            )
        """
        from cluster.rpc import pack

        data = pack(event, args, kwargs)
        await self.websocket.send(data)

    async def start_listener(self, local_env) -> asyncio.Task:
        """Start a background task that forwards server events to local_env.

        Receives msgpack messages from the server and re-injects them into
        *local_env*'s event system via ``eventPush``.  This drives the local
        UI (progress bars, plot refreshes) from remote task activity.

        Returns the ``asyncio.Task`` — cancel it to stop listening.

        Note: do not call ``ping()`` while the listener is running; both
        compete for the same websocket receive stream.
        """
        from cluster.rpc import unpack

        async def _listen():
            try:
                async for message in self.websocket:
                    if not isinstance(message, bytes):
                        continue  # skip text messages (pong etc.)
                    try:
                        event, args, kwargs = unpack(message)
                        local_env.eventPush(event, *args, **kwargs)
                    except Exception as exc:
                        logger.warning(
                            "Listener decode error: %s", exc
                        )
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.warning("Listener terminated: %s", exc)

        return asyncio.create_task(_listen())

    async def disconnect(self) -> None:
        """
        Close WebSocket and kill SSH tunnel.
        SLURM job continues running until its time limit.
        """
        try:
            await self.websocket.close()
        except Exception:
            pass
        try:
            self.ssh_proc.terminate()
            self.ssh_proc.wait(timeout=5)
        except Exception:
            pass
        logger.info(
            "Disconnected from job %s "
            "(SSH tunnel closed; job still running on cluster)",
            self.job_id,
        )


async def connect_to_cluster(
    profile,
    remote_port: int = _DEFAULT_REMOTE_PORT,
    poll_interval: float = _POLL_INTERVAL,
    poll_timeout: float = _POLL_TIMEOUT,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> RemoteSession:
    """
    Full connect flow: SLURM submit → poll → SSH tunnel → WebSocket.

    Parameters
    ----------
    profile : ClusterProfile
        Connection + resource profile.
    remote_port : int
        Port ffast-server listens on inside the job (default 8765).
    poll_interval : float
        Seconds between squeue status checks.
    poll_timeout : float
        Maximum seconds to wait for the job to reach RUNNING state.
    progress_cb : callable(str) | None
        Optional callback invoked with a human-readable progress message at
        each stage — useful for forwarding to the UI task progress system.

    Returns
    -------
    RemoteSession

    Raises
    ------
    ClusterError
        SLURM submit failed, job failed/timed-out before RUNNING.
    OSError
        SSH tunnel died or WebSocket could not connect.
    """
    from cluster.backend import ClusterError, JobStatus
    from cluster.slurm import RemoteSlurmBackend, SlurmBackend

    def _progress(msg: str) -> None:
        logger.info(msg)
        if progress_cb is not None:
            progress_cb(msg)

    # Use remote backend when a host is configured (the normal case).
    # Fall back to local SlurmBackend for local/test setups.
    if profile.host:
        backend = RemoteSlurmBackend(
            host=profile.host,
            username=profile.username,
            identity_file=profile.identity_file,
        )
    else:
        backend = SlurmBackend()

    server_cmd = getattr(profile, "ffast_server_cmd", "ffast-server") or "ffast-server"
    command = f"{server_cmd} --port {remote_port}"

    # ── 1. submit SLURM job ───────────────────────────────────────────────
    _progress("Submitting SLURM job…")
    spec = profile.to_job_spec(command)
    job_id = await backend.submit_job(spec)
    _progress(f"Job submitted: {job_id}")

    # ── 2. poll until RUNNING ─────────────────────────────────────────────
    _progress("Waiting for job to reach RUNNING state…")
    loop = asyncio.get_event_loop()
    deadline = loop.time() + poll_timeout

    while True:
        status = await backend.poll_status(job_id)

        if status == JobStatus.RUNNING:
            break

        if status == JobStatus.FAILED:
            raise ClusterError(
                f"Job {job_id} failed before reaching RUNNING state"
            )
        if status == JobStatus.COMPLETED:
            raise ClusterError(
                f"Job {job_id} completed immediately — ffast-server exited early"
            )
        if loop.time() > deadline:
            await backend.cancel_job(job_id)
            raise ClusterError(
                f"Timed out waiting {poll_timeout}s for job {job_id}"
            )

        await asyncio.sleep(poll_interval)

    # ── 3. resolve node address ───────────────────────────────────────────
    node = await backend.get_node_address(job_id)
    _progress(f"Job running on node: {node}")

    # ── 4. SSH port-forward ───────────────────────────────────────────────
    local_port = _find_free_port()
    login_target = (
        f"{profile.username}@{profile.host}"
        if profile.username
        else profile.host
    )
    identity_file = os.path.expanduser(
        getattr(profile, "identity_file", "") or ""
    )
    # Forward local_port → compute_node:remote_port through the login node.
    # The login node TCP-connects to the compute node (no SSH auth to compute
    # node required; only the login node needs key auth).
    ssh_cmd = [
        "ssh",
        "-N",                             # no remote command
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",            # key-auth only, no password prompts
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=30",
    ]
    if identity_file:
        ssh_cmd += ["-i", identity_file]
    ssh_cmd += [
        "-L", f"{local_port}:{node}:{remote_port}",
        login_target,
    ]
    _progress(
        f"Opening SSH tunnel: localhost:{local_port}"
        f" → {node}:{remote_port} via {profile.host}"
    )
    ssh_proc = subprocess.Popen(
        ssh_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    # ── 5. connect WebSocket (retry until tunnel ready) ───────────────────
    import websockets

    ws_url = f"ws://localhost:{local_port}"
    _progress(f"Connecting to {ws_url}…")

    websocket = None
    last_exc: Optional[Exception] = None

    for attempt in range(1, _TUNNEL_RETRIES + 1):
        # Abort early if SSH died before we connected
        if ssh_proc.poll() is not None:
            stderr = ssh_proc.stderr.read().decode(errors="replace").strip()
            raise OSError(
                f"SSH tunnel exited unexpectedly "
                f"(exit {ssh_proc.returncode}).\n{stderr}"
            )
        try:
            websocket = await websockets.connect(ws_url)
            break
        except Exception as exc:
            last_exc = exc
            logger.debug(
                "WebSocket connect attempt %d/%d failed: %s",
                attempt, _TUNNEL_RETRIES, exc,
            )
            await asyncio.sleep(_TUNNEL_RETRY_DELAY)

    if websocket is None:
        ssh_proc.terminate()
        raise OSError(
            f"Could not connect to {ws_url} after "
            f"{_TUNNEL_RETRIES} attempts: {last_exc}"
        )

    # ── 6. verify with ping/pong ──────────────────────────────────────────
    _progress("Verifying connection…")
    try:
        await websocket.send("ping")
        reply = await asyncio.wait_for(websocket.recv(), timeout=10)
    except Exception as exc:
        ssh_proc.terminate()
        await websocket.close()
        raise OSError(f"Ping/pong handshake failed: {exc}") from exc

    if reply != "pong":
        ssh_proc.terminate()
        await websocket.close()
        raise OSError(f"Unexpected ping reply: {reply!r}")

    _progress("Connected!")
    logger.info(
        "RemoteSession ready: job=%s node=%s local_port=%d",
        job_id, node, local_port,
    )

    return RemoteSession(
        job_id=job_id,
        ssh_proc=ssh_proc,
        websocket=websocket,
        profile=profile,
        local_port=local_port,
        remote_port=remote_port,
    )
