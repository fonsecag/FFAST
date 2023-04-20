import numpy as np
from client.dataType import DataType
import logging
from scipy.stats import gaussian_kde

logger = logging.getLogger("FFAST")

DEPENDENCIES = []


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

            diff = fPred.get("forces") - fData
            atomicMAE = np.mean(np.abs(diff), axis=2)

            de = self.newDataEntity(diff=diff, atomicMAE=atomicMAE)
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
    from UI.ContentTab import ContentTab, DatasetModelSelector
    from UI.Plots import BasicPlotWidget
    from UI.Templates import Slider

    ct = ContentTab(UIHandler)
    UIHandler.addContentTab(ct, "Basic Errors")

    class EnergyErrorDistPlot(BasicPlotWidget):
        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Energy MAE distribution",
                isSubbable=False,
                name="Energy Error Distribution",
                **kwargs
            )
            self.setDataDependencies("energyErrorDist")
            self.setXLabel("Energy MAE")
            self.setYLabel("Density")

        def addPlots(self):
            for data in self.getWatchedData():
                de = data["dataEntry"]
                x, y = de.get("distX"), de.get("distY")
                self.plot(x, y, autoColor=data)

    class ForcesErrorDistPlot(BasicPlotWidget):
        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Forces MAE distribution",
                isSubbable=False,
                name="Force Error Distribution",
                **kwargs
            )
            self.setDataDependencies("forcesErrorDist")
            self.setXLabel("Forces MAE")
            self.setYLabel("Density")

        def addPlots(self):
            for data in self.getWatchedData():
                de = data["dataEntry"]
                x, y = de.get("distX"), de.get("distY")
                self.plot(x, y, autoColor=data)

    class EnergyErrorPlot(BasicPlotWidget):
        smoothing = 1

        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Energy MAE timeline",
                name="Energy Error Timeline",
                **kwargs
            )
            self.setDataDependencies("energyError")
            self.setXLabel("Configuration index")
            self.setYLabel("Energy MAE")

            self.slider = Slider(
                hasEditBox=True, label="Smoothing", nMin=1, nMax=10000
            )
            self.addOption(self.slider)
            self.slider.setCallbackFunc(self.updateSmoothing)

        def updateSmoothing(self, value):
            self.smoothing = value
            self.visualRefresh(force=True)

        def addPlots(self):
            smoothing = self.smoothing
            for data in self.getWatchedData():
                err = data["dataEntry"].get("diff")
                err = np.convolve(
                    err, np.ones(smoothing) / smoothing, mode="valid"
                )
                self.plot(np.arange(err.shape[0]), np.abs(err), autoColor=data)

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange
            return np.arange(
                max(0, int(x0 + self.smoothing)),
                min(N, int(x1 + self.smoothing)),
            )

    class ForcesErrorPlot(BasicPlotWidget):

        smoothing = 1

        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Forces MAE timeline",
                name="Force Error Timeline",
                **kwargs
            )
            self.setDataDependencies("forcesError")
            self.setXLabel("Configuration index")
            self.setYLabel("Forces MAE")

            self.slider = Slider(
                hasEditBox=True, label="Smoothing", nMin=1, nMax=10000
            )
            self.addOption(self.slider)
            self.slider.setCallbackFunc(self.updateSmoothing)

        def updateSmoothing(self, value):
            self.smoothing = value
            self.visualRefresh(force=True)

        def addPlots(self):
            smoothing = self.smoothing
            for data in self.getWatchedData():
                err = data["dataEntry"].get("diff")
                mae = err.reshape(err.shape[0], -1)
                mae = np.mean(np.abs(mae), axis=1)
                mae = np.convolve(
                    mae, np.ones(smoothing) / smoothing, mode="valid"
                )
                self.plot(np.arange(mae.shape[0]), mae, autoColor=data)

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange
            return np.arange(
                max(0, int(x0 + self.smoothing)),
                min(N, int(x1 + self.smoothing)),
            )

    plt = EnergyErrorDistPlot(UIHandler, parent=ct)
    ct.addWidget(plt, 0, 0)
    ct.addDataSelectionCallback(plt.setModelDatasetDependencies)

    plt = ForcesErrorDistPlot(UIHandler, parent=ct)
    ct.addWidget(plt, 0, 1)
    ct.addDataSelectionCallback(plt.setModelDatasetDependencies)

    plt = EnergyErrorPlot(UIHandler, parent=ct)
    ct.addWidget(plt, 1, 0)
    ct.addDataSelectionCallback(plt.setModelDatasetDependencies)

    plt = ForcesErrorPlot(UIHandler, parent=ct)
    ct.addWidget(plt, 1, 1)
    ct.addDataSelectionCallback(plt.setModelDatasetDependencies)
