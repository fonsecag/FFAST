from .loader import ModelLoader
import numpy as np
from Utils.misc import md5FromArraysAndStrings


class GhostModelLoader(ModelLoader):
    isGhost = True
    modelName = "Ghost Model"

    def __init__(self, env, fingerprint, *args, **kwargs):
        """
        Initialises the ModelLoader given a path to the model. All methods
        that are only called once (i.e. loading the model) are performed here.

        Args:
            path (str): path to the model
        """
        self.fingerprint = fingerprint
        super().__init__(env, "N/A", *args, **kwargs)

    def predict(self, dataset, indices=None, batchSize=50, taskID=None):
        return None

    def getFingerprint(self):
        return self.fingerprint

    def getDisplayName(self):
        return f"*{self.getName()}"

    def initialise(self):
        self.setName(self.fingerprint)
