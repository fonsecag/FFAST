import numpy as np
from client.dataType import DataType, DataEntity
from UI.plots import BasicPlotContainer
from UI.tab import Tab
import logging
from scipy.stats import gaussian_kde

logger = logging.getLogger("FFAST")


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

        print('\n\n--------LOOK HERE---------') # eradendum
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


class EnergyErrorDistPlot(BasicPlotContainer):
    def __init__(self, handler, tab):
        super().__init__(
            handler,
            parentSelector=True,
            title="Energy MAE distribution",
            isSubbable=False,
            name="EnErrDist",
        )
        self.setDataDependencies("energyErrorDist")
        self.setXLabel("Energy MAE", "kcal/mol")
        self.setYLabel("Density")

    def addPlots(self):
        for x in self.getWatchedData():
            de = x["dataEntry"]
            x, y = de.get("distX"), de.get("distY")
            self.plot(x, y)

    # TODO: make 3d active
    # def getXRangeDatasetIndices(self, xRange, dataset):
    #     N = dataset.getN()
    #     x0, x1 = xRange
    #     return np.arange(max(0, int(x0 + 1)), min(N, int(x1 + 1)))


class ForcesErrorDistPlot(BasicPlotContainer):
    def __init__(self, handler, tab):
        super().__init__(
            handler,
            parentSelector=True,
            title="Forces MAE distribution",
            isSubbable=False,
            name="FoErrDist",
        )
        self.setDataDependencies("forcesErrorDist")
        self.setXLabel("Forces MAE", "kcal/mol")
        self.setYLabel("Density")

    def addPlots(self):
        for x in self.getWatchedData():
            de = x["dataEntry"]
            x, y = de.get("distX"), de.get("distY")
            self.plot(x, y)

    # TODO: make 3d active
    # def getXRangeDatasetIndices(self, xRange, dataset):
    #     N = dataset.getN()
    #     x0, x1 = xRange
    #     return np.arange(max(0, int(x0 + 1)), min(N, int(x1 + 1)))


class EnergyErrorPlot(BasicPlotContainer):
    def __init__(self, handler, tab):
        super().__init__(
            handler,
            parentSelector=True,
            title="Energy MAE timeline",
            name="EnErr",
        )
        self.setDataDependencies("energyError")
        self.setXLabel("Configuration index")
        self.setYLabel("Energy MAE", "kcal/mol")

    def addPlots(self):
        for x in self.getWatchedData():
            err = x["dataEntry"].get()
            self.plot(np.arange(err.shape[0]), np.abs(err))

    def getDatasetSubIndices(self, dataset, model):
        (xRange, yRange) = self.getRanges()
        N = dataset.getN()
        x0, x1 = xRange
        return np.arange(max(0, int(x0 + 1)), min(N, int(x1 + 1)))


class ForcesErrorPlot(BasicPlotContainer):
    def __init__(self, handler, tab):
        super().__init__(
            handler,
            parentSelector=True,
            title="Forces MAE timeline",
            name="FoErr",
        )
        self.setDataDependencies("forcesError")
        self.setXLabel("Configuration index")
        self.setYLabel("Forces MAE", "kcal/mol A")

    def addPlots(self):
        for x in self.getWatchedData():
            err = x["dataEntry"].get()
            mae = err.reshape(err.shape[0], -1)
            mae = np.mean(np.abs(mae), axis=1)
            self.plot(np.arange(mae.shape[0]), mae)

    def getDatasetSubIndices(self, dataset, model):
        (xRange, yRange) = self.getRanges()
        N = dataset.getN()
        x0, x1 = xRange
        return np.arange(max(0, int(x0 + 1)), min(N, int(x1 + 1)))


def load(UIHandler, env):
    env.registerDataType(EnergyPredictionError)
    env.registerDataType(ForcesPredictionError)
    env.registerDataType(EnergyErrorDist)
    env.registerDataType(ForcesErrorDist)

    tab = Tab(UIHandler, hasDatasetSelector=True, hasModelSelector=True)
    UIHandler.addTab(tab, "Basic")

    plot = EnergyErrorDistPlot(UIHandler, tab)
    tab.addWidget(plot, 0, 0)

    plot = ForcesErrorDistPlot(UIHandler, tab)
    tab.addWidget(plot, 0, 1)

    plot = EnergyErrorPlot(UIHandler, tab)
    tab.addWidget(plot, 1, 0)

    plot = ForcesErrorPlot(UIHandler, tab)
    tab.addWidget(plot, 1, 1)

    tab.addBottomVerticalSpacer()
