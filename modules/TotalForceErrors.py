import numpy as np
from client.dataType import DataType
import logging
from scipy.stats import gaussian_kde
from config.userConfig import getConfig

logger = logging.getLogger("FFAST")

DEPENDENCIES = ["basicErrors"]

def loadData(env):
    class TotalForcesErrorDist(DataType):
            modelDependent = True
            datasetDependent = True
            key = "totalForcesErrorDist"
            dependencies = ["forcesError"]
            iterable = False

            def __init__(self, *args):
                super().__init__(*args)

            def data(self, dataset=None, model=None, taskID=None):
                env = self.env

                err = env.getData("forcesError", model=model, dataset=dataset)
                err = err.get("diff").sum(axis = 1)
                diff = np.abs(err)
                diff = diff.reshape(diff.shape[0], -1)
                mae = np.mean(np.abs(diff), axis=1)
                mae = np.concatenate([-np.abs(mae), np.abs(mae)])

                kde = gaussian_kde(mae)

                delta = np.max(mae) - 0

                distX = np.linspace(
                    0,
                    np.max(mae) + delta * 0.05,
                    getConfig("plotDistNum"),
                )
                distY = kde(distX)

                de = self.newDataEntity(distY=distY, distX=distX)
                env.setData(de, self.key, model=model, dataset=dataset)
                return True

    class TotalForcesErrorMetrics(DataType):


        modelDependent = True
        datasetDependent = True
        key = "totalForcesErrorMetrics"
        dependencies = ["forcesError"]
        iterable = False

        def __init__(self, *args):
            super().__init__(*args)

        def data(self, dataset=None, model=None, taskID=None):
            env = self.env
            err = env.getData("forcesError", model=model, dataset=dataset)
            err = err.get("diff").sum(axis = 1)

            diff = np.abs(err)
            mae = np.mean(np.abs(diff))
            rmse = np.sqrt(np.mean(diff ** 2))
            de = self.newDataEntity(mae=mae, rmse=rmse)
            env.setData(de, self.key, model=model, dataset=dataset)
            return True

    env.registerDataType(TotalForcesErrorDist)
    env.registerDataType(TotalForcesErrorMetrics)

def loadUI(UIHandler, env):
    from UI.ContentTab import ContentTab
    from UI.Plots import BasicPlotWidget, Table
    from UI.Templates import HorizontalContainerScrollArea

    ct = ContentTab(
        UIHandler, hasDataSelector=True
    )  # adding a new one manually
    UIHandler.addContentTab(ct, "Total Force Errors")

    class TotalForcesErrorDistPlot(BasicPlotWidget):
        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Forces MAE distribution",
                isSubbable=False,
                name="Force Error Distribution",
                **kwargs,
            )
            self.setDataDependencies("totalForcesErrorDist")
            self.setXLabel("Forces MAE", getConfig("forceUnit"))
            self.setYLabel("Density")


        def addPlots(self):
            for data in self.getWatchedData():
                de = data["dataEntry"]
                x, y = de.get("distX"), de.get("distY")
                self.plot(x, y, autoColor=data, autoLabel=data)

    plt = TotalForcesErrorDistPlot(UIHandler, parent=ct)
    ct.addWidget(plt, 0, 0)
    ct.addDataSelectionCallback(plt.setModelDatasetDependencies)

    # TABLES
    scrollContainer = HorizontalContainerScrollArea()
    scrollContainer.content.layout.setSpacing(32)

    class BaseTable(Table):
        def __init__(self, **kwargs):
            super().__init__(UIHandler, parent=ct, **kwargs)
            ct.addDataSelectionCallback(self.setModelDatasetDependencies)

        def getSize(self):
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

    class ForcesMAETable(BaseTable):
        def __init__(self):
            super().__init__(title="Forces MAE")
            self.setDataDependencies("totalForcesErrorMetrics")

        def getValue(self, i, j):
            env = self.handler.env
            model = self.getModelDependencies()[i]
            dataset = self.getDatasetDependencies()[j]
            de = env.getData(
                "totalForcesErrorMetrics",
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
            self.setDataDependencies("totalForcesErrorMetrics")

        def getValue(self, i, j):
            env = self.handler.env
            model = self.getModelDependencies()[i]
            dataset = self.getDatasetDependencies()[j]
            de = env.getData(
                "totalForcesErrorMetrics",
                model=env.getModel(model),
                dataset=env.getDataset(dataset),
            )

            if de is None:
                return ""
            else:
                return f"{de.get('rmse'):.2f}"

    scrollContainer.addContent(ForcesMAETable())
    scrollContainer.addContent(ForcesRMSERable())
    scrollContainer.addStretch()

    # argument are (row, col, rowSpan, colSpan)
    ct.addWidget(scrollContainer, 2, 0, 1, 2)