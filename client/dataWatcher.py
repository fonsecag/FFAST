from events import EventChildClass
import logging

logger = logging.getLogger("FFAST")


class DataWatcher(EventChildClass):
    """
    They're always watching.
    """

    def __init__(self, env):
        super().__init__()
        self.env = env
        self.env.addEventChild(self)

        self.eventSubscribe("DATA_UPDATED", self.onDataUpdated)
        self.eventSubscribe("DATASET_LOADED", self.refreshDependencyList)
        self.eventSubscribe("MODEL_LOADED", self.refreshDependencyList)
        self.eventSubscribe("DATASET_UPDATED", self.onDatasetUpdated)
        self.eventSubscribe(
            "DATASET_STATE_CHANGED", self.onDatasetStateChanged
        )
        self.eventSubscribe("DATASET_DELETED", self.refreshDependencyList)
        self.eventSubscribe("MODEL_DELETED", self.refreshDependencyList)

        self.dataTypeDependencies = []
        self.datasetDependencies = []
        self.modelDependencies = []
        self.dependencyList = []
        self.currentlyMissingKeys = []
        self.refreshWidgets = []

    allDatasets = False
    allModels = False
    parentName = None
    # updateKey = 0

    # def getUpdateKey(self):
    #     return self.updateKey

    def setDataDependencies(self, *args):
        self.dataTypeDependencies = []
        env = self.env

        if len(args) == 0:
            self.refreshDependencyList()
            return

        if isinstance(args[0], list):
            args = args[0]

        for key in args:
            if not env.hasDataType(key):
                logger.error(
                    f"Tried to set DataWatcher dependency with key `{key}`,"
                    + ", but this key has not been registered."
                )

            self.dataTypeDependencies.append(key)

        self.refreshDependencyList()

    def getDataDependencies(self):
        return self.dataTypeDependencies

    def setModelDependencies(self, *args, quiet=False):
        self.modelDependencies = []

        if len(args) == 0:
            self.refreshDependencyList()
            return

        if len(args) == 1:
            if args[0] == "all":
                self.allDatasets = True
                return
            else:
                self.allDatasets = False

            if isinstance(args[0], list):
                args = args[0]

        for key in args:
            self.modelDependencies.append(key)

        if not quiet:
            self.refreshDependencyList()

    def getModelDependencies(self):
        return self.modelDependencies

    def isDependentOn(self, key):
        return (key in self.getModelDependencies()) or (
            key in self.getDatasetDependencies()
        )

    def setModelDatasetDependencies(self, modelKeys, datasetKeys):
        self.setModelDependencies(*modelKeys, quiet=True)
        self.setDatasetDependencies(*datasetKeys)

    def setDatasetDependencies(self, *args, quiet=False):
        self.datasetDependencies = []

        if len(args) == 0:
            self.refreshDependencyList()
            return

        if len(args) == 1:
            if args[0] == "all":
                self.allDatasets = True
                return
            else:
                self.allDatasets = False

            if isinstance(args[0], list):
                args = args[0]

        for key in args:
            dataset = self.env.getDataset(key)
            if (dataset is None) or (not dataset.active):
                continue
            if dataset.isSubDataset and dataset.subName == self.parentName:
                continue
            self.datasetDependencies.append(key)

        if not quiet:
            self.refreshDependencyList()

    def getDatasetDependencies(self):
        return self.datasetDependencies

    def refreshDatasets(self):
        self.setDatasetDependencies(*self.datasetDependencies.copy())

    def refreshDependencyList(self, *args):
        # args because event

        self.dependencyList = []
        env = self.env

        if len(self.dataTypeDependencies) < 1 or (
            self.dataTypeDependencies[0] is None
        ):
            self.refresh()
            return

        datasetDependencies = (
            self.allDatasets
            and env.getAllDatasetKeys()
            or self.datasetDependencies
        )
        modelDependencies = (
            self.allModels and env.getAllModelKeys() or self.modelDependencies
        )

        for dataTypeKey in self.dataTypeDependencies:
            dataType = env.getRegisteredDataType(dataTypeKey)
            if dataType is None:
                continue

            mds = modelDependencies
            if not dataType.modelDependent:
                mds = [None]

            for modelKey in mds:
                model = env.getModel(modelKey)
                if (model is None) and dataType.modelDependent:
                    continue

                dds = datasetDependencies
                if not dataType.datasetDependent:
                    dds = [None]

                for datasetKey in dds:
                    dataset = env.getDataset(datasetKey)

                    if (dataset is None) and dataType.datasetDependent:
                        continue

                    key = dataType.getCacheKey(model=model, dataset=dataset)
                    self.dependencyList.append(key)

        self.refresh()

    def getMissingDependencies(self):
        missingKeys = []
        env = self.env

        for key in self.dependencyList:
            if not env.hasCacheKey(key):
                missingKeys.append(key)

        return missingKeys

    def addRefreshWidget(self, widget):
        self.refreshWidgets.append(widget)

    def refresh(self):
        missingKeys = self.getMissingDependencies()
        self.currentlyMissingKeys = missingKeys

        self.sendRefresh()

    def onDataUpdated(self, cacheKey):
        if cacheKey not in self.dependencyList:
            return

        (dataTypeKey, model, dataset) = self.env.cacheKeyToComponents(cacheKey)

        self.refresh()

    def onDatasetUpdated(self, key):
        if key not in self.datasetDependencies:
            return

        self.refresh()

    def onDatasetStateChanged(self, key):
        if key not in self.datasetDependencies:
            return

        self.refreshDatasets()

    def sendRefresh(self):
        for widget in self.refreshWidgets:
            self.eventPush("WIDGET_REFRESH", widget)

    def getWatchedData(self, dataOnly=False):
        env = self.env
        allData = []

        for key in self.dependencyList:
            if env.hasCacheKey(key):
                if dataOnly:
                    allData.append(env.getCacheByKey(key))
                else:
                    (dataTypeKey, model, dataset) = env.cacheKeyToComponents(
                        key
                    )

                    dataEntry = env.getCacheByKey(key)
                    entry = {
                        "key": dataTypeKey,
                        "model": model,
                        "dataset": dataset,
                        "dataEntry": dataEntry,
                    }

                    allData.append(entry)

        return allData

    def linkSelectionTo(self, dataWatcher):
        # links this dataWatcher to another
        # everytime the other dataWatcher gets updated, updates this one to the same values
        pass

    def loadContent(self):
        env = self.env
        deps = self.getMissingDependencies()
        for dep in deps:
            env.generationQueue.add(dep)
