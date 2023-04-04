import json
import logging

logger = logging.getLogger("FFAST")

with open("config/default.json") as f:
    default = json.load(f)
with open("config/user.json") as f:
    config = json.load(f)


def getConfig(key, fallback=None):
    c = config.get(key, None)
    if c is None:
        return default.get(key, fallback)


def addConfig(key, defaultValue):
    if key in default:
        raise Exception(
            f"Tried to add config of name {key} and default value {defaultValue} but key already registered"
        )
    default[key] = defaultValue
