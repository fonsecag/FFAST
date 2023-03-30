import numpy as np
from client.dataType import DataType
import logging
from scipy.stats import gaussian_kde

logger = logging.getLogger("FFAST")


def loadData(env):

    class AtomicForcesErrorDist(DataType):
        modelDependent = True
        datasetDependent = True
        key = "atomicForcesErrorDist"
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

    env.registerDataType(AtomicForcesErrorDist)


def loadUI(UIHandler, env):
    from UI.ContentTab import ContentTab
    from UI.Plots import BasicPlotWidget

    ct = ContentTab(UIHandler)
    UIHandler.addContentTab(ct, "Atomic Errors")

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

        def addPlots(self):
            for data in self.getWatchedData():
                err = data["dataEntry"].get()
                self.plot(np.arange(err.shape[0]), np.abs(err), autoColor=data)

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange
            return np.arange(max(0, int(x0 + 1)), min(N, int(x1 + 1)))

    class ForcesErrorPlot(BasicPlotWidget):
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

        def addPlots(self):
            for data in self.getWatchedData():
                err = data["dataEntry"].get()
                mae = err.reshape(err.shape[0], -1)
                mae = np.mean(np.abs(mae), axis=1)
                self.plot(np.arange(mae.shape[0]), mae, autoColor=data)

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange
            return np.arange(max(0, int(x0 + 1)), min(N, int(x1 + 1)))

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
