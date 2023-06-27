import numpy as np
from client.dataType import DataType
import logging
from scipy.stats import gaussian_kde
from config.userConfig import getConfig

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
            mae = np.mean(np.abs(diff))
            de = self.newDataEntity(diff=diff)  # , mae=mae)
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
            mae = np.mean(np.abs(diff))
            rmse = np.sqrt(np.mean(diff ** 2))

            de = self.newDataEntity(
                diff=diff  # atomicMAE=atomicMAE, mae=mae, rmse=rmse
            )
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

            kde = gaussian_kde(diff)

            distX = np.linspace(
                np.min(diff) * 0.95,
                np.max(diff) * 1.05,
                getConfig("plotDistNum"),
            )
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

            distX = np.linspace(
                np.min(mae) * 0.95,
                np.max(mae) * 1.05,
                getConfig("plotDistNum"),
            )
            distY = kde(distX)

            de = self.newDataEntity(distY=distY, distX=distX)
            env.setData(de, self.key, model=model, dataset=dataset)
            return True

    class EnergyErrorMetrics(DataType):
        modelDependent = True
        datasetDependent = True
        key = "energyErrorMetrics"
        dependencies = ["energyError"]
        iterable = False

        def __init__(self, *args):
            super().__init__(*args)

        def data(self, dataset=None, model=None, taskID=None):
            env = self.env

            eErr = env.getData("energyError", model=model, dataset=dataset)

            diff = np.abs(eErr.get("diff"))
            mae = np.mean(np.abs(diff))
            rmse = np.sqrt(np.mean(diff ** 2))

            de = self.newDataEntity(mae=mae, rmse=rmse)
            env.setData(de, self.key, model=model, dataset=dataset)
            return True

    class ForcesErrorMetrics(DataType):
        modelDependent = True
        datasetDependent = True
        key = "forcesErrorMetrics"
        dependencies = ["forcesError"]
        iterable = False

        def __init__(self, *args):
            super().__init__(*args)

        def data(self, dataset=None, model=None, taskID=None):
            env = self.env

            err = env.getData("forcesError", model=model, dataset=dataset)

            diff = np.abs(err.get("diff"))
            atomicMAE = np.mean(np.abs(diff), axis=2)
            mae = np.mean(np.abs(diff))
            rmse = np.sqrt(np.mean(diff ** 2))

            de = self.newDataEntity(atomicMAE=atomicMAE, mae=mae, rmse=rmse)
            env.setData(de, self.key, model=model, dataset=dataset)
            return True

    env.registerDataType(EnergyPredictionError)
    env.registerDataType(ForcesPredictionError)
    env.registerDataType(EnergyErrorDist)
    env.registerDataType(ForcesErrorDist)
    env.registerDataType(EnergyErrorMetrics)
    env.registerDataType(ForcesErrorMetrics)


def loadUI(UIHandler, env):
    from UI.ContentTab import ContentTab
    from UI.Plots import BasicPlotWidget, Table
    from UI.Templates import Slider, Widget, HorizontalContainerScrollArea

    ct = ContentTab(UIHandler)
    UIHandler.addContentTab(ct, "Basic Errors")

    # PLOTS

    class EnergyErrorDistPlot(BasicPlotWidget):
        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Energy MAE distribution",
                isSubbable=True,
                name="Energy Error Distribution",
                **kwargs,
            )
            self.setDataDependencies("energyErrorDist")
            self.setXLabel("Energy MAE", getConfig("energyUnit"))
            self.setYLabel("Density")

        def addPlots(self):
            for data in self.getWatchedData():
                de = data["dataEntry"]
                x, y = de.get("distX"), de.get("distY")
                self.plot(x, y, autoColor=data)

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange

            eErr = env.getData("energyError", model=model, dataset=dataset)
            diff = np.abs(eErr.get("diff"))

            idxs = np.argwhere((diff >= x0) & (diff <= x1))
            idxs = np.unique(idxs)

            return idxs

    class ForcesErrorDistPlot(BasicPlotWidget):
        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Forces MAE distribution",
                isSubbable=False,  # not finding a good way to do it
                # If we say: at least one force component f with x0 < f < x1
                # then for large molecules, even small windows have a shitload
                # of indices
                # If we average the force error by geometry
                # then outliers can be hidden within otherwise okay geometries
                # as tested on DHA
                # Perhaps error scatters are better for the outliers,
                # but there only one/two points can realistically be selected
                # at the same time
                name="Force Error Distribution",
                **kwargs,
            )
            self.setDataDependencies("forcesErrorDist")
            self.setXLabel("Forces MAE", getConfig("forceUnit"))
            self.setYLabel("Density")

        def addPlots(self):
            for data in self.getWatchedData():
                de = data["dataEntry"]
                x, y = de.get("distX"), de.get("distY")
                self.plot(x, y, autoColor=data)

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange

            err = env.getData("forcesError", model=model, dataset=dataset)
            diff = np.abs(err.get("diff"))
            nConf = diff.shape[0]
            diff = diff.reshape(-1)
            nAtoms = dataset.getNAtoms()

            idxs = np.argwhere((diff >= x0) & (diff <= x1))
            idxs = np.unique(idxs // (nAtoms * 3))

            return idxs

    class EnergyErrorPlot(BasicPlotWidget):
        smoothing = 1

        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Energy MAE timeline",
                name="Energy Error TimelineP",
                **kwargs,
            )
            self.setDataDependencies("energyError")
            self.setXLabel("Configuration index")
            self.setYLabel("Energy MAE", getConfig("energyUnit"))

            self.slider = Slider(
                hasEditBox=True, label="Smoothing", nMin=1, nMax=10000
            )
            self.slider.setToolTip("Number of points in sliding average")
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
                **kwargs,
            )
            self.setDataDependencies("forcesError")
            self.setXLabel("Configuration index")
            self.setYLabel("Forces MAE", getConfig("forceUnit"))

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


    # TABLES
    scrollContainer = HorizontalContainerScrollArea()
    scrollContainer.content.layout.setSpacing(32)

    class BaseTable(Table):
        def __init__(self, **kwargs):
            super().__init__(UIHandler, parent=ct, **kwargs)
            ct.addDataSelectionCallback(self.setModelDatasetDependencies)

        def getSize(self):
            # placeholder, should be implemented by user
            nCols = len(self.getDatasetDependencies())
            nRows = len(self.getModelDependencies())
            return (nRows, nCols)

        def getLeftHeader(self, i):
            models = self.getModelDependencies()
            model = self.handler.env.getModel(models[i])
            return f"{model.getDisplayName()}"

        def getTopHeader(self, i):
            datasets = self.getDatasetDependencies()
            dataset = self.handler.env.getDataset(datasets[i])
            return f"{dataset.getDisplayName()}"

    class EnergyMAETable(BaseTable):
        def __init__(self):
            super().__init__(title="Energy MAE")
            self.setDataDependencies("energyErrorMetrics")

        def getValue(self, i, j):
            env = self.handler.env
            model = self.getModelDependencies()[i]
            dataset = self.getDatasetDependencies()[j]
            de = env.getData(
                "energyErrorMetrics",
                model=env.getModel(model),
                dataset=env.getDataset(dataset),
            )

            if de is None:
                return ""
            else:
                return f"{de.get('mae'):.2f}"

    class EnergyRMSETable(BaseTable):
        def __init__(self):
            super().__init__(title="Energy RMSE")
            self.setDataDependencies("energyErrorMetrics")

        def getValue(self, i, j):
            env = self.handler.env
            model = self.getModelDependencies()[i]
            dataset = self.getDatasetDependencies()[j]
            de = env.getData(
                "energyErrorMetrics",
                model=env.getModel(model),
                dataset=env.getDataset(dataset),
            )

            if de is None:
                return ""
            else:
                return f"{de.get('rmse'):.2f}"

    class ForcesMAETable(BaseTable):
        def __init__(self):
            super().__init__(title="Forces MAE")
            self.setDataDependencies("forcesErrorMetrics")

        def getValue(self, i, j):
            env = self.handler.env
            model = self.getModelDependencies()[i]
            dataset = self.getDatasetDependencies()[j]
            de = env.getData(
                "forcesErrorMetrics",
                model=env.getModel(model),
                dataset=env.getDataset(dataset),
            )

            if de is None:
                return ""
            else:
                return f"{de.get('mae'):.2f}"

    class ForcesRMSERable(BaseTable):
        def __init__(self):
            super().__init__(title="Forces RMSE")
            self.setDataDependencies("forcesErrorMetrics")

        def getValue(self, i, j):
            env = self.handler.env
            model = self.getModelDependencies()[i]
            dataset = self.getDatasetDependencies()[j]
            de = env.getData(
                "forcesErrorMetrics",
                model=env.getModel(model),
                dataset=env.getDataset(dataset),
            )

            if de is None:
                return ""
            else:
                return f"{de.get('rmse'):.2f}"

    scrollContainer.addContent(EnergyMAETable())
    scrollContainer.addContent(EnergyRMSETable())
    scrollContainer.addContent(ForcesMAETable())
    scrollContainer.addContent(ForcesRMSERable())
    scrollContainer.addStretch()

    # argument are (row, col, rowSpan, colSpan)
    ct.addWidget(scrollContainer, 2, 0, 1, 2)