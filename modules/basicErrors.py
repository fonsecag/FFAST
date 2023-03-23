import numpy as np
from client.dataType import DataType
import logging
from scipy.stats import gaussian_kde

logger = logging.getLogger("FFAST")


def loadData(env):
    class EnergyPredictionError(DataType):
        modelDependent = True
        datasetDependent = True
        key = "energyError"
        dependencies = ["energy"]
        iterable = True

        def __init__(self, *args):
            super().__init__(*args)

        def data(self, dataset=None, model=None, taskID=None):
            env = self.env

            ePred = env.getData("energy", model=model, dataset=dataset)
            eData = dataset.getEnergies()

            diff = ePred.get("energy") - eData
            de = self.newDataEntity(diff=diff)
            env.setData(de, self.key, model=model, dataset=dataset)
            return True

    class ForcesPredictionError(DataType):
        modelDependent = True
        datasetDependent = True
        key = "forcesError"
        dependencies = ["forces"]
        iterable = True

        def __init__(self, *args):
            super().__init__(*args)

        def data(self, dataset=None, model=None, taskID=None):
            env = self.env

            fPred = env.getData("forces", model=model, dataset=dataset)
            fData = dataset.getForces()

            N = fData.shape[0]

            diff = fPred.get("forces") - fData

            de = self.newDataEntity(diff=diff)
            env.setData(de, self.key, model=model, dataset=dataset)
            return True

    class EnergyErrorDist(DataType):
        modelDependent = True
        datasetDependent = True
        key = "energyErrorDist"
        dependencies = ["energyError"]
        iterable = False

        def __init__(self, *args):
            super().__init__(*args)

        def data(self, dataset=None, model=None, taskID=None):
            env = self.env

            eErr = env.getData("energyError", model=model, dataset=dataset)

            diff = np.abs(eErr.get("diff"))

            N = env.getConfig("errorDistNKdePoints")
            kde = gaussian_kde(np.abs(diff))

            distX = np.linspace(np.min(diff) * 0.95, np.max(diff) * 1.05)
            distY = kde(distX)

            de = self.newDataEntity(distY=distY, distX=distX)
            env.setData(de, self.key, model=model, dataset=dataset)
            return True

    class ForcesErrorDist(DataType):
        modelDependent = True
        datasetDependent = True
        key = "forcesErrorDist"
        dependencies = ["forcesError"]
        iterable = False

        def __init__(self, *args):
            super().__init__(*args)

        def data(self, dataset=None, model=None, taskID=None):
            env = self.env

            err = env.getData("forcesError", model=model, dataset=dataset)

            diff = np.abs(err.get("diff"))
            diff = diff.reshape(diff.shape[0], -1)
            mae = np.mean(np.abs(diff), axis=1)

            N = env.getConfig("errorDistNKdePoints")
            kde = gaussian_kde(np.abs(mae))

            distX = np.linspace(np.min(mae) * 0.95, np.max(mae) * 1.05)
            distY = kde(distX)

            de = self.newDataEntity(distY=distY, distX=distX)
            env.setData(de, self.key, model=model, dataset=dataset)
            return True

    env.registerDataType(EnergyPredictionError)
    env.registerDataType(ForcesPredictionError)
    env.registerDataType(EnergyErrorDist)
    env.registerDataType(ForcesErrorDist)


def loadUI(UIHandler, env):
    from UI.ContentTab import ContentTab
    from UI.Plots import BasicPlotWidget

    ct = ContentTab(UIHandler)
    UIHandler.addContentTab(ct, "Basic Errors")

    for i in range(2):
        for j in range(2):
            a = BasicPlotWidget(UIHandler, env, parent=ct)
            ct.addWidget(a, i, j)
