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
import json
import logging
import os
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger("FFAST")

# ── session record persistence ────────────────────────────────────────────────
# Saved under ~/.ffast/sessions.json so the reconnect UI can find running jobs.

_SESSIONS_FILE = os.path.expanduser(
    os.path.join("~", ".ffast", "sessions.json")
)


def _load_session_records() -> list:
    """Read session records from ~/.ffast/sessions.json (returns [] on error)."""
    if not os.path.exists(_SESSIONS_FILE):
        return []
    try:
        with open(_SESSIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _write_session_records(records: list) -> None:
    os.makedirs(os.path.dirname(_SESSIONS_FILE), exist_ok=True)
    try:
        with open(_SESSIONS_FILE, "w") as f:
            json.dump(records, f, indent=2)
    except Exception as exc:
        logger.warning("Failed to write sessions.json: %s", exc)


def save_session_record(
    job_id: str, profile_name: str, node: str, remote_port: int
) -> None:
    """Upsert a session record for the given job."""
    records = _load_session_records()
    records = [r for r in records if r.get("job_id") != job_id]
    records.append(
        {
            "job_id": job_id,
            "profile_name": profile_name,
            "node": node,
            "remote_port": remote_port,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    )
    _write_session_records(records)
    logger.info("Session record saved: job=%s node=%s", job_id, node)


def delete_session_record(job_id: str) -> None:
    """Remove the session record for a job (call on user-initiated disconnect)."""
    records = _load_session_records()
    records = [r for r in records if r.get("job_id") != job_id]
    _write_session_records(records)
    logger.info("Session record deleted: job=%s", job_id)


def load_session_records() -> list:
    """Return all saved session records.  Used by the reconnect UI."""
    return _load_session_records()

_DEFAULT_REMOTE_PORT = 8765
_POLL_INTERVAL = 5        # seconds between squeue polls
_POLL_TIMEOUT = 600       # seconds to wait for RUNNING state
_TUNNEL_RETRIES = 100      # WebSocket connect attempts after tunnel spawn
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

    # ── array transfer cache ─────────────────────────────────────────────────
    # fingerprint → {R, F, z, n} dicts of numpy arrays
    _array_cache: dict = None
    # fingerprint → asyncio.Future waiting for SUBDATASET_ARRAYS response
    _pending_array_requests: dict = None
    # path → asyncio.Future waiting for DATASET_KEYS_RESPONSE
    _pending_key_probes: dict = None
    # path → asyncio.Future waiting for DATASET_LENGTH_RESPONSE
    _pending_length_probes: dict = None
    # (dataset_fp, model_fp) → asyncio.Future waiting for PREDICTION_ARRAYS
    _pending_prediction_requests: dict = None

    def __post_init__(self):
        self._array_cache = {}
        self._pending_array_requests = {}
        self._pending_key_probes = {}
        self._pending_length_probes = {}
        self._pending_prediction_requests = {}

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
        from cluster.rpc import CLIENT_ENV_SAFE, unpack

        async def _listen():
            try:
                async for message in self.websocket:
                    if not isinstance(message, bytes):
                        continue  # skip text messages (pong etc.)
                    try:
                        event, args, kwargs = unpack(message)
                        logger.debug(
                            "Listener received: %s args=%r", event, args
                        )

                        # ── key probe response ────────────────────────────
                        if event == "DATASET_KEYS_RESPONSE" and args:
                            path = args[0]
                            fut = self._pending_key_probes.pop(path, None)
                            if fut is not None and not fut.done():
                                fut.set_result(kwargs)
                                logger.info(
                                    "Listener: resolved key probe for %r",
                                    path,
                                )
                            else:
                                logger.warning(
                                    "Listener: DATASET_KEYS_RESPONSE for"
                                    " unknown path %r", path
                                )
                            await asyncio.sleep(0)
                            continue  # do NOT forward to env

                        # ── dataset length response ───────────────────────
                        if event == "DATASET_LENGTH_RESPONSE" and args:
                            path = args[0]
                            fut = self._pending_length_probes.pop(path, None)
                            if fut is not None and not fut.done():
                                fut.set_result(kwargs)
                                logger.info(
                                    "Listener: resolved length probe for %r",
                                    path,
                                )
                            else:
                                logger.warning(
                                    "Listener: DATASET_LENGTH_RESPONSE for"
                                    " unknown path %r", path,
                                )
                            await asyncio.sleep(0)
                            continue  # do NOT forward to env

                        # ── prediction-only array response ───────────────
                        if event == "PREDICTION_ARRAYS" and len(args) >= 2:
                            dataset_fp, model_fp = args[0], args[1]
                            from cluster.rpc import unpack_arrays
                            arrays = unpack_arrays(kwargs)
                            key = (dataset_fp, model_fp)
                            fut = self._pending_prediction_requests.pop(
                                key, None
                            )
                            if fut is not None and not fut.done():
                                fut.set_result(arrays)
                                logger.info(
                                    "Listener: resolved prediction future"
                                    " dataset=%r model=%r",
                                    dataset_fp[:8], model_fp[:8],
                                )
                            else:
                                logger.warning(
                                    "Listener: PREDICTION_ARRAYS for unknown"
                                    " (dataset=%r, model=%r)",
                                    dataset_fp[:8], model_fp[:8],
                                )
                            await asyncio.sleep(0)
                            continue  # do NOT forward to env

                        # ── array transfer response ───────────────────────
                        if event == "SUBDATASET_ARRAYS" and args:
                            fingerprint = args[0]
                            from cluster.rpc import unpack_arrays
                            arrays = unpack_arrays(kwargs)
                            # model_names is a plain str→str dict packed
                            # alongside the arrays (not encoded as ndarrays)
                            model_names = kwargs.get("model_names") or {}
                            fut = self._pending_array_requests.pop(
                                fingerprint, None
                            )
                            if fut is not None and not fut.done():
                                fut.set_result(
                                    {
                                        "arrays": arrays,
                                        "model_names": model_names,
                                    }
                                )
                                logger.info(
                                    "Listener: resolved array future for %r"
                                    " (models: %s)",
                                    fingerprint,
                                    list(model_names.keys()),
                                )
                            else:
                                logger.warning(
                                    "Listener: SUBDATASET_ARRAYS for unknown"
                                    " fingerprint %r", fingerprint
                                )
                            await asyncio.sleep(0)
                            continue  # do NOT forward to env

                        if event not in CLIENT_ENV_SAFE:
                            logger.debug(
                                "Listener: skipping non-local-safe event %s",
                                event,
                            )
                            continue

                        if event == "REMOTE_DATASET_META" and args:
                            logger.info(
                                "Listener: forwarding REMOTE_DATASET_META"
                                " fp=%r kwargs=%r", args[0], kwargs
                            )

                        # ── remote task ID namespacing ────────────────────
                        # Both the server and the local env use incrementing
                        # integer task IDs starting from 1, so they collide:
                        # the local connect task is typically ID 1, and the
                        # first remote task (dataset load) is also ID 1.
                        # Without namespacing, _inject_phantom_task overwrites
                        # the connect task entry, and TASK_DONE [1] from the
                        # server removes the connect bar from the sidebar.
                        # Prefix remote IDs so they occupy a distinct namespace.
                        if (
                            event in (
                                "TASK_CREATED", "TASK_PROGRESS",
                                "TASK_DONE", "TASK_FAILED",
                            )
                            and args
                        ):
                            args = list(args)
                            args[0] = f"remote_{args[0]}"

                        # Phantom task: TASK_CREATED from server carries only
                        # taskID.  The local TaskManager has no record of it,
                        # so TasksList.onTaskCreated would silently skip it.
                        # Insert a minimal entry so progress bars appear.
                        if event == "TASK_CREATED" and args:
                            logger.info(
                                "Listener: registering phantom task %r",
                                args[0],
                            )
                            local_env.tm.registerPhantomTask(args[0])
                        if event == "TASK_DONE":
                            # Delay TASK_DONE so Qt can paint the progress
                            # bar before it disappears.  Without this, fast
                            # remote tasks (TASK_CREATED + TASK_DONE arrive
                            # buffered together) vanish before the first
                            # paint cycle.
                            await asyncio.sleep(2.0)
                        local_env.eventPush(event, *args, **kwargs)
                        # Yield to the Qt/asyncio event loop so that widget
                        # changes from this event are painted before the next
                        # event is processed.
                        await asyncio.sleep(0)
                    except Exception as exc:
                        logger.warning(
                            "Listener decode error: %s", exc
                        )
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.warning("Listener terminated: %s", exc)

        return asyncio.create_task(_listen())

    async def request_subdataset_arrays(
        self, fingerprint: str, timeout: float = 300.0
    ) -> dict:
        """Request numpy arrays for a dataset from the remote server.

        Sends REQUEST_SUBDATASET_ARRAYS and awaits the SUBDATASET_ARRAYS
        response.  Result is cached so repeated calls for the same fingerprint
        are instant.

        Parameters
        ----------
        fingerprint : str
            Server-side dataset fingerprint.
        timeout : float
            Maximum seconds to wait for the server response (default 300 s —
            large SubDatasets can take a while to serialise).

        Returns
        -------
        dict with two top-level keys:

        ``arrays`` : dict
            Coordinate/element arrays (keys R/F/z for uniform or
            R_flat/F_flat/z_flat/offsets for variable datasets) plus any
            cached prediction arrays prefixed ``pred__<dtype>__<model_fp>``.
        ``model_names`` : dict[str, str]
            Server-side model fingerprint → human-readable name for each
            model whose prediction data was included in ``arrays``.
        """
        # Return cached result immediately
        if fingerprint in self._array_cache:
            logger.info("Array cache hit for %r", fingerprint)
            return self._array_cache[fingerprint]

        # Create a Future that the listener will resolve
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._pending_array_requests[fingerprint] = fut

        logger.info("Requesting arrays for %r from server…", fingerprint)
        await self.push_event("REQUEST_SUBDATASET_ARRAYS", fingerprint)

        arrays = await asyncio.wait_for(fut, timeout=timeout)
        self._array_cache[fingerprint] = arrays
        logger.info(
            "Arrays cached for %r (R shape %s)",
            fingerprint,
            arrays.get("R", None) and arrays["R"].shape,
        )
        return arrays

    async def request_prediction_arrays(
        self, dataset_fp: str, model_fp: str, timeout: float = 60.0
    ) -> dict:
        """Request prediction arrays (energy/forces) for a (dataset, model) pair.

        Uses the dedicated Prediction-Only Array Channel — geometry arrays are
        not re-transferred.  Sends ``REQUEST_PREDICTION_ARRAYS`` and awaits
        the ``PREDICTION_ARRAYS`` response.

        Parameters
        ----------
        dataset_fp : str
            Server-side dataset fingerprint.
        model_fp : str
            Ghost model fingerprint.
        timeout : float
            Maximum seconds to wait for the server response (default 60 s).

        Returns
        -------
        dict
            Arrays keyed as ``pred__energy__<model_fp>`` and/or
            ``pred__forces__<model_fp>``.
        """
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        key = (dataset_fp, model_fp)
        self._pending_prediction_requests[key] = fut

        logger.info(
            "Requesting prediction arrays: dataset=%r model=%r",
            dataset_fp[:8], model_fp[:8],
        )
        await self.push_event(
            "REQUEST_PREDICTION_ARRAYS", dataset_fp, model_fp
        )
        return await asyncio.wait_for(fut, timeout=timeout)

    async def probe_dataset_length(
        self, path: str, timeout: float = 60.0
    ) -> dict:
        """Ask server to count frames in a dataset file.

        Sends PROBE_DATASET_LENGTH and awaits DATASET_LENGTH_RESPONSE.

        Returns
        -------
        dict with keys:
            n     : int | None  — total frame count, or None on error
            error : str | None  — set if server-side probe failed
        """
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._pending_length_probes[path] = fut

        logger.info("Probing dataset length for %r", path)
        await self.push_event("PROBE_DATASET_LENGTH", path)

        return await asyncio.wait_for(fut, timeout=timeout)

    async def probe_dataset_keys(
        self, path: str, typ: str, timeout: float = 30.0
    ) -> dict:
        """Ask server to probe available energy/force key names for a file.

        Sends PROBE_DATASET_KEYS and awaits DATASET_KEYS_RESPONSE.  The server
        reads only the first frame so the round-trip is fast (<1 s normally).

        Parameters
        ----------
        path : str
            Cluster-side path to the dataset file.
        typ : str
            Dataset type string (e.g. ``"ase (auto)"``).
        timeout : float
            Maximum seconds to wait for the server response (default 30 s).

        Returns
        -------
        dict with keys:
            energy_keys : list[str]
            force_keys  : list[str]
            has_calculator_energy : bool
            has_calculator_forces : bool
            error : str | None  — set if server-side probe failed
        """
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._pending_key_probes[path] = fut

        logger.info("Probing dataset keys for %r (type=%s)", path, typ)
        await self.push_event("PROBE_DATASET_KEYS", path, typ)

        return await asyncio.wait_for(fut, timeout=timeout)

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


async def connect_direct(host: str = "localhost", port: int = 8765) -> "RemoteSession":
    """Connect directly to a running ffast-server without SLURM or SSH.

    Use this for local testing:
    1. ``python server.py --port 8765`` in one terminal.
    2. In the app: File → Connect to Local Server…

    Returns a RemoteSession with job_id="local" and ssh_proc=None.
    """
    import websockets

    url = f"ws://{host}:{port}"
    logger.info("connect_direct: connecting to %s", url)

    websocket = await websockets.connect(url, max_size=None)

    # verify with ping/pong
    await websocket.send("ping")
    reply = await asyncio.wait_for(websocket.recv(), timeout=10)
    if reply != "pong":
        await websocket.close()
        raise OSError(f"Unexpected ping reply: {reply!r}")

    logger.info("connect_direct: connected to %s", url)
    return RemoteSession(
        job_id="local",
        ssh_proc=None,
        websocket=websocket,
        profile=None,
        local_port=port,
        remote_port=port,
    )


def _build_backend(profile):
    """Return RemoteSlurmBackend or SlurmBackend depending on profile.host."""
    from cluster.slurm import RemoteSlurmBackend, SlurmBackend

    if profile.host:
        return RemoteSlurmBackend(
            host=profile.host,
            username=profile.username,
            identity_file=profile.identity_file,
        )
    return SlurmBackend()


async def _establish_connection(
    profile,
    job_id: str,
    node: str,
    remote_port: int,
    progress_cb: Optional[Callable[[str], None]],
) -> RemoteSession:
    """Spawn SSH tunnel, connect WebSocket, verify with ping/pong.

    Shared implementation used by both connect_to_cluster and
    reconnect_to_cluster.  Both call this after resolving the node address
    by their own means (submit+poll vs. verify existing job).

    Parameters
    ----------
    profile : ClusterProfile
        Used for SSH credentials (host, username, identity_file).
    job_id : str
        SLURM job ID — used for logging and session record persistence.
    node : str
        Compute node hostname resolved by the caller (e.g. ``"gpu001"``).
    remote_port : int
        Port ffast-server is listening on inside the job.
    progress_cb : callable(str) | None
        Optional progress callback forwarded to the UI task progress system.

    Returns
    -------
    RemoteSession

    Raises
    ------
    OSError
        SSH tunnel died or WebSocket could not connect within the retry budget.
    """
    import websockets

    def _progress(msg: str) -> None:
        logger.info(msg)
        if progress_cb is not None:
            progress_cb(msg)

    # ── SSH port-forward ──────────────────────────────────────────────────
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

    # ── WebSocket connect (retry until tunnel ready) ──────────────────────
    ws_url = f"ws://localhost:{local_port}"
    _progress(f"Connecting to {ws_url}…")

    websocket = None
    last_exc: Optional[Exception] = None
    for attempt in range(1, _TUNNEL_RETRIES + 1):
        if ssh_proc.poll() is not None:
            stderr = ssh_proc.stderr.read().decode(errors="replace").strip()
            raise OSError(
                f"SSH tunnel exited unexpectedly "
                f"(exit {ssh_proc.returncode}).\n{stderr}"
            )
        try:
            websocket = await websockets.connect(ws_url, max_size=None)
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

    # ── ping/pong verification ────────────────────────────────────────────
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
        "RemoteSession established: job=%s node=%s local_port=%d",
        job_id, node, local_port,
    )

    save_session_record(job_id, profile.name, node, remote_port)

    return RemoteSession(
        job_id=job_id,
        ssh_proc=ssh_proc,
        websocket=websocket,
        profile=profile,
        local_port=local_port,
        remote_port=remote_port,
    )


async def connect_to_cluster(
    profile,
    remote_port: int = _DEFAULT_REMOTE_PORT,
    poll_interval: float = _POLL_INTERVAL,
    poll_timeout: float = _POLL_TIMEOUT,
    progress_cb: Optional[Callable[[str], None]] = None,
    on_job_submitted: Optional[Callable[[str], None]] = None,
) -> RemoteSession:
    """Full connect flow: SLURM submit → poll → SSH tunnel → WebSocket.

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
    on_job_submitted : callable(str) | None
        Called once with the SLURM job ID immediately after submission.
        Use this to capture the job ID for cancellation purposes.

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

    def _progress(msg: str) -> None:
        logger.info(msg)
        if progress_cb is not None:
            progress_cb(msg)

    backend = _build_backend(profile)

    server_cmd = (
        getattr(profile, "ffast_server_cmd", "ffast-server") or "ffast-server"
    )
    snap_interval = getattr(profile, "snapshot_interval_minutes", 5)
    command = (
        f"{server_cmd} --port {remote_port} --snapshot-interval {snap_interval}"
    )

    # ── 1. submit SLURM job ───────────────────────────────────────────────
    _progress("Submitting SLURM job…")
    spec = profile.to_job_spec(command)
    job_id = await backend.submit_job(spec)
    if on_job_submitted is not None:
        on_job_submitted(job_id)
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

    # ── 4–6. SSH tunnel → WebSocket → ping/pong → RemoteSession ──────────
    return await _establish_connection(
        profile, job_id, node, remote_port, progress_cb
    )


async def reconnect_to_cluster(
    profile,
    job_id: str,
    remote_port: int = _DEFAULT_REMOTE_PORT,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> RemoteSession:
    """Reconnect to a RUNNING cluster job without submitting a new SLURM job.

    Use when the client disconnected (network blip, laptop sleep, etc.) but
    the server is still running.  Skips job submission and polling; goes
    directly to node resolution → SSH tunnel → WebSocket.

    Parameters
    ----------
    profile : ClusterProfile
        Connection profile (used for SSH credentials).
    job_id : str
        SLURM job ID of the already-running server.
    remote_port : int
        Port ffast-server is listening on inside the job (default 8765).
    progress_cb : callable(str) | None
        Optional progress callback for UI integration.

    Returns
    -------
    RemoteSession

    Raises
    ------
    ClusterError
        Job is no longer running.
    OSError
        SSH tunnel died or WebSocket could not connect.
    """
    from cluster.backend import ClusterError, JobStatus

    def _progress(msg: str) -> None:
        logger.info(msg)
        if progress_cb is not None:
            progress_cb(msg)

    backend = _build_backend(profile)

    # ── 1. verify job still RUNNING ───────────────────────────────────────
    _progress(f"Verifying job {job_id} is still running…")
    status = await backend.poll_status(job_id)
    if status != JobStatus.RUNNING:
        raise ClusterError(
            f"Job {job_id} is no longer running (status: {status.name})"
        )

    # ── 2. resolve node address ───────────────────────────────────────────
    node = await backend.get_node_address(job_id)
    _progress(f"Job {job_id} running on node: {node}")

    # ── 3–5. SSH tunnel → WebSocket → ping/pong → RemoteSession ──────────
    return await _establish_connection(
        profile, job_id, node, remote_port, progress_cb
    )
