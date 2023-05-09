from loaders.modelLoader import ModelLoader
import numpy as np


class ZeroModelLoader(ModelLoader):
    modelName = "Zero Model"
    fingerprint = "zeroModel"
    singlePredict = True

    def __init__(self, env, *args, **kwargs):
        super().__init__(env, "N/A", *args, **kwargs)
        self.name = "Zero Model"

    def predict(self, dataset, indices=None, batchSize=50, taskID=None):
        R = dataset.getCoordinates()
        return np.zeros(R.shape[0]), np.zeros_like(R)

    def getFingerprint(self):
        return self.fingerprint

    def getDisplayName(self):
        return f"{self.getName()}"

    def initialise(self):
        pass
