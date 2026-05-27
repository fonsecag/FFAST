"""
ffast-server — headless FFAST environment wrapped in a WebSocket RPC server.

Start with: ffast-server --port <port>

Control messages are msgpack-encoded dicts:
    {"event": str, "args": list, "kwargs": dict}

Client → server events:
    LOAD_DATASET  args=[path, datasetType]
                  kwargs={selected_energy_key, selected_force_key,
                          prediction_keys, slice_num}
    LOAD_MODEL    args=[path, modelType]

Server → client events (auto-forwarded):
    TASK_CREATED, TASK_PROGRESS, TASK_DONE, TASK_FAILED,
    DATA_UPDATED, DATASET_LOADED, MODEL_LOADED,
    DATASET_DELETED, MODEL_DELETED

Text "ping" → text "pong" still supported for liveness checks.

Log file: server.log (same directory as this file).
"""
import argparse
import asyncio
import logging
import os

import numpy as np

logger = logging.getLogger("FFAST")

_SERVER_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "server.log"
)


def _setupServerLogger():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(_SERVER_LOG),
            logging.StreamHandler(),
        ],
    )


async def _dispatch_client_event(env, event, args, kwargs, outbound):
    """Route an incoming client event to the appropriate env method."""
    if event == "LOAD_DATASET":
        if len(args) < 2:
            logger.warning("LOAD_DATASET: missing args %r", args)
            return
        path, datasetType = args[0], args[1]
        # msgpack deserializes tuples as lists; restore for prediction_keys
        if kwargs.get("prediction_keys"):
            kwargs["prediction_keys"] = [
                tuple(k) for k in kwargs["prediction_keys"]
            ]
        env.taskLoadDataset(path, datasetType, **kwargs)

    elif event == "LOAD_MODEL":
        if len(args) < 2:
            logger.warning("LOAD_MODEL: missing args %r", args)
            return
        env.taskLoadModel(args[0], args[1])

    elif event == "REQUEST_SUBDATASET_ARRAYS":
        if not args:
            logger.warning("REQUEST_SUBDATASET_ARRAYS: missing fingerprint")
            return
        fingerprint = args[0]
        await _send_subdataset_arrays(env, fingerprint, outbound)

    elif event == "PROBE_DATASET_KEYS":
        if len(args) < 2:
            logger.warning("PROBE_DATASET_KEYS: missing args %r", args)
            return
        path, typ = args[0], args[1]
        await _send_dataset_keys(path, typ, outbound)

    else:
        logger.warning("Unknown client event: %s", event)


async def _send_dataset_keys(path: str, typ: str, outbound) -> None:
    """Probe first frame of an ASE file and push DATASET_KEYS_RESPONSE.

    Uses the same key-detection logic as the local _showASEKeySelectionDialog
    so the client can display an identical KeySelectionDialog.
    """
    from cluster.rpc import pack

    energy_keys: list = []
    force_keys: list = []
    has_calculator_energy = False
    has_calculator_forces = False
    error: str | None = None

    try:
        import ase.io
        from modules.aseDataset import aseDatasetLoader

        first_atoms = ase.io.read(path, index=0)
        temp_loader = aseDatasetLoader(path, atomsList=[first_atoms])
        energy_keys = list(temp_loader.EneregyKeys())
        force_keys = list(temp_loader.ForceKeys())

        try:
            first_atoms.get_potential_energy()
            has_calculator_energy = True
        except Exception:
            pass
        try:
            first_atoms.get_forces()
            has_calculator_forces = True
        except Exception:
            pass

        logger.info(
            "PROBE_DATASET_KEYS %r: energy_keys=%r force_keys=%r",
            path, energy_keys, force_keys,
        )
    except Exception as exc:
        logger.warning("PROBE_DATASET_KEYS error for %r: %s", path, exc)
        error = str(exc)

    data = pack(
        "DATASET_KEYS_RESPONSE",
        (path,),
        {
            "energy_keys": energy_keys,
            "force_keys": force_keys,
            "has_calculator_energy": has_calculator_energy,
            "has_calculator_forces": has_calculator_forces,
            "error": error,
        },
    )
    try:
        outbound.put_nowait(data)
    except asyncio.QueueFull:
        await outbound.put(data)
    logger.debug("DATASET_KEYS_RESPONSE queued for %r", path)


async def _send_subdataset_arrays(env, fingerprint, outbound):
    """Serialize SubDataset arrays and push them onto the outbound queue.

    Supports both uniform datasets (R shape: N×natoms×3) and variable datasets
    (molecules of different sizes, stored as flat arrays + offsets).
    """
    from cluster.rpc import pack_arrays

    dataset = env.getDataset(fingerprint)
    if dataset is None:
        logger.warning(
            "REQUEST_SUBDATASET_ARRAYS: fingerprint %r not found", fingerprint
        )
        return

    n = dataset.getN()
    is_variable = bool(getattr(dataset, "isVariable", False))
    logger.info(
        "Sending arrays for dataset %r (n=%d, variable=%s) to client",
        fingerprint, n, is_variable,
    )

    arrays = {"n": np.array([n]), "variable": np.array([int(is_variable)])}

    if is_variable:
        # Flat format: R_flat (total_atoms, 3), molecule_offsets (N+1,)
        arrays["R_flat"] = dataset.R_flat
        arrays["offsets"] = dataset.molecule_offsets
        try:
            arrays["F_flat"] = dataset.F_flat
        except Exception:
            arrays["F_flat"] = None
        try:
            arrays["z_flat"] = dataset.z_flat
        except Exception:
            arrays["z_flat"] = None
    else:
        # Uniform format: R (N, natoms, 3)
        arrays["R"] = dataset.getCoordinates()
        try:
            arrays["F"] = dataset.getForces()
        except Exception:
            arrays["F"] = None
        try:
            arrays["z"] = dataset.getElements()
        except Exception:
            arrays["z"] = None

    # Energies — same shape (N,) for both uniform and variable datasets
    try:
        E = dataset.getEnergies()
        arrays["E"] = np.asarray(E, dtype=np.float64).reshape(-1)
    except Exception:
        arrays["E"] = None

    # ── Include cached prediction data for this dataset ──────────────────
    # Pack prediction arrays as "pred__<dtype>__<model_fp>" entries so the
    # client can reconstruct DataEntity objects and show ghost models in the
    # sidebar without a separate round-trip.
    model_names: dict = {}
    pred_count = 0
    for cache_key in list(env.cache.keys()):
        parts = cache_key.split("__")
        if len(parts) != 3:
            continue
        dt_key, model_fp, ds_fp = parts
        if ds_fp != fingerprint:
            continue
        if dt_key not in ("energy", "forces"):
            continue
        de = env.cache.get(cache_key)
        if de is None:
            continue
        raw = de.get(dt_key)
        if raw is None:
            continue

        # Variable-dataset forces arrive as a list of (natoms_i, 3) arrays;
        # flatten to (total_atoms, 3) — client rebuilds per-molecule slices
        # using the already-transferred offsets.
        if isinstance(raw, list):
            try:
                raw = np.concatenate(raw, axis=0)
            except Exception as exc:
                logger.warning(
                    "Could not concatenate prediction %s for %r: %s",
                    cache_key, fingerprint, exc,
                )
                continue

        arrays[f"pred__{dt_key}__{model_fp}"] = np.asarray(raw)
        pred_count += 1

    # Collect human-readable model names for all models whose prediction
    # data was included above.
    for model_fp, model in env.models.items():
        model_names[model_fp] = getattr(model, "name", model_fp[:8]) or model_fp[:8]

    if pred_count:
        logger.info(
            "Including %d prediction arrays for %d model(s) with dataset %r",
            pred_count, len({k.split("__")[2] for k in arrays if k.startswith("pred__")}),
            fingerprint,
        )

    data = pack_arrays(fingerprint, arrays, model_names=model_names)
    try:
        outbound.put_nowait(data)
    except asyncio.QueueFull:
        # Queue full — blocking put so large transfers aren't dropped
        await outbound.put(data)
    logger.info("Arrays for %r queued (%d bytes)", fingerprint, len(data))


async def _handler(websocket, env, outbound):
    """Handle one WebSocket connection."""
    from cluster.rpc import unpack

    addr = websocket.remote_address
    logger.info("Client connected: %s", addr)

    async def receive_loop():
        async for message in websocket:
            if isinstance(message, bytes):
                try:
                    event, args, kwargs = unpack(message)
                    await _dispatch_client_event(env, event, args, kwargs, outbound)
                except Exception as exc:
                    logger.warning("RPC decode error: %s", exc)
            elif message == "ping":
                await websocket.send("pong")
                logger.debug("Pong sent to %s", addr)
            else:
                logger.debug(
                    "Unknown text message from %s: %r", addr, message
                )

    async def send_loop():
        while True:
            data = await outbound.get()
            try:
                await websocket.send(data)
            except Exception as exc:
                logger.warning(
                    "Send error to %s: %s", addr, exc
                )

    receive_task = asyncio.create_task(receive_loop())
    send_task = asyncio.create_task(send_loop())

    try:
        await receive_task
    except Exception as exc:
        logger.warning("Connection error from %s: %s", addr, exc)
    finally:
        send_task.cancel()
        try:
            await send_task
        except asyncio.CancelledError:
            pass
        logger.info("Client disconnected: %s", addr)


async def _serve(env, outbound, port: int):
    """Run the WebSocket server until the environment signals quit."""
    import websockets

    async def handler(websocket):
        await _handler(websocket, env, outbound)

    logger.info("Starting ffast-server on port %d", port)
    # Bind to "" so the OS picks the right family (IPv4 + IPv6 on most systems).
    async with websockets.serve(handler, "", port):
        logger.info("ffast-server listening on ws://0.0.0.0:%d", port)
        while not env.quitReady:
            await asyncio.sleep(1)
    logger.info("ffast-server shut down")


async def _main(port: int):
    """Bootstrap env, wire RPC subscriptions, run server + event loop."""
    from client.environment import HeadlessEnvironment
    from cluster.rpc import SERVER_TO_CLIENT, pack
    from utils import loadModules

    env = HeadlessEnvironment()
    loadModules(None, env, headless=True)

    # Queue for server→client events (events dropped when full / no client)
    outbound: asyncio.Queue = asyncio.Queue(maxsize=200)

    for evt in SERVER_TO_CLIENT:

        def make_sender(e: str):
            def handler(*args, **kwargs):
                try:
                    data = pack(e, args, kwargs)
                    outbound.put_nowait(data)
                except asyncio.QueueFull:
                    logger.debug(
                        "Outbound queue full, dropping %s event", e
                    )

            return handler

        env.eventSubscribe(evt, make_sender(evt))

    # Send lightweight dataset metadata to the client when any dataset loads.
    # This lets the client create a RemoteDatasetProxy for Loupe without
    # transferring the full arrays.
    def _on_dataset_loaded_meta(fingerprint):
        dataset = env.getDataset(fingerprint)
        if dataset is None:
            return
        try:
            n = dataset.getN()
            name = dataset.getName()
            is_sub = bool(getattr(dataset, "isSubDataset", False))
            try:
                dataset.getForces()
                has_forces = True
            except Exception:
                has_forces = False
            data = pack(
                "REMOTE_DATASET_META",
                (fingerprint,),
                {
                    "name": name,
                    "n": n,
                    "has_forces": has_forces,
                    "is_sub": is_sub,
                },
            )
            outbound.put_nowait(data)
            logger.debug("REMOTE_DATASET_META sent for %r", fingerprint)
        except Exception as exc:
            logger.warning("REMOTE_DATASET_META error: %s", exc)

    env.eventSubscribe("DATASET_LOADED", _on_dataset_loaded_meta)

    # Send lightweight model metadata when a ghost model is registered.
    # MODEL_LOADED fires AFTER _loadPredictionsFromKeys + lookForGhosts(),
    # so prediction arrays are already in env.cache at this point.
    def _on_model_loaded_meta(model_fp):
        model = env.getModel(model_fp)
        if model is None or not getattr(model, "isGhost", False):
            return   # only ghost (prediction) models are relevant remotely
        try:
            name = getattr(model, "name", None) or model_fp[:8]

            # Find which dataset fingerprints this model has predictions for
            dataset_fps = []
            for cache_key in list(env.cache.keys()):
                parts = cache_key.split("__")
                if len(parts) == 3 and parts[1] == model_fp:
                    ds_fp = parts[2]
                    if ds_fp not in dataset_fps:
                        dataset_fps.append(ds_fp)

            data = pack(
                "REMOTE_MODEL_META",
                (model_fp,),
                {
                    "name": name,
                    "dataset_fingerprints": dataset_fps,
                },
            )
            outbound.put_nowait(data)
            logger.info(
                "REMOTE_MODEL_META sent: model=%r name=%r datasets=%r",
                model_fp[:8], name, dataset_fps,
            )
        except Exception as exc:
            logger.warning("REMOTE_MODEL_META error: %s", exc)

    env.eventSubscribe("MODEL_LOADED", _on_model_loaded_meta)

    logger.info("Environment ready")

    await asyncio.gather(
        env.headlessEventLoop(),
        _serve(env, outbound, port),
    )


def cli():
    _setupServerLogger()

    parser = argparse.ArgumentParser(
        description="ffast-server — headless FFAST WebSocket RPC server"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to listen on (default: 8765)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(_main(args.port))
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down")
    except Exception:
        logger.exception("ffast-server crashed during startup")
        raise


if __name__ == "__main__":
    cli()
