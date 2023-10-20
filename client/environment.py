from events import EventClass
from loaders.datasetLoader import (
    SubDataset,
    FrozenSubDataset,
    AtomFilteredDataset,
)
from loaders.modelGhost import GhostModelLoader
from loaders.zeroModel import ZeroModelLoader
from tasks import TaskManager
from client.dataType import DataEntity
from utils import md5FromArraysAndStrings
from client.dataType import SubDataEntity
import logging
import os, glob
import numpy as np
import asyncio
from utils import loadModules, mixColors
import json
import threading, time

logger = logging.getLogger("FFAST")


class Environment(EventClass):
    """
    Environment class, responsible for loading and handling all datasets,
    models and saving intermediate and final data where necessary (e.g.
    model predictions, extra dataset descriptors).
    """

    def __init__(self, headless=True):
        super().__init__()
        self.headless = headless

        if headless:
            self.quitReady = False

        # Note: might have multiple environments at some point
        self.datasets = {}
        self.models = {}
        self.cache = {}
        self.dataTypes = {}
        self.modelTypes = {}
        self.datasetTypes = {}
        self.info = {}
        self.tm = TaskManager()

        self.initialiseDataTypes()

        self.generationQueue = set()
        self.queuedTasks = set()

        # self.eventSubscribe("DATA_UPDATED", self.handleGenerationQueue)
        # self.eventSubscribe("GENERATION_QUEUE_CHANGED", self.handleGenerationQueue)
        self.eventSubscribe("TASK_CANCEL", self.onTaskCancel)
        self.eventSubscribe("TASK_FAILED", self.onTaskFailed)
        self.eventSubscribe("TASK_DONE", self.onTaskDone)
        self.eventSubscribe(
            "SUBDATASET_INDICES_CHANGED", self.deleteCacheByDataset
        )

    #############
    ## DATA TYPES
    #############

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

    def getRegisteredDataType(self, dataTypeKey):
        return self.dataTypes.get(dataTypeKey, None)

    #############
    ## MODELS
    #############

    def initialiseModelType(self, modelType):
        self.modelTypes[modelType.modelName] = modelType

    def setNewModel(self, model):
        self.models[model.fingerprint] = model
        model.loaded = True
        self.eventPush("MODEL_LOADED", model.fingerprint)

    def getModel(self, key):
        return self.models.get(key, None)

    def getModelFromPath(self, path):
        return self.getModel(self.getKeyFromPath(path))

    def deleteModel(self, key):
        model = self.getModel(key)
        if model is None:
            return

        model.onDelete()
        del self.models[key]
        logger.info(f"Model {key} deleted")
        self.eventPush("MODEL_DELETED", key)

    def modelExists(self, key):
        return key in self.models.keys()

    def datasetExists(self, key):
        return key in self.datasets.keys()

    def getAllModelKeys(self):
        return list(self.models.keys())

    def getAllModels(self, excludeGhosts=False):
        if excludeGhosts:
            return [m for m in self.models.values() if not m.isGhost]
        else:
            return list(self.models.values())

    def taskLoadModel(self, path, modelType):
        self.newTask(
            self.loadModel,
            args=(path, modelType),
            visual=True,
            name="Loading model",
            threaded=True,
        )

    def loadModel(self, path, modelType, taskID=None):
        if not os.path.exists(path):
            logger.error(f"Tried to load dataset, but path `{path}` not found")
            return None

        if modelType not in self.modelTypes:
            logger.error(
                f"Tried to load dataset, but dataset type {modelType} not recognised"
            )
            return None

        model = self.modelTypes[modelType](self, path)
        if model is None:
            logging.warn(f"Model `{path}` did not load successfully")
            return
        model.initialise()

        self.setNewModel(model)
        logging.info(f"Model `{path}` successfully loaded")

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
        energyDataEntity = energyDataType.newDataEntity(energy=E.flatten())
        self.setData(
            energyDataEntity, "energy", model=modelKey, dataset=dataset
        )

        forcesDataType = self.getDataType("forces")
        forcesDataEntity = forcesDataType.newDataEntity(forces=F)
        self.setData(
            forcesDataEntity, "forces", model=modelKey, dataset=dataset
        )

        # update info with the path etc
        self.info.update(
            {
                "objects": {
                    modelKey: {"path": path, "name": os.path.basename(path)}
                }
            }
        )

        self.lookForGhosts()

    #############
    ## DATASETS
    #############

    def initialiseDatasetType(self, datasetType):
        self.datasetTypes[datasetType.datasetName] = datasetType

    def setNewDataset(self, dataset):
        self.datasets[dataset.fingerprint] = dataset
        dataset.loaded = True
        self.eventPush("DATASET_LOADED", dataset.fingerprint)

    def getDataset(self, key):
        return self.datasets.get(key, None)

    def getDatasetFromPath(self, path):
        return self.getDataset(self.getKeyFromPath(path))

    def deleteDataset(self, key):
        dataset = self.getDataset(key)
        if dataset is None:
            return

        dataset.onDelete()
        del self.datasets[key]
        logger.info(f"Dataset {key} deleted")
        self.eventPush("DATASET_DELETED", key)

    def getAllDatasetKeys(self):
        ds = self.getAllDatasets()
        return [x.fingerprint for x in ds]
        # return list(self.datasets.keys())

    def getAllDatasets(self, subOnly=False, excludeSubs=False):
        ds = [x for x in self.datasets.values() if x.active]
        if subOnly:
            return [x for x in ds if x.isSubDataset]
        elif excludeSubs:
            return [x for x in ds if not x.isSubDataset]
        else:
            return ds

    def taskLoadDataset(self, path, datasetType):
        self.newTask(
            self.loadDataset,
            args=(path, datasetType),
            visual=True,
            name="Loading dataset",
            threaded=True,
        )

    def loadDataset(self, path, datasetType, taskID=None):
        if not os.path.exists(path):
            logger.error(f"Tried to load dataset, but path `{path}` not found")
            return None

        if datasetType not in self.datasetTypes:
            logger.error(
                f"Tried to load dataset, but dataset type {datasetType} not recognised"
            )
            return None

        dataset = self.datasetTypes[datasetType](path)
        if dataset is None:
            logging.warn(f"Dataset `{path}` did not load successfully")
            return
        dataset.initialise()

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

    def freezeSubDataset(self, fingerprint):
        dataset = self.getDataset(fingerprint)
        if (dataset is None) or (not dataset.isSubDataset):
            return

        fp = FrozenSubDataset.getFingerprint(
            FrozenSubDataset,
            parent=dataset.parent,
            model=dataset.modelDep,
            indices=dataset.indices,
            subName=dataset.subName,
        )
        if self.getDataset(fp) is not None:
            return

        sub = FrozenSubDataset(
            dataset.parent, dataset.modelDep, dataset.indices, dataset.subName
        )
        sub.initialise()
        self.setNewDataset(sub)

    def createAtomFilteredDataset(self, dataset, idxs):
        fp = AtomFilteredDataset.getFingerprint(
            AtomFilteredDataset, dataset, idxs
        )
        sub = self.getDataset(fp)

        if sub is not None:
            return

        sub = AtomFilteredDataset(dataset, idxs)
        sub.initialise()
        self.setNewDataset(sub)

    #############
    ## OBJECTS (MODELS & DATASETS)
    #############

    def getModelOrDataset(self, key):
        model = self.getModel(key)
        if model is None:
            return self.getDataset(key)
        else:
            return model

    def getObject(self, *args):
        return self.getModelOrDataset(*args)

    def getKeyFromPath(self, path):
        # check dataset
        for dataset in self.getAllDatasets(excludeSubs=True):
            if dataset.path == path:
                return dataset.fingerprint

        for model in self.getAllModels():
            if model.path == path:
                return model.fingerprint

        return None

    def deleteObject(self, key):
        if self.datasetExists(key):
            self.deleteDataset(key)
        elif self.modelExists(key):
            self.deleteModel(key)

    #############
    ## TASKS
    #############

    def newTask(self, *args, **kwargs):
        """See newTask method of TaskManager class."""
        return self.tm.queueTask(*args, **kwargs)

    def getTask(self, *args, **kwargs):
        return self.tm.getTask(*args, **kwargs)

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

    def onTaskFailed(self, taskID):
        self.onTaskCancel(taskID)

    def onTaskDone(self, taskID):
        if taskID in self.queuedTasks:
            self.queuedTasks.remove(taskID)

        # if the task was also in the generation queue, that means it crashed
        #  gotta remove it then
        if taskID in self.generationQueue:
            self.generationQueue.discard(taskID)

    #############
    ## DATA
    #############

    def getData(self, dataTypeKey, model=None, dataset=None):
        dataType = self.getRegisteredDataType(dataTypeKey)

        if dataType is None:
            logger.error(
                f"Tried to get data for dataTypeKey {dataTypeKey}, "
                + "but no such key was registered"
            )
            return None

        cacheKey = dataType.getCacheKey(model=model, dataset=dataset)

        if type(model) == str:
            obj = self.getObject(model)
            if obj is None:
                logger.error(
                    f"In env.getData, tried to get model for key {model} but no model found"
                )
            model = obj

        if type(dataset) == str:
            obj = self.getObject(dataset)
            if obj is None:
                logger.error(
                    f"In env.getData, tried to get dataset for key {dataset} but no dataset found"
                )
            dataset = obj

        ## SUBDATSETS
        if (
            (dataset is not None)
            and (dataset.isSubDataset)
            and not self.hasCacheKey(cacheKey, subChecks=False)
        ):
            ## ATOM FILTERED
            if dataset.isAtomFiltered:
                if dataType.atomFilterable:
                    data = self.getData(
                        dataTypeKey, model=model, dataset=dataset.parent
                    )
                    if data is not None:
                        return data.getAtomFilteredEntity(
                            indices=dataset.indices
                        )

                if dataType.atomConstant:
                    return self.getData(
                        dataTypeKey, model=model, dataset=dataset.parent
                    )

            elif dataType.iterable:
                data = self.getData(
                    dataTypeKey, model=model, dataset=dataset.parent
                )
                if data is not None:
                    return data.getSubEntity(indices=dataset.indices)

        return self.cache.get(cacheKey, None)

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

    def hasCacheKey(self, key, subChecks=True):
        if key is None:
            logger.error("Called env.hasCacheKey(key) but key was None!")
            return False
        if subChecks:
            (dataTypeKey, model, dataset) = self.cacheKeyToComponents(key)
            return self.hasData(dataTypeKey, model=model, dataset=dataset)
        else:
            return key in self.cache

    def hasData(self, dataTypeKey, model=None, dataset=None):
        cacheKey = self.getCacheKey(dataTypeKey, model=model, dataset=dataset)
        hasKey = self.hasCacheKey(cacheKey, subChecks=False)

        if hasKey:
            return True

        if (dataset is not None) and (dataset.isSubDataset):
            dataType = self.getDataType(dataTypeKey)

            if dataset.isAtomFiltered:
                if dataType.atomFilterable or dataType.atomConstant:
                    return self.hasData(
                        dataTypeKey, model=model, dataset=dataset.parent
                    )

            elif dataType.iterable:
                return self.hasData(
                    dataTypeKey, model=model, dataset=dataset.parent
                )

        return False

    #############
    ## DATA GENERATION
    #############

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
        if (model is not None) and (not model.isGhost):
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
                queue.discard(cacheKey)
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

        return compKeys
        # return [
        #     self.getCacheKey(key, model=model, dataset=dataset)
        #     for key in compKeys
        # ]

    def deleteCacheByDataset(self, datasetKey):
        toDelete = []
        for key in self.cache.keys():
            if datasetKey in key:
                toDelete.append(key)

        for key in toDelete:
            del self.cache[key]
            self.eventPush("DATA_UPDATED", key)

    def getCacheByKey(self, key, subChecks=True):
        if subChecks:
            (dataTypeKey, model, dataset) = self.cacheKeyToComponents(key)
            return self.getData(dataTypeKey, model=model, dataset=dataset)
        else:
            return self.cache.get(key, None)

    def cacheKeyToComponents(self, key, dataTypeObject=False):
        spl = key.split("__")
        dataTypeKey = spl[0]
        if dataTypeObject:
            dataType = self.getDataType(dataTypeKey)
        else:
            dataType = dataTypeKey

        if spl[1] == "nil":
            model = None
        else:
            model = self.getModel(spl[1])

        if spl[2] == "nil":
            dataset = None
        else:
            dataset = self.getDataset(spl[2])

        return (dataType, model, dataset)

    #############
    ## SAVE/LOAD
    #############

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

        ## GENERATE INFO
        info = {"objects": {}}
        objects = self.getAllDatasets(excludeSubs=True) + self.getAllModels()
        for o in objects:
            info["objects"][o.fingerprint] = {
                "name": o.getName(),
                "path": o.path,
            }

        # dataset/model names and paths

        ## SAVE INFO
        infoFile = os.path.join(path, "info.json")
        with open(infoFile, "w") as f:
            json.dump(info, f, indent=4)

    def taskLoad(self, path):
        self.newTask(
            self.load,
            args=(path,),
            visual=True,
            name="Loading save",
            threaded=True,
        )

    def load(self, path, taskID=None):
        # LOAD INFO (names etc)
        infoFile = os.path.join(path, "info.json")
        if os.path.exists(infoFile):
            with open(infoFile, "r") as f:
                info = json.load(f)
            self.loadInfo(info)

        ## LOAD CACHE
        cacheDir = os.path.join(path, "cache")
        for npzPath in glob.glob(os.path.join(cacheDir, "*.npz")):
            d = dict(np.load(npzPath, allow_pickle=True))
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

    def loadInfo(self, info):
        self.info.update(info)

    def saveDataset(self, dataset, datasetType, form, path, taskID=None):
        self.eventPush(
            "TASK_PROGRESS",
            taskID,
            message=f"Saving {dataset.getDisplayName()} as {datasetType} dataset at z`{path}`",
            quiet=True,
            percent=False,
        )

        datasetClass = self.datasetTypes.get(datasetType, None)
        if datasetClass is None:
            logger.error(
                f"Tried saving dataset {dataset.getDisplayName()} as {datasetType} dataset, but type is not recognised"
            )
            return

        if not hasattr(datasetClass, "saveDataset"):
            logger.error(
                f"Tried saving dataset {dataset.getDisplayName()} as {datasetType} dataset, but no saveDataset method defined"
            )
            return

        datasetClass.saveDataset(dataset, path, format=form, taskID=taskID)

    def taskSaveDataset(self, dataset, datasetType, form, path):
        self.newTask(
            self.saveDataset,
            args=(dataset, datasetType, form, path),
            visual=True,
            name="Saving dataset",
            threaded=True,
        )

    #############
    ## MISC
    #############

    def getColorMix(self, dataset=None, model=None):
        if dataset is None and model is None:
            return (255, 255, 255)
        elif dataset is None:
            return model.color
        elif model is None:
            return dataset.color
        else:
            return mixColors(model.color, dataset.color)

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
                self.setNewModel(model)

    def loadZeroModel(self):
        fp = ZeroModelLoader.fingerprint
        if self.modelExists(fp):
            return
        model = ZeroModelLoader(self)
        model.initialise()
        self.setNewModel(model)

    def startInteract(self, **kwargs):
        import code

        code.interact(local=kwargs)


class HeadlessEnvironment(Environment, threading.Thread):
    def __init__(self):
        Environment.__init__(self, headless=True)
        threading.Thread.__init__(self)
        self.loop = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.headlessEventLoop())

    async def headlessEventLoop(self):
        taskManager = self.tm
        while not self.quitReady:
            await self.eventHandle()
            await self.handleGenerationQueue()
            await taskManager.eventHandle()
            await taskManager.handleTaskQueue()
            await asyncio.sleep(0.1)

        await self.eventHandle()
        await taskManager.eventHandle()

    def headlessQuit(self):
        self.quitReady = True

    def waitForTasks(self, verbose=False, dt=5):
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

            time.sleep(dt)


def startHeadlessEnvironment():
    from utils import setupLogger

    thread = HeadlessEnvironment()
    setupLogger()

    loadModules(None, thread, headless=True)
    thread.start()

    return thread
