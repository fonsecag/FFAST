from loaders.modelLoader import ModelLoader
import numpy as np
from utils import md5FromArraysAndStrings


class GhostModelLoader(ModelLoader):
    isGhost = True
    modelName = "Ghost Model"

    def __init__(self, env, fingerprint, *args, **kwargs):
        self.fingerprint = fingerprint
        super().__init__(env, "N/A", *args, **kwargs)

    def predict(self, dataset, indices=None, batchSize=50, taskID=None):
        return None

    def getFingerprint(self):
        return self.fingerprint

    def getDisplayName(self):
        return f"*{self.getName()}"

    def initialise(self):
        # search for path and name in info
        if "objects" not in self.env.info:
            self.path = "?"
            self.setName("?")
            return

        info = self.env.info["objects"].get(self.fingerprint, None)
        if info is not None:
            self.path = info["path"]
            self.setName(info["name"])
