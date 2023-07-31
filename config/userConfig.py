import json
import logging
import os

logger = logging.getLogger("FFAST")


class Settings(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = {}  # what actions exist
        self.pendingActions = set()  # which actions are currently pending
        self.parameterActions = {}  # which parameter does which action

    def addAction(self, actionName, func):
        self.actions[actionName] = func

    def doAction(self, actionName):
        func = self.actions.get(actionName, None)
        if func is not None:
            func()

    def addParameter(self, key, defaultValue, *actions):
        self[key] = defaultValue
        self.addParameterActions(key, *actions)

    def addParameterActions(self, key, *actions):
        if len(actions) <= 0:
            return

        if key not in self.parameterActions:
            self.parameterActions[key] = []

        for a in actions:
            if callable(a):
                self.addAction(hash(a), a)
                self.parameterActions[key].append(hash(a))
            else:
                self.parameterActions[key].append(a)

    def addParameters(self, **kwargs):
        for k, v in kwargs.items():
            self.addParameter(k, v[0], *v[1:])

    def setParameter(self, key, value, refresh=True):
        try:
            if self[key] == value:
                return
        except ValueError:
            # means the value cannot be compared, usually if the parameter is an object, list or array
            pass

        self[key] = value

        actions = self.parameterActions.get(key, None)
        if actions is not None:
            for x in actions:
                self.pendingActions.add(x)

        if refresh:
            self.doPendingActions()

    def doPendingActions(self):
        for _ in range(len(self.pendingActions)):
            if not self.pendingActions:
                # check that the set has not become empty since
                return
            actionKey = self.pendingActions.pop()
            self.doAction(actionKey)


# NOTE: The workflow here is not yet 100% clear
# I've iterated throguh different ways of doing but decided
# it was not a priority for now

default = Settings()
config = Settings()

with open("config/default.json") as f:
    d = json.load(f)
    default.update(d)
if os.path.exists("config/user.json"):
    with open("config/user.json") as f:
        c = json.load(f)
        config.update(c)


def getConfig(key, fallback=None):
    c = config.get(key, None)
    if c is None:
        return default.get(key, fallback)
    else:
        return c


def addConfig(key, defaultValue):
    if key in default:
        raise Exception(
            f"Tried to add config of name {key} and default value {defaultValue} but key already registered"
        )
    default[key] = defaultValue
