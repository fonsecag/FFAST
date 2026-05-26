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


def _dispatch_client_event(env, event, args, kwargs):
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

    else:
        logger.warning("Unknown client event: %s", event)


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
                    _dispatch_client_event(env, event, args, kwargs)
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
    async with websockets.serve(handler, "0.0.0.0", port):
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
