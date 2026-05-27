"""
Integration test for Issue #13 — SubDataset array transfer to local Loupe.

Runs ffast-server locally (no SLURM/SSH), connects directly via WebSocket,
loads examples/data/dataset.xyz, then requests arrays and verifies the
round-trip.  No cluster required.

Usage:
    source ~/.venvs/ffast_env/bin/activate
    python test_array_transfer.py
"""
import asyncio
import os
import subprocess
import sys
import time

import numpy as np
import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(HERE, "examples", "data", "dataset.xyz")
SERVER_PORT = 18765   # unusual port so we don't clash with a real server


async def _wait_for_server(url: str, retries: int = 30, delay: float = 0.5):
    for _ in range(retries):
        try:
            ws = await websockets.connect(url)
            await ws.close()
            return
        except Exception:
            await asyncio.sleep(delay)
    raise RuntimeError(f"Server did not start at {url}")


async def run_test():
    from cluster.rpc import pack, unpack, unpack_arrays

    url = f"ws://localhost:{SERVER_PORT}"

    print(f"[test] Connecting to {url}")
    ws = await websockets.connect(url)

    # ── 1. ping/pong ────────────────────────────────────────────────────────
    await ws.send("ping")
    reply = await asyncio.wait_for(ws.recv(), timeout=5)
    assert reply == "pong", f"Expected pong, got {reply!r}"
    print("[test] ping/pong OK")

    # ── 2. LOAD_DATASET ──────────────────────────────────────────────────────
    print(f"[test] Loading dataset: {DATASET_PATH}")
    await ws.send(pack("LOAD_DATASET", (DATASET_PATH, "ase (auto)"), {}))

    # Collect events until REMOTE_DATASET_META arrives (or timeout)
    fingerprint = None
    n_remote = None
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=2)
        except asyncio.TimeoutError:
            continue
        if not isinstance(msg, bytes):
            continue
        event, args, kwargs = unpack(msg)
        print(f"[test]   ← {event} args={args!r} kwargs_keys={list(kwargs)}")
        if event == "REMOTE_DATASET_META":
            fingerprint = args[0]
            n_remote = kwargs["n"]
            print(f"[test] Got REMOTE_DATASET_META: fp={fingerprint!r} n={n_remote}")
            break
        if event in ("TASK_FAILED",):
            raise RuntimeError(f"Server task failed: {args}")

    assert fingerprint is not None, "Never received REMOTE_DATASET_META"

    # ── 3. REQUEST_SUBDATASET_ARRAYS ─────────────────────────────────────────
    print(f"[test] Requesting arrays for {fingerprint!r}")
    await ws.send(pack("REQUEST_SUBDATASET_ARRAYS", (fingerprint,), {}))

    arrays = None
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
        except asyncio.TimeoutError:
            continue
        if not isinstance(msg, bytes):
            continue
        event, args, kwargs = unpack(msg)
        if event == "SUBDATASET_ARRAYS":
            assert args[0] == fingerprint
            arrays = unpack_arrays(kwargs)
            break
        print(f"[test]   ← {event} (skipping)")

    assert arrays is not None, "Never received SUBDATASET_ARRAYS"

    is_variable = bool(arrays.get("variable") is not None and
                       int(np.asarray(arrays["variable"]).flat[0]))
    print(f"[test] Arrays received: variable={is_variable}")

    if is_variable:
        R_flat = arrays["R_flat"]
        offsets = arrays["offsets"]
        z_flat = arrays["z_flat"]
        print(f"[test]   R_flat.shape={R_flat.shape}  offsets.shape={offsets.shape}  z_flat.shape={z_flat.shape}")
        assert R_flat.ndim == 2 and R_flat.shape[1] == 3
        assert len(offsets) == n_remote + 1
        assert z_flat.ndim == 1
    else:
        R = arrays["R"]
        z = arrays["z"]
        print(f"[test]   R.shape={R.shape}  z.shape={z.shape}")
        assert R.ndim == 3
        assert R.shape[0] == n_remote
        assert R.shape[2] == 3
        assert z.ndim == 1

    # ── 4. CachedRemoteDataset round-trip ────────────────────────────────────
    from cluster.remote_dataset import CachedRemoteDataset

    proxy = CachedRemoteDataset(fingerprint, "test", n_remote)
    assert proxy.is_remote_proxy
    proxy.populate(arrays)
    assert not proxy.is_remote_proxy
    assert proxy.getN() == n_remote
    if is_variable:
        # getNAtoms() returns array for variable datasets
        counts = proxy.getNAtoms()
        assert hasattr(counts, "__len__") and len(counts) == n_remote
        print(f"[test] CachedRemoteDataset OK (variable): n={proxy.getN()} atom_counts={counts.min()}-{counts.max()}")
    else:
        assert proxy.getNAtoms() == arrays["R"].shape[1]
        assert np.allclose(proxy.getCoordinates(), arrays["R"])
        assert np.array_equal(proxy.getElements(), arrays["z"])
        print(f"[test] CachedRemoteDataset OK: n={proxy.getN()} natoms={proxy.getNAtoms()}")

    # ── 5. idempotency — second request hits cache on server (no second transfer needed)
    # Just verify the wire is still live
    await ws.send("ping")
    pong = await asyncio.wait_for(ws.recv(), timeout=5)
    assert pong == "pong"
    print("[test] Connection still live after transfer")

    await ws.close()
    print("[test] ✓ All assertions passed")


async def main():
    # Start a local server subprocess
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, "-m", "server", "--port", str(SERVER_PORT)]
        if False  # kept for reference
        else [sys.executable, "server.py", "--port", str(SERVER_PORT)],
        cwd=HERE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(f"[test] Server PID {proc.pid} starting…")

    try:
        await _wait_for_server(f"ws://localhost:{SERVER_PORT}")
        print("[test] Server ready")
        await run_test()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        out, _ = proc.communicate()
        if out:
            lines = out.decode(errors="replace").splitlines()[-30:]
            print("[server log]\n" + "\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
