from events import EventClass
from modelLoaders.loader import loadModel
from datasetLoaders.loader import loadDataset, SubDataset
from modelLoaders.ghost import GhostModelLoader
from tasks import TaskManager
from client.dataType import DataEntity
from Utils.misc import md5FromArraysAndStrings
from client.dataType import SubDataEntity
import logging
import os, glob
import numpy as np
import asyncio
from Utils.misc import loadModules, mixColors

logger = logging.getLogger("FFAST")


async def headlessEventLoop(env):
    taskManager = env.tm
    while not env.quitReady:
        await env.eventHandle()
        await env.handleGenerationQueue()
        await taskManager.eventHandle()
        await taskManager.handleTaskQueue()
        await asyncio.sleep(0.1)

    await env.eventHandle()
    await taskManager.eventHandle()


def runHeadless(func):
    # https://stackoverflow.com/questions/27480967/why-does-the-asyncios-event-loop-suppress-the-keyboardinterrupt-on-windows
    # Without it, it just gets stuck forever...
    # It's dirty but it's the only way it's worked so far
    import signal

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    async def funcWrapper(env):
        await func(env)
        env.quitReady = True

    loop = asyncio.get_event_loop()
    env = Environment()
    loadModules(None, env, headless=True)

    tasks = asyncio.gather(headlessEventLoop(env), funcWrapper(env))

    loop.run_until_complete(tasks)


class Environment(EventClass):
    """
    Environment class, responsible for loading and handling all datasets,
    models and saving intermediate and final data where necessary (e.g.
    model predictions, extra dataset descriptors).
    """

    

    def __init__(self, headless=True):
        super().__init__()
        self.headless = headless
        self.loadConfig()

        if headless:
            self.quitReady = False

        # Note: might have multiple environments at some point
        self.datasets = {}
        self.models = {}
        self.cache = {}
        self.dataTypes = {}
        self.tm = TaskManager()

        self.initialiseDataTypes()

        self.generationQueue = set()
        self.queuedTasks = set()

        # self.eventSubscribe("DATA_UPDATED", self.handleGenerationQueue)
        # self.eventSubscribe("GENERATION_QUEUE_CHANGED", self.handleGenerationQueue)
        self.eventSubscribe("TASK_CANCEL", self.onTaskCancel)
        self.eventSubscribe("TASK_DONE", self.onTaskDone)
        self.eventSubscribe(
            "SUBDATASET_INDICES_CHANGED", self.deleteCacheByDataset
        )

    def loadConfig(self):
        from config.userConfig import config

        self.userConfig = config

    def getConfig(self, key):
        return self.userConfig.get(key, None)

    def initialiseDataTypes(self):
        from client.dataType import EnergyPredictionData, ForcesPredictionData

        self.registerDataType(EnergyPredictionData)
        self.registerDataType(ForcesPredictionData)

    def hasDataType(self, dataTypeKey):
        return dataTypeKey in self.dataTypes

    def getDataType(self, dataTypeKey):
        return self.dataTypes.get(dataTypeKey, None)

    def registerDataType(self, dataType):
        """
        Adds a new data type to the known data types of the environment.

        Args:
            dataType (class): DataType class (not object!).
        """

        self.dataTypes[dataType.key] = dataType(self)

    def setNewModel(self, key, model):
        self.models[key] = model
        model.loaded = True
        self.eventPush("MODEL_LOADED", key)

    def getModel(self, key):
        return self.models.get(key, None)

    def modelExists(self, key):
        return key in self.models.keys()

    def getAllModelKeys(self):
        return list(self.models.keys())

    def getAllModels(self):
        return list(self.models.values())

    def taskLoadModel(self, path):
        self.newTask(
            self.loadModel,
            args=(path,),
            visual=True,
            name="Loading model",
            threaded=True,
        )

    def loadModel(self, path, taskID=None):
        """
        Asks the environment to load a model from a given path and save it at a
        newly generated key.

        Should be called as a threaded task.

        Args:
            path ([type]): path to the model
            taskID ([type], optional): [description]. Defaults to None.
        """
        model = loadModel(self, path)
        if model is None:
            logging.warn(f"Model `{path}` did not load successfully")
            return

        key = model.fingerprint
        self.setNewModel(key, model)
        logging.info(f"Model `{path}` successfully loaded")

    def deleteObject(self, key):
        if self.datasetExists(key):
            self.deleteDataset(key)
        elif self.modelExists(key):
            self.deleteModel(key)

    def deleteModel(self, key):
        model = self.getModel(key)
        if model is None:
            return

        model.onDelete()
        del self.models[key]
        logger.info(f"Model {key} deleted")
        self.eventPush("MODEL_DELETED", key)

    def deleteDataset(self, key):
        dataset = self.getDataset(key)
        if dataset is None:
            return

        dataset.onDelete()
        del self.datasets[key]
        logger.info(f"Dataset {key} deleted")
        self.eventPush("DATASET_DELETED", key)

    def setNewDataset(self, dataset):
        self.datasets[dataset.fingerprint] = dataset
        dataset.loaded = True
        self.eventPush("DATASET_LOADED", dataset.fingerprint)

    def getModelOrDataset(self, key):
        model = self.getModel(key)
        if model is None:
            return self.getDataset(key)
        else:
            return model

    def getDataset(self, key):
        return self.datasets.get(key, None)

    def getAllDatasetKeys(self):
        ds = self.getAllDatasets()
        return [x.fingerprint for x in ds]
        # return list(self.datasets.keys())

    def datasetExists(self, key):
        return key in self.datasets.keys()

    def getAllDatasets(self, subOnly=False, excludeSubs=False):
        ds = [x for x in self.datasets.values() if x.active]
        if subOnly:
            return [x for x in ds if x.isSubDataset]
        elif excludeSubs:
            return [x for x in ds if not x.isSubDataset]
        else:
            return ds

    def taskLoadDataset(self, path):
        self.newTask(
            self.loadDataset,
            args=(path,),
            visual=True,
            name="Loading dataset",
            threaded=True,
        )

    def loadDataset(self, path, taskID=None):
        """
        Asks the environment to load a dataset from a given path and save it at a newly generated key.

        Should be called as a threaded task.

        Args:
            path (str): path to dataset
            taskID (int, optional): [description]. Defaults to None.
        """

        dataset = loadDataset(path)
        if dataset is None:
            logging.warn(f"Dataset `{path}` did not load successfully")
            return

        key = dataset.fingerprint
        self.setNewDataset(dataset)
        logging.info(f"Dataset `{path}` successfully loaded")
        self.lookForGhosts()

    def declareSubDataset(self, parent, model, idx, subName):

        # check if already exists
        fp = SubDataset.getFingerprint(SubDataset, parent, model, subName)
        sub = self.getDataset(fp)

        # if doesnt exist yet
        if sub is None:  # and (idx is not None):
            sub = SubDataset(parent, model, idx, subName)
            sub.initialise()
            self.setNewDataset(sub)
        # elif sub is None:
        #     pass
        # elif idx is None:
        #     sub.setActive(False)
        else:
            sub.setIndices(idx)
            sub.setActive(True)

    def newTask(self, *args, **kwargs):
        """See newTask method of TaskManager class."""
        return self.tm.queueTask(*args, **kwargs)

    def getTask(self, *args, **kwargs):
        return self.tm.getTask(*args, **kwargs)

    def taskGenerateDataByKey(self, key, **kwargs):
        (dataTypeKey, model, dataset) = self.cacheKeyToComponents(key)
        self.taskGenerateData(
            dataTypeKey, model=model, dataset=dataset, **kwargs
        )

    def taskGenerateData(
        self,
        dataTypeKey,
        model=None,
        dataset=None,
        threaded=True,
        visual=False,
        isComponent=False,
        componentParent=None,
    ):
        # for models that predict energies and forces at the same time (e.g. sGDML)
        # convert force tasks to energy tasks to avoid duplicates
        if (
            (model is not None)
            and (model.singlePredict)
            and (dataTypeKey == "forces")
        ):
            dataTypeKey = "energy"

        dataKey = self.getCacheKey(dataTypeKey, model=model, dataset=dataset)

        if self.hasCacheKey(dataKey):
            return

        if dataKey in self.queuedTasks:
            # even if the job is not running, it's possible it was generated already
            # in that case, don't
            return

        self.queuedTasks.add(dataKey)

        func = (threaded and self.generateData) or self.generateDataAsync
        self.newTask(
            func,
            args=(dataTypeKey,),
            kwargs={
                "model": model,
                "dataset": dataset,
                "isComponent": isComponent,
            },
            threaded=threaded,
            visual=visual,
            name=f"Generating {dataTypeKey}",
            taskKey=f"{dataKey}",
            componentParent=componentParent,
        )

    def onTaskCancel(self, taskID):
        task = self.tm.getTask(taskID)

        if task["componentParent"] is not None:
            queue = self.generationQueue
            cacheKey = task["componentParent"]

            if cacheKey in queue:
                queue.discard(cacheKey)

            logger.info(
                f"Removed {cacheKey} from data generation queue because child task got cancelled."
            )

    def onTaskDone(self, taskID):
        if taskID in self.queuedTasks:
            self.queuedTasks.remove(taskID)

    async def generateDataAsync(self, *args, **kwargs):
        self.generateData(*args, **kwargs)

    def canGenerateData(self, dataTypeKey, model=None, dataset=None):
        dataType = self.getDataType(dataTypeKey)
        (deps, canGenerate) = dataType.checkDependencies(
            model=model, dataset=dataset
        )

        return canGenerate

    def generateData(
        self,
        dataTypeKey,
        model=None,
        dataset=None,
        isComponent=False,
        taskID=None,
    ):
        dataType = self.getDataType(dataTypeKey)

        if dataType is None:
            logger.error(
                f"Tried to generate data for dataTypeKey {dataTypeKey}, "
                + "but no such key was registered"
            )
            return None

        cacheKey = dataType.getCacheKey(model=model, dataset=dataset)

        sModel, sDataset = "None", "None"
        if model is not None:
            sModel = model.getDisplayName()
        if dataset is not None:
            sDataset = dataset.getDisplayName()
        logger.info(
            f"Generating data for key {cacheKey}, model = {sModel}, dataset = {sDataset}"
        )

        generated = dataType.generateData(
            model=model, dataset=dataset, taskID=taskID
        )

        if (taskID is not None) and (not self.tm.isTaskRunning(taskID)):
            # check if the task was cancelled, in which case it's normal it
            # failed to generate, thus skip the generation queue
            # in principle this should be unnecessary since cancelling means
            # this function is no longer directly awaited, but better safe
            # than sorry
            return

        if (not generated) and (not isComponent):
            self.generationQueue.add(cacheKey)
            logger.info(f"Added {cacheKey} to generation queue")
            self.eventPush("GENERATION_QUEUE_CHANGED")

    def keyIsHaunted(self, dataTypeKey, model=None, dataset=None):
        if not model.isGhost:
            return False

        compKeys = self.getLowestComponents(
            dataTypeKey, model=model, dataset=dataset
        )

        for key in compKeys:
            (dataTypeKey, _, _) = self.cacheKeyToComponents(key)
            if (dataTypeKey == "energy") or (dataTypeKey == "forces"):
                return True

        return False

    def addToGenerationQueue(self, key, dataset=None, model=None):
        dataType = self.getDataType(key)
        cacheKey = dataType.getCacheKey(model=model, dataset=dataset)
        self.generationQueue.add(cacheKey)
        if self.headless:
            print(f"Added {cacheKey} to generation queue", flush=True)

    def getKeyFromPath(self, path):
        # check dataset
        for dataset in self.getAllDatasets(excludeSubs=True):
            if dataset.path == path:
                return dataset.fingerprint

        for model in self.getAllModels():
            if model.path == path:
                return model.fingerprint

        return None

    async def handleGenerationQueue(self, *args):
        queue = self.generationQueue

        if len(queue) == 0:
            return

        logger.info(f"Handling generation queue {self.generationQueue}")

        # copying because we discard in loop
        keysToGenerate = {}
        for cacheKey in queue.copy():
            (dataTypeKey, model, dataset) = self.cacheKeyToComponents(cacheKey)

            if self.hasCacheKey(cacheKey):
                continue

            if self.canGenerateData(dataTypeKey, model=model, dataset=dataset):
                keysToGenerate[
                    cacheKey
                ] = None  # value is the parent key, if available
                queue.discard(cacheKey)

            elif self.keyIsHaunted(dataTypeKey, model=model, dataset=dataset):
                keysToGenerate[cacheKey] = None
                queue.discard(cacheKey)

            else:
                compKeys = self.getLowestComponents(
                    dataTypeKey, model=model, dataset=dataset
                )

                for key in compKeys:
                    if key not in keysToGenerate:
                        keysToGenerate[
                            key
                        ] = cacheKey  # indicates the parent key

        for key, parentKey in keysToGenerate.items():
            (dataTypeKey, model, dataset) = self.cacheKeyToComponents(key)

            self.taskGenerateData(
                dataTypeKey,
                model=model,
                dataset=dataset,
                visual=True,
                threaded=True,
                isComponent=parentKey is not None,
                componentParent=parentKey,
            )

    def getLowestComponents(self, dataTypeKey, model=None, dataset=None):
        dataType = self.getDataType(dataTypeKey)
        compKeys = dataType.getGeneratableComponent(
            model=model, dataset=dataset
        )

        return [
            self.getCacheKey(key, model=model, dataset=dataset)
            for key in compKeys
        ]

    def getData(self, dataTypeKey, model=None, dataset=None):
        dataType = self.getRegisteredDataType(dataTypeKey)

        if dataType is None:
            logger.error(
                f"Tried to get data for dataTypeKey {dataTypeKey}, "
                + "but no such key was registered"
            )
            return None

        cacheKey = dataType.getCacheKey(model=model, dataset=dataset)
        if (
            (dataset is not None)
            and (dataset.isSubDataset)
            and dataType.iterable
            and not self.hasCacheKey(cacheKey, subChecks=False)
        ):
            cacheKey = dataType.getCacheKey(
                model=model, dataset=dataset.parent
            )
            data = self.cache.get(cacheKey, None)
            if data is not None:
                data = data.getSubEntity(indices=dataset.indices)
        else:
            data = self.cache.get(cacheKey, None)

        return data

    def setData(self, dataEntity, dataTypeKey, model=None, dataset=None):
        dataType = self.getRegisteredDataType(dataTypeKey)

        if dataType is None:
            logger.error(
                f"Tried to set data for dataTypeKey {dataTypeKey}, "
                + "but no such key was registered"
            )
            return None

        cacheKey = dataType.getCacheKey(model=model, dataset=dataset)

        self.cache[cacheKey] = dataEntity
        logger.info(f"Data for key {cacheKey} set, {self.cache[cacheKey]}")
        self.eventPush("DATA_UPDATED", cacheKey)

    def getCacheKey(self, dataTypeKey, model=None, dataset=None):
        dataType = self.getRegisteredDataType(dataTypeKey)
        if dataType is None:
            return None

        cacheKey = dataType.getCacheKey(model=model, dataset=dataset)

        return cacheKey

    def getRegisteredDataType(self, dataTypeKey):
        return self.dataTypes.get(dataTypeKey, None)

    def deleteCacheByDataset(self, datasetKey):
        toDelete = []
        for key in self.cache.keys():
            if datasetKey in key:
                toDelete.append(key)

        for key in toDelete:
            del self.cache[key]
            self.eventPush("DATA_UPDATED", key)

    def hasCacheKey(self, key, subChecks=True):
        if subChecks:
            (dataTypeKey, model, dataset) = self.cacheKeyToComponents(key)
            return self.hasData(dataTypeKey, model=model, dataset=dataset)
        else:
            return key in self.cache

    def hasData(self, dataTypeKey, model=None, dataset=None):
        cacheKey = self.getCacheKey(dataTypeKey, model=model, dataset=dataset)
        hasKey = self.hasCacheKey(cacheKey, subChecks=False)
        if (dataset is not None) and (dataset.isSubDataset):
            dataType = self.getDataType(dataTypeKey)
            if (not hasKey) and dataType.iterable:
                return self.hasData(
                    dataTypeKey, model=model, dataset=dataset.parent
                )
        return hasKey

    def getCacheByKey(self, key, subChecks=True):
        if subChecks:
            (dataTypeKey, model, dataset) = self.cacheKeyToComponents(key)
            return self.getData(dataTypeKey, model=model, dataset=dataset)
        else:
            return self.cache.get(key, None)

    def cacheKeyToComponents(self, key):
        spl = key.split("__")
        dataTypeKey = spl[0]

        if spl[1] == "nil":
            model = None
        else:
            model = self.getModel(spl[1])

        if spl[2] == "nil":
            dataset = None
        else:
            dataset = self.getDataset(spl[2])

        return (dataTypeKey, model, dataset)

    def save(self, path, taskID=None):
        if not os.path.exists(path):
            os.mkdir(path)

        ## SAVE CACHE
        cacheDir = os.path.join(path, "cache")
        if not os.path.exists(cacheDir):
            os.mkdir(cacheDir)

        for key, entity in self.cache.items():
            if isinstance(entity, SubDataEntity):
                continue

            np.savez_compressed(
                os.path.join(cacheDir, key),
                entityDataTypeKey=entity.dataType.key,
                cacheKey=key,
                **entity.data,
            )

    def taskLoad(self, path):
        self.newTask(
            self.load,
            args=(path,),
            visual=True,
            name="Loading dataset",
            threaded=True,
        )

    def load(self, path, taskID=None):
        ## LOAD CACHE
        cacheDir = os.path.join(path, "cache")
        for path in glob.glob(os.path.join(cacheDir, "*.npz")):
            d = dict(np.load(path, allow_pickle=True))
            dataTypeKey = str(d.pop("entityDataTypeKey"))
            cacheKey = str(d.pop("cacheKey"))
            dataType = self.getDataType(dataTypeKey)

            if dataType is None:
                raise ValueError(
                    f"Tried to load data of type `{dataTypeKey}`, but no such type registered."
                )

            de = dataType.newDataEntity(**d)
            self.cache[cacheKey] = de
            self.eventPush("DATA_UPDATED", cacheKey)

        self.lookForGhosts()

    def lookForGhosts(self):
        for cacheKey in self.cache.keys():
            (dataKey, modelKey, datasetKey) = cacheKey.split("__")

            if (
                (dataKey == "forces" or dataKey == "energy")
                and (modelKey not in self.models)
                and self.datasetExists(datasetKey)
            ):
                model = GhostModelLoader(self, modelKey)
                model.initialise()
                self.setNewModel(modelKey, model)

        print("DONE LOOKING FOR GHOSTS")

    def loadPrepredictedDataset(self, path, datasetKey):
        d = np.load(path, allow_pickle=True)
        E, F = d["E"], d["F"]

        dataset = self.getDataset(datasetKey)
        eDataset = dataset.getEnergies()
        if E.shape != eDataset.shape:
            logger.error(
                f"Shape mismatch when loading prepredicted model. Model energy shape: {E.shape}, dataset energy shape: {eDataset.shape}"
            )

        modelKey = md5FromArraysAndStrings(E, F)

        energyDataType = self.getDataType("energy")
        energyDataEntity = energyDataType.newDataEntity(energy=E)
        self.setData(
            energyDataEntity, "energy", model=modelKey, dataset=dataset
        )

        forcesDataType = self.getDataType("forces")
        forcesDataEntity = forcesDataType.newDataEntity(forces=F)
        self.setData(
            forcesDataEntity, "forces", model=modelKey, dataset=dataset
        )

        self.lookForGhosts()

    async def waitForTasks(self, verbose=False, dt=1):
        tm = self.tm
        while (
            (tm.taskQueue.qsize() > 0)
            or (len(tm.runningTasks) > 0)
            or (len(self.generationQueue) > 0)
        ) and not self.quitReady:
            if verbose:
                print("-" * 20)
                lTaskQueue = tm.taskQueue.qsize()
                if lTaskQueue > 0:
                    print(f"{lTaskQueue} tasks queued.\n")

                lRunningTasks = len(tm.runningTasks)
                if lRunningTasks > 0:
                    print(f"{lRunningTasks} tasks running:")
                    for taskID in tm.runningTasks:
                        task = tm.getTask(taskID)
                        prog = "?%"
                        if task["progress"] is not None:
                            prog = f'{task["progress"]*100:.0f}%'

                        print(
                            f'{prog:<4} {task["name"]:<20}  {task["progressMessage"]}'
                        )
                    print()

                lGenQueue = len(self.generationQueue)
                if lGenQueue > 0:
                    print(f"{lGenQueue} tasks in generation queue:")
                    for i in self.generationQueue:
                        print(i)

                print(flush=True)

            await asyncio.sleep(dt)

    def getColorMix(self, dataset=None, model=None):
        if dataset is None and model is None:
            return (255, 255, 255)
        elif dataset is None:
            return model.color
        elif model is None:
            return dataset.color
        else:
            return mixColors(model.color, dataset.color)
