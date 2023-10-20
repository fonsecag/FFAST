import numpy as np
from client.dataType import DataType
import logging
from scipy.stats import gaussian_kde
from config.atoms import zIntToZStr, atomColors
from config.userConfig import getConfig

logger = logging.getLogger("FFAST")

DEPENDENCIES = ["basicErrors"]


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
            z = dataset.getElements()

            diffAll = err.get("diff")
            out = {}

            for i in np.unique(z):
                idxs = np.argwhere(z == i)
                idxs = idxs.flatten()

                diff = diffAll[:, idxs, :]

                diff = diff.reshape(diff.shape[0], -1)
                mae = np.mean(np.abs(diff), axis=1)

                kde = gaussian_kde(np.abs(mae))

                distX = np.linspace(
                    np.min(mae) * 0.95,
                    np.max(mae) * 1.05,
                    getConfig("plotDistNum"),
                )
                distY = kde(distX)

                out[zIntToZStr[i]] = {"distY": distY, "distX": distX}

            de = self.newDataEntity(**out)
            env.setData(de, self.key, model=model, dataset=dataset)
            return True

    class AtomicForceErrors(DataType):
        modelDependent = True
        datasetDependent = True
        key = "atomicForcesError"
        dependencies = ["forcesError"]
        iterable = False

        def __init__(self, *args):
            super().__init__(*args)

        def data(self, dataset=None, model=None, taskID=None):
            env = self.env

            err = env.getData("forcesError", model=model, dataset=dataset)
            z = dataset.getElements()

            diffAll = err.get("diff")
            out = {}

            for i in np.unique(z):
                idxs = np.argwhere(z == i)
                idxs = idxs.flatten()

                diff = diffAll[:, idxs, :]

                diff = diff.reshape(diff.shape[0], -1)
                mae = np.mean(np.abs(diff))
                rmse = np.sqrt(np.mean(diff ** 2))

                out[zIntToZStr[i]] = {"mae": mae, "rmse": rmse}

            de = self.newDataEntity(**out)
            env.setData(de, self.key, model=model, dataset=dataset)
            return True

    env.registerDataType(AtomicForcesErrorDist)
    env.registerDataType(AtomicForceErrors)


def loadUI(UIHandler, env):
    from UI.ContentTab import ContentTab, DatasetModelSelector, ListCheckButton
    from UI.Plots import BasicPlotWidget, Table
    from UI.Templates import FlexibleListSelector
    from config.atoms import atomColors, zIntToZStr

    ct = ContentTab(
        UIHandler, hasDataSelector=False
    )  # adding a new one manually
    UIHandler.addContentTab(ct, "Atomic Errors")

    class AtomLabel(ListCheckButton):
        def __init__(self, atomIndex, *args, **kwargs):
            color = atomColors[atomIndex]
            name = zIntToZStr[atomIndex]
            self.atomIndex = atomIndex
            self.atomName = name
            super().__init__(*args, color=color, label=name, **kwargs)

    class AtomicDatasetModelSelector(DatasetModelSelector):

        lastSelectedDataset = None

        def __init__(self, UIHandler, parent=None):
            super().__init__(UIHandler, parent=parent)
            self.atomsList = FlexibleListSelector(
                parent=self, label="Selected elements", elementSize=50
            )
            self.atomsList.setOnUpdate(self.update)
            self.layout.addWidget(self.atomsList)

            self.datasetsList.singleSelection = True

        def getSelectedAtomIndices(self):
            return [x.atomIndex for x in self.atomsList.getSelectedWidgets()]

        def getSelectedAtomInfo(self):
            l = {}
            idxs = self.getSelectedAtomIndices()
            for i in idxs:
                l[zIntToZStr[i]] = {"index": i, "color": atomColors[i]}

            return l

        def update(self):
            modelKeys, datasetKeys = self.getSelectedKeys()
            if len(datasetKeys) > 1:
                logger.error(
                    f"Too many keys in singleton dataset selector: {datasetKeys}"
                )
                return

            key = None
            if len(datasetKeys) > 0:
                key = datasetKeys[0]
            if key != self.lastSelectedDataset:
                self.lastSelectedDataset = key
                self.updateAtomsList()

            nModels, nTypes = (
                len(modelKeys),
                len(self.getSelectedAtomIndices()),
            )

            self.atomsList.singleSelection = nModels > 1
            self.modelsList.singleSelection = nTypes > 1

            DatasetModelSelector.update(self)

        def updateAtomsList(self):
            key = self.lastSelectedDataset

            self.atomsList.removeWidgets(clear=True)
            if key is not None:
                dataset = self.handler.env.getDataset(key)
                if dataset is None:
                    return

                elements = set(dataset.getElements())

                if len(elements) > 0:
                    label = AtomLabel(0, parent=self.atomsList)  # All
                    self.atomsList.addWidget(label)

                for i in elements:
                    label = AtomLabel(i, parent=self.atomsList)
                    self.atomsList.addWidget(label)

    dataselector = AtomicDatasetModelSelector(UIHandler, parent=ct)
    ct.setDataSelector(dataselector)

    class ForcesErrorDistPlot(BasicPlotWidget):
        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Forces MAE distribution",
                isSubbable=False,
                name="Force Error Distribution",
                **kwargs,
            )
            self.setDataDependencies(
                "atomicForcesErrorDist", "forcesErrorDist"
            )
            self.setXLabel("Forces MAE", getConfig("forceUnit"))
            self.setYLabel("Density")

        def addPlots(self):

            atomTypes = dataselector.getSelectedAtomInfo()
            atomMode = len(atomTypes) > 1
            hasAll = "All" in atomTypes

            for data in self.getWatchedData():
                de = data["dataEntry"]
                dataType = data["dataTypeKey"]

                if dataType == "forcesErrorDist":
                    if not hasAll:
                        continue

                    x, y = de.get("distX"), de.get("distY")
                    if atomMode:
                        self.plot(x, y, color=atomColors[0], autoLabel=data)
                    else:
                        self.plot(x, y, autoColor=data, autoLabel=data)

                else:
                    for atom, info in atomTypes.items():
                        if atom == "All":
                            continue

                        atomDE = de.get(atom)

                        x, y = atomDE.get("distX"), atomDE.get("distY")

                        if atomMode:
                            self.plot(
                                x, y, color=info["color"], autoLabel=data
                            )
                        else:
                            self.plot(x, y, autoColor=data, autoLabel=data)

    plt = ForcesErrorDistPlot(UIHandler, parent=ct)
    ct.addWidget(plt, 0, 0)
    ct.addDataSelectionCallback(plt.setModelDatasetDependencies)

    class AtomicErrorTable(Table):
        def __init__(self, **kwargs):
            super().__init__(
                UIHandler, parent=ct, title="Atomic Errors", **kwargs
            )
            ct.addDataSelectionCallback(self.setModelDatasetDependencies)
            self.setDataDependencies("atomicForcesError", "forcesErrorMetrics")

        def getSize(self):
            atomTypes = dataselector.getSelectedAtomInfo()
            nCols = 2
            if len(atomTypes) == 0:
                nRows = 0
            elif len(atomTypes) > 1:
                nRows = len(atomTypes)
            else:
                nRows = max(
                    len(self.getModelDependencies()),
                    len(self.getDatasetDependencies()),
                )
            return (nRows, nCols)

        def getLeftHeader(self, i):
            atomTypes = dataselector.getSelectedAtomInfo()
            if len(self.getDatasetDependencies()) > 1:
                datasets = self.getDatasetDependencies()
                dataset = self.handler.env.getDataset(datasets[i])
                return f"{dataset.getDisplayName()}"
            elif len(self.getModelDependencies()) > 1:
                models = self.getModelDependencies()
                model = self.handler.env.getModel(models[i])
                return f"{model.getDisplayName()}"
            else:
                return f"{list(atomTypes.keys())[i]}"

        def getTopHeader(self, i):
            if i == 0:
                return "MAE"
            elif i == 1:
                return "RMSE"
            else:
                return "/"

        def getValue(self, i, j):
            atomTypes = list(dataselector.getSelectedAtomInfo().keys())
            atomMode = len(atomTypes) > 1

            models = self.getModelDependencies()
            dataset = self.getDatasetDependencies()[0]
            value = None

            if atomMode:
                model = models[0]
                atomType = atomTypes[i]
            else:
                model = models[i]
                atomType = atomTypes[0]

            if atomType == "All":
                de = self.handler.env.getData(
                    "forcesErrorMetrics", dataset=dataset, model=model
                )
                if de is None:
                    return
                if j == 0:
                    value = de.get("mae")
                else:
                    value = de.get("rmse")

            else:
                de = self.handler.env.getData(
                    "atomicForcesError", dataset=dataset, model=model
                )
                if de is None:
                    return

                if j == 0:
                    value = de.get(atomType)["mae"]
                else:
                    value = de.get(atomType)["rmse"]

            if value is not None:
                return f"{value:.2f}"

    table = AtomicErrorTable()
    ct.addWidget(table, 1, 0)
