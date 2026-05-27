"""
msgpack serialization for FFAST WebSocket RPC.

Control message wire format (msgpack-encoded dict):
    {"event": str, "args": list, "kwargs": dict}

Control message values must be msgpack-serializable primitives (str, int,
float, list, dict, bytes, None).  Qt objects must never cross the wire.

Array transfer uses the same envelope but encodes each numpy array inside
kwargs as {"__ndarray__": True, "dtype": str, "shape": list, "data": bytes}.
Use pack_arrays / unpack_arrays for the SUBDATASET_ARRAYS event.
"""
import msgpack
import numpy as np

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


# ── numpy array transfer ──────────────────────────────────────────────────────

def _encode_array(arr):
    """Encode a single numpy array as a msgpack-serializable dict."""
    a = np.ascontiguousarray(arr)
    return {
        "__ndarray__": True,
        "dtype": str(a.dtype),
        "shape": list(a.shape),
        "data": a.tobytes(),
    }


def _decode_array(v):
    """Decode a dict produced by _encode_array back to a numpy array."""
    arr = np.frombuffer(bytes(v["data"]), dtype=v["dtype"])
    return arr.reshape(v["shape"]).copy()


def pack_arrays(fingerprint: str, arrays: dict, **extra_kwargs) -> bytes:
    """Serialize a SUBDATASET_ARRAYS response message.

    ``arrays`` values may be numpy arrays or None (e.g. when forces are
    unavailable).  Returns msgpack bytes using the standard event envelope so
    the receiver's existing ``unpack`` call can dispatch on ``event``.

    Any ``extra_kwargs`` are included in the outer msgpack kwargs dict
    alongside ``arrays`` — use this to pass small primitive payloads such as
    ``model_names`` (a plain dict of str→str) without re-encoding as arrays.

    Example::

        data = pack_arrays(
            fp,
            {"R": coords, "F": forces, "z": atomic_nums},
            model_names={"abc123": "SO3LR"},
        )
        await websocket.send(data)
    """
    encoded = {}
    for k, v in arrays.items():
        encoded[k] = None if v is None else _encode_array(v)
    return pack(
        "SUBDATASET_ARRAYS", (fingerprint,), {"arrays": encoded, **extra_kwargs}
    )


def unpack_arrays(kwargs: dict) -> dict:
    """Decode the ``arrays`` payload from a SUBDATASET_ARRAYS kwargs dict.

    Returns a plain dict mapping key → numpy array (or None).

    Example::

        event, args, kw = unpack(data)
        if event == "SUBDATASET_ARRAYS":
            fp = args[0]
            arrays = unpack_arrays(kw)
    """
    result = {}
    for k, v in kwargs["arrays"].items():
        if v is None:
            result[k] = None
        elif isinstance(v, dict) and v.get("__ndarray__"):
            result[k] = _decode_array(v)
        else:
            result[k] = v
    return result
