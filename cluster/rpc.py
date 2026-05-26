"""
msgpack serialization for FFAST WebSocket RPC.

Wire format (msgpack-encoded dict):
    {"event": str, "args": list, "kwargs": dict}

All values must be msgpack-serializable primitives (str, int, float,
list, dict, bytes, None).  Qt objects and numpy arrays must never cross
the wire.
"""
import msgpack

# Events the server broadcasts to every connected client.
SERVER_TO_CLIENT = frozenset(
    {
        "TASK_CREATED",
        "TASK_PROGRESS",
        "TASK_DONE",
        "TASK_FAILED",
        "DATA_UPDATED",
        "DATASET_LOADED",
        "MODEL_LOADED",
        "DATASET_DELETED",
        "MODEL_DELETED",
    }
)


def pack(event: str, args: tuple, kwargs: dict) -> bytes:
    """Serialize event + args/kwargs to msgpack bytes."""
    return msgpack.packb(
        {"event": event, "args": list(args), "kwargs": kwargs},
        use_bin_type=True,
    )


def unpack(data: bytes) -> tuple:
    """Deserialize msgpack bytes → (event, args, kwargs)."""
    msg = msgpack.unpackb(data, raw=False)
    return msg["event"], msg["args"], msg["kwargs"]
