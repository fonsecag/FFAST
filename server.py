"""
ffast-server — headless FFAST environment wrapped in a WebSocket server.

Runs on a cluster compute node after SLURM allocates resources.
Connect with: websocat ws://localhost:<port>
Send "ping", receive "pong" to confirm the server is alive.

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


async def _handler(websocket):
    """Handle a single WebSocket connection."""
    addr = websocket.remote_address
    logger.info("Connection from %s", addr)
    try:
        async for message in websocket:
            logger.info("Received from %s: %r", addr, message)
            if message == "ping":
                await websocket.send("pong")
                logger.info("Sent pong to %s", addr)
            else:
                logger.info("Unknown message from %s: %r", addr, message)
    except Exception as exc:
        logger.warning("Connection error from %s: %s", addr, exc)
    finally:
        logger.info("Connection closed: %s", addr)


async def _serve(env, port: int):
    """Start the WebSocket server and run until interrupted."""
    import websockets

    logger.info("Starting ffast-server on port %d", port)
    async with websockets.serve(_handler, "0.0.0.0", port):
        logger.info("ffast-server listening on ws://0.0.0.0:%d", port)
        # Keep serving until the environment signals quit or process exits
        while not env.quitReady:
            await asyncio.sleep(1)
    logger.info("ffast-server shut down")


def cli():
    _setupServerLogger()

    parser = argparse.ArgumentParser(
        description="ffast-server — headless FFAST WebSocket server"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to listen on (default: 8765)",
    )
    args = parser.parse_args()

    from client.environment import startHeadlessEnvironment

    logger.info("Starting headless FFAST environment...")
    env = startHeadlessEnvironment()
    logger.info("Environment ready")

    try:
        asyncio.run(_serve(env, args.port))
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down")
    finally:
        env.headlessQuit()


if __name__ == "__main__":
    cli()
