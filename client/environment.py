import ase.io.formats
from ase.calculators.calculator import PropertyNotImplementedError
from ase.io.trajectory import Trajectory
from events import EventClass
from datasetLoaders.loader import (
    SubDataset,
    FrozenSubDataset,
    AtomFilteredDataset,
)
from modelLoaders.ghost import GhostModelLoader
from modelLoaders.zeroModel import ZeroModelLoader
from tasks import TaskManager
from client.dataType import DataEntity, AtomsList
from utils import md5FromArraysAndStrings
from client.dataType import SubDataEntity
import logging
import os, glob
import numpy as np
import asyncio
from utils import loadModules, mixColors
import json
import threading, time
from modules.aseDataset import aseDatasetLoader

logger = logging.getLogger("FFAST")


class Environment(EventClass):
    """
    Environment class, responsible for loading and handling all datasets,
    models and saving intermediate and final data where necessary (e.g.
    model predictions, extra dataset descriptors).
    """

    def __init__(self, headless=True):
        """Build the session registries, caches, and event wiring for one environment."""
        super().__init__()
        self.headless = headless

        if headless:
            self.quitReady = False

        # Note: might have multiple environments at some point
        self.datasets = {}
        self.dataset_slice_numbers = {}
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
        self.eventSubscribe(
            "QUIT_EVENT", self._disconnectRemoteSession, asynchronous=True
        )

        # Active remote cluster session (set by menuHandler after connect_to_cluster)
        self.remoteSession = None

        # Subscribe to remote dataset metadata so we can create local proxies
        self.eventSubscribe("REMOTE_DATASET_META", self._onRemoteDatasetMeta)
        # Subscribe to remote ghost-model metadata (fired after predictions load)
        self.eventSubscribe("REMOTE_MODEL_META", self._onRemoteModelMeta)

        self.maxDatasetSize = 0  # To handle the smoothing maximum value in plots

    #############
    ## DATA TYPES
    #############

    def initialiseDataTypes(self):
        """Register the built-in prediction data types that other modules depend on."""
        from client.dataType import EnergyPredictionData, ForcesPredictionData

        self.registerDataType(EnergyPredictionData)
        self.registerDataType(ForcesPredictionData)

    def hasDataType(self, dataTypeKey):
        """Provide a cheap existence check before code asks for a data type."""
        return dataTypeKey in self.dataTypes

    def getDataType(self, dataTypeKey):
        """Resolve the live data-type instance used for generation and dependency checks."""
        return self.dataTypes.get(dataTypeKey, None)

    def registerDataType(self, dataType):
        """
        Adds a new data type to the known data types of the environment.

        Args:
            dataType (class): DataType class (not object!).
        """

        self.dataTypes[dataType.key] = dataType(self)

    def getRegisteredDataType(self, dataTypeKey):
        """Keep the older accessor name for callers that still use it."""
        return self.dataTypes.get(dataTypeKey, None)

    #############
    ## MODELS
    #############

    def initialiseModelType(self, modelType):
        """Register a model loader class discovered during module loading."""
        self.modelTypes[modelType.modelName] = modelType

    def setNewModel(self, model):
        """Mark a model as available in the session and notify listeners."""
        self.models[model.fingerprint] = model
        model.loaded = True
        self.eventPush("MODEL_LOADED", model.fingerprint)

    def getModel(self, key):
        """Fetch a loaded model by fingerprint."""
        return self.models.get(key, None)

    def getModelFromPath(self, path):
        """Resolve a loaded model through its source path."""
        return self.getModel(self.getKeyFromPath(path))

    def deleteModel(self, key):
        """Remove a model and invalidate every cached artifact produced by it."""
        model = self.getModel(key)
        if model is None:
            return

        # Clean up all cached data for this model before deleting it
        # Cache keys are in format: "dataTypeKey__modelFingerprint__datasetFingerprint"
        cache_keys_to_delete = []
        for cache_key in self.cache.keys():
            parts = cache_key.split("__")
            if len(parts) == 3 and parts[1] == key:
                cache_keys_to_delete.append(cache_key)

        # Delete all cached data for this model
        for cache_key in cache_keys_to_delete:
            del self.cache[cache_key]
            logger.info(f"Deleted cached data: {cache_key}")

        model.onDelete()
        del self.models[key]
        logger.info(f"Model {key} deleted")
        self.eventPush("MODEL_DELETED", key)

    def modelExists(self, key):
        """Support quick guard checks before model-specific work."""
        return key in self.models.keys()

    def datasetExists(self, key):
        """Support quick guard checks before dataset-specific work."""
        return key in self.datasets.keys()

    def getAllModelKeys(self):
        """Expose model fingerprints to UI and persistence code."""
        return list(self.models.keys())

    def getAllModels(self, excludeGhosts=False):
        """Return live models, optionally hiding ghost placeholders from callers."""
        if excludeGhosts:
            return [m for m in self.models.values() if not m.isGhost]
        else:
            return list(self.models.values())

    def taskLoadModel(self, path, modelType):
        """Queue model loading so disk I/O and setup do not block the main loop."""
        self.newTask(
            self.loadModel,
            args=(path, modelType),
            visual=True,
            name="Loading model",
            threaded=True,
        )

    def loadModel(self, path, modelType, taskID=None):
        """Validate and instantiate a concrete model from disk."""
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

    def taskLoadPrepredictedDataset(self, path, datasetKey, selected_energy_key=None, selected_force_key=None):
        """Queue import of external predictions as cached model outputs for a dataset."""
        self.newTask(
            self.loadPrepredictedDataset,
            args=(path, datasetKey),
            kwargs={
                'selected_energy_key': selected_energy_key,
                'selected_force_key': selected_force_key
            },
            visual=True,
            name="Loading prepredicted dataset",
            threaded=True,
        )

    def loadPrepredictedDataset(self, path, datasetKey, taskID=None, selected_energy_key=None, selected_force_key=None):
        """Attach precomputed energies and forces to a dataset as a ghost model."""
        if "npz" in path:
            d = np.load(path, allow_pickle=True)
            E, F = d["E"], d["F"]
        else:
            # Use smart loader to detect uniform vs variable datasets
            import ase.io
            from modules.aseDataset import aseDatasetLoader, VariableASEDatasetLoader
            def check_homogeneity(atoms_list):
                for i in range(20):
                    temp_atoms_list = []
                    for j in np.random.choice(len(atoms_list), size=3, replace=False):
                        temp_atoms_list.append(atoms_list[j].get_chemical_formula())
                    if len(set(temp_atoms_list)) != 1:
                        return False

                return True

            # Read once to detect type
            slice_num = self.dataset_slice_numbers.get(datasetKey)
            if slice_num is not None and slice_num > 0:
                logger.info(f"Loading dataset with slice number of: {slice_num}")
                atomsList = ase.io.read(path, index=slice(0, None, slice_num))
            elif slice_num is not None and slice_num == 0:
                logger.info("Loading prediction dataset with caching.")
                if path.endswith(".traj"):
                    logger.info("Trajectory prediction dataset detected, loading with class ase.io.Trajectory")
                    atomsList = Trajectory(path)
                else:
                    atomsList = AtomsList(path)
            else:
                logger.info("Loading the dataset entirely on RAM.")
                atomsList = ase.io.read(path, index=':')

            # atom_counts = [len(atoms) for atoms in atomsList] --> inefficient for large datasets because it
            # literally creates a copy of the entire dataset on RAM, just to check whether the dataset is variable or
            # fixed. Instead, the following probabilistic method:
            fixed_or_variable = check_homogeneity(atomsList)
            if fixed_or_variable:
                # Uniform dataset
                logger.info(
                    f"Loading prepredicted data as uniform ASE dataset: {len(atomsList)} molecules, {len(atomsList[0])} atoms each")
                aseObject = aseDatasetLoader(
                    path,
                    atomsList=atomsList,
                    selected_energy_key=selected_energy_key,
                    selected_force_key=selected_force_key
                )
            else:
                # Variable dataset
                logger.info(f"Loading prepredicted data as variable ASE dataset: {len(atomsList)} molecules")
                aseObject = VariableASEDatasetLoader(
                    path,
                    atomsList=atomsList,
                    selected_energy_key=selected_energy_key,
                    selected_force_key=selected_force_key
                )

            try:
                E = aseObject.getEnergies()
            except (PropertyNotImplementedError, RuntimeError):
                logger.warning(
                    "Energy not available in prediction file. "
                    "Loading forces only."
                )
                E = None
            try:
                F = aseObject.getForces()
            except (PropertyNotImplementedError, RuntimeError):
                logger.warning(
                    "Forces not available in prediction file. "
                    "Loading energies only."
                )
                F = None

        dataset = self.getDataset(datasetKey)

        if E is not None:
            eDataset = dataset.getEnergies()
            if E.shape != eDataset.shape:
                logger.error(
                    f"Shape mismatch when loading prepredicted model. Model energy shape: {E.shape}, dataset energy shape: {eDataset.shape}"
                )
                logger.error(
                    "Prediction load failed, you have probably selected the wrong prediction for the designated dataset. "
                    "Please try again and choose the correct prediction file according to the dataset selected "
                    "in the file filter dropdown."
                )
                return

        available = [x for x in (E, F) if x is not None]
        modelKey = (
            md5FromArraysAndStrings(*available)
            if available
            else md5FromArraysAndStrings(path)
        )

        if E is not None:
            energyDataType = self.getDataType("energy")
            energyDataEntity = energyDataType.newDataEntity(energy=E.flatten())
            self.setData(
                energyDataEntity, "energy", model=modelKey, dataset=dataset
            )

        if F is not None:
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
        """Register a dataset loader class discovered during module loading."""
        self.datasetTypes[datasetType.datasetName] = datasetType

    def updateMaxSize(self, on_deletion, dataset):
        if on_deletion:
            maximum = 0
            for ds in self.datasets.values():
                n = ds.getN()
                if n is not None and n > maximum:
                    maximum = n
            self.maxDatasetSize = maximum
            logger.info(f"Maximum dataset size updated to : {maximum}")
        else:
            n = dataset.getN()
            if n is not None and n > self.maxDatasetSize:
                self.maxDatasetSize = n
                logger.info(f"Maximum dataset size updated to : {n}")

    def getMaxSize(self):
        return self.maxDatasetSize

    def setNewDataset(self, dataset, slice_num=-2):
        self.datasets[dataset.fingerprint] = dataset
        dataset.loaded = True
        if slice_num != -2:  # to avoid adding slices for sub-datasets.
            self.updateMaxSize(False, dataset)
            self.dataset_slice_numbers[dataset.fingerprint] = slice_num
        self.eventPush("DATASET_LOADED", dataset.fingerprint)

    def getDataset(self, key):
        """Fetch a loaded dataset by fingerprint."""
        return self.datasets.get(key, None)

    def getDatasetFromPath(self, path):
        """Resolve a loaded dataset through its source path."""
        return self.getDataset(self.getKeyFromPath(path))

    def deleteDataset(self, key):
        """Remove a dataset and invalidate every cached artifact derived from it."""
        dataset = self.getDataset(key)
        if dataset is None:
            return

        # Clean up all cached data for this dataset before deleting it
        # Cache keys are in format: "dataTypeKey__modelFingerprint__datasetFingerprint"
        cache_keys_to_delete = []
        for cache_key in self.cache.keys():
            parts = cache_key.split("__")
            if len(parts) == 3 and parts[2] == key:
                cache_keys_to_delete.append(cache_key)

        # Delete all cached data for this dataset
        for cache_key in cache_keys_to_delete:
            del self.cache[cache_key]
            logger.info(f"Deleted cached data: {cache_key}")

        if self.dataset_slice_numbers.get(key) is not None:  # We need to delete its slice number as well
            del self.dataset_slice_numbers[key]

        dataset.onDelete()
        del self.datasets[key]
        logger.info(f"Dataset {key} deleted")
        self.updateMaxSize(on_deletion=True, dataset=None)
        self.eventPush("DATASET_DELETED", key)

    def getAllDatasetKeys(self):
        """Expose active dataset fingerprints to UI and persistence code."""
        ds = self.getAllDatasets()
        return [x.fingerprint for x in ds]
        # return list(self.datasets.keys())

    def getAllDatasets(self, subOnly=False, excludeSubs=False):
        """Return active datasets with optional filtering for subdataset views."""
        ds = [x for x in self.datasets.values() if x.active]
        if subOnly:
            return [x for x in ds if x.isSubDataset]
        elif excludeSubs:
            return [x for x in ds if not x.isSubDataset]
        else:
            return ds

    def taskLoadDataset(self, path, datasetType, selected_energy_key=None,
                       selected_force_key=None, prediction_keys=None, slice_num=0):
        """Load dataset and optionally load predictions from same file.

        Args:
            path: Path to dataset file
            datasetType: Type of dataset loader to use
            selected_energy_key: Pre-selected energy key for reference (ASE only)
            selected_force_key: Pre-selected force key for reference (ASE only)
            prediction_keys: List of (energy_key, force_key, model_name) tuples
            :param slice_num: slicing number for sampled load of datasets.
        """
        self.newTask(
            self.loadDataset,
            args=(path, datasetType),
            kwargs={
                'selected_energy_key': selected_energy_key,
                'selected_force_key': selected_force_key,
                'prediction_keys': prediction_keys,
                'slice_num': slice_num
            },
            visual=True,
            name="Loading dataset",
            threaded=True,
        )

    def loadDataset(self, path, datasetType, taskID=None, selected_energy_key=None,
                   selected_force_key=None, prediction_keys=None, slice_num=0):
        """Load dataset and create ghost models for prediction keys."""
        #logger.info(f"self.datasetTypes:\n{self.datasetTypes}\narg datasetType:\n{datasetType}")
        if not os.path.exists(path):
            logger.error(f"Tried to load dataset, but path `{path}` not found")
            return None

        if datasetType not in self.datasetTypes:  # This if statement seems to be useless
            logger.error(
                f"Tried to load dataset, but dataset type {datasetType} not recognised"
            )
            return None

        # Load dataset - pass selected keys to ASE loader
        if datasetType == "ase (auto)":
            try:
                result = self.datasetTypes[datasetType](
                    path,
                    selected_energy_key=selected_energy_key,
                    selected_force_key=selected_force_key,
                    prediction_keys=prediction_keys,
                    show_dialog=False,  # Dialog already shown on main thread
                    slice_num=slice_num
                )
            except Exception as e:
                logger.error(f"Failed to load dataset {path} in method 'loadDataset'")
                return None
        else:
            result = self.datasetTypes[datasetType](path)

        # Handle SmartASELoader return value (tuple) or regular loader (dataset object)
        if isinstance(result, tuple):
            dataset, pred_keys = result
            if dataset is None:
                logger.info("Dataset loading cancelled by user")
                return

            # Merge prediction keys from dialog with any passed in.
            # SmartASELoader echoes the caller's prediction_keys unchanged
            # when show_dialog=False, so naïve concatenation would double
            # every entry.  Deduplicate to prevent loading predictions twice.
            if pred_keys:
                seen = {tuple(k) for k in (prediction_keys or [])}
                extra = [k for k in pred_keys if tuple(k) not in seen]
                prediction_keys = (prediction_keys or []) + extra
        else:
            dataset = result

        if dataset is None:
            logging.warn(f"Dataset `{path}` did not load successfully")
            return

        dataset.initialise()
        self.setNewDataset(dataset, slice_num)
        logging.info(f"Dataset `{path}` successfully loaded")

        # Load predictions as ghost models if specified
        if prediction_keys:
            # Reuse atomsList from dataset to avoid re-reading file
            atomsList = dataset.atomsList if hasattr(dataset, 'atomsList') else None
            self._loadPredictionsFromKeys(dataset, path, prediction_keys, atomsList=atomsList)

        self.lookForGhosts()

    def _loadPredictionsFromKeys(self, dataset, path, prediction_keys, atomsList=None):
        """Materialize extra energy/force columns as ghost-model cache entries.

        Args:
            dataset: The loaded dataset
            path: Path to the file
            prediction_keys: List of (energy_key, force_key, model_name) tuples
            atomsList: Optional pre-loaded atoms list to avoid re-reading file
        """
        from modules.aseDataset import aseDatasetLoader, VariableASEDatasetLoader
        import ase.io
        from utils import md5FromArraysAndStrings

        # Read file only if not provided
        if atomsList is None:
            atomsList = ase.io.read(path, index=":")

        atom_counts = [len(atoms) for atoms in atomsList]
        is_uniform = len(set(atom_counts)) == 1

        for energy_key, force_key, model_name in prediction_keys:
            try:
                # Create temporary loader with selected keys and pre-loaded atomsList
                if is_uniform:
                    temp_loader = aseDatasetLoader(
                        path,
                        atomsList=atomsList,
                        selected_energy_key=energy_key,
                        selected_force_key=force_key
                    )
                else:
                    temp_loader = VariableASEDatasetLoader(
                        path,
                        atomsList=atomsList,
                        selected_energy_key=energy_key,
                        selected_force_key=force_key
                    )

                # Extract predictions
                E = temp_loader.getEnergies()
                F = temp_loader.getForces()

                # Verify shape matches dataset
                dataset_E = dataset.getEnergies()
                if isinstance(E, list) and isinstance(dataset_E, list):
                    # Variable dataset - check list lengths
                    if len(E) != len(dataset_E):
                        logger.error(
                            f"Shape mismatch for prediction '{model_name}'. "
                            f"Expected {len(dataset_E)} molecules, got {len(E)}. Skipping."
                        )
                        continue
                elif hasattr(E, 'shape') and hasattr(dataset_E, 'shape'):
                    # Uniform dataset - check array shapes
                    if E.shape != dataset_E.shape:
                        logger.error(
                            f"Shape mismatch for prediction '{model_name}'. "
                            f"Expected {dataset_E.shape}, got {E.shape}. Skipping."
                        )
                        continue

                # Create ghost model fingerprint
                ghost_fp = md5FromArraysAndStrings(E, F, model_name)

                # Cache predictions
                energy_dt = self.getDataType("energy")
                if isinstance(E, list):
                    # Variable dataset - E is list of scalars, need to convert to array
                    import numpy as np
                    E_array = np.array(E)
                    energy_de = energy_dt.newDataEntity(energy=E_array.flatten())
                else:
                    energy_de = energy_dt.newDataEntity(energy=E.flatten())
                self.setData(energy_de, "energy", model=ghost_fp, dataset=dataset)

                forces_dt = self.getDataType("forces")
                forces_de = forces_dt.newDataEntity(forces=F)
                self.setData(forces_de, "forces", model=ghost_fp, dataset=dataset)

                # Register ghost model info
                self.info.setdefault('objects', {})[ghost_fp] = {
                    'path': path,
                    'name': model_name,
                    'type': 'ghost_model',
                    'energy_key': energy_key,
                    'force_key': force_key
                }

                logger.info(f"Loaded predictions for '{model_name}' from keys {energy_key}/{force_key}")

            except Exception as e:
                logger.error(f"Failed to load predictions for '{model_name}': {e}")
                import traceback
                logger.debug(traceback.format_exc())
                continue

    def declareSubDataset(self, parent, model, idx, subName):
        """Create or refresh a logical subset view over a parent dataset."""

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
        """Persist the current subdataset selection as its own frozen dataset object."""
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
        """Build a per-atom filtered dataset view for atom-level analyses."""
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
        """Resolve an object key without the caller needing to know its type."""
        model = self.getModel(key)
        if model is None:
            return self.getDataset(key)
        else:
            return model

    def getObject(self, *args):
        """Keep a short alias for generic object lookup call sites."""
        return self.getModelOrDataset(*args)

    def getKeyFromPath(self, path):
        """Map a known filesystem path back to the loaded object fingerprint."""
        # check dataset
        for dataset in self.getAllDatasets(excludeSubs=True):
            if dataset.path == path:
                return dataset.fingerprint

        for model in self.getAllModels():
            if model.path == path:
                return model.fingerprint

        return None

    def deleteObject(self, key):
        """Route generic delete requests to the appropriate registry."""
        if self.datasetExists(key):
            self.deleteDataset(key)
        elif self.modelExists(key):
            self.deleteModel(key)

    #############
    ## TASKS
    #############

    def newTask(self, *args, **kwargs):
        """Send environment work through the shared task queue."""
        return self.tm.queueTask(*args, **kwargs)

    def getTask(self, *args, **kwargs):
        """Expose task state for progress displays and cancellation logic."""
        return self.tm.getTask(*args, **kwargs)

    def onTaskCancel(self, taskID):
        """Keep parent generation requests consistent when a child task is cancelled."""
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
        """Reuse cancellation cleanup for failed tasks as well."""
        self.onTaskCancel(taskID)

    def onTaskDone(self, taskID):
        """Clear queue bookkeeping once a scheduled task has finished."""
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
        """Serve cached data, including derived subdataset and atom-filtered views."""
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
        """Store generated data in the cache and notify subscribers that it changed."""
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
        """Build the canonical cache key for one datatype/model/dataset triple."""
        dataType = self.getRegisteredDataType(dataTypeKey)
        if dataType is None:
            return None

        cacheKey = dataType.getCacheKey(model=model, dataset=dataset)

        return cacheKey

    def hasCacheKey(self, key, subChecks=True):
        """Check whether a cache key is available, optionally honoring subdataset fallbacks."""
        if key is None:
            logger.error("Called env.hasCacheKey(key) but key was None!")
            return False
        if subChecks:
            (dataTypeKey, model, dataset) = self.cacheKeyToComponents(key)
            return self.hasData(dataTypeKey, model=model, dataset=dataset)
        else:
            return key in self.cache

    def hasData(self, dataTypeKey, model=None, dataset=None):
        """Answer whether data exists, including inherited subdataset cases."""
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
        """Schedule data generation when the caller already has a full cache key."""
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
        """Deduplicate and queue one data-generation request."""
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
        """Provide an awaitable adapter for synchronous generation code."""
        self.generateData(*args, **kwargs)

    def canGenerateData(self, dataTypeKey, model=None, dataset=None):
        """Ask the data type whether all dependencies are already satisfied."""
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
        """Attempt one generation step and defer unresolved work to the dependency queue."""
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
        """Detect requests that can be satisfied from ghost-model cache instead of a real model."""
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
        """Record a high-level request for later dependency-driven generation."""
        dataType = self.getDataType(key)
        cacheKey = dataType.getCacheKey(model=model, dataset=dataset)
        self.generationQueue.add(cacheKey)
        if self.headless:
            print(f"Added {cacheKey} to generation queue", flush=True)

    async def handleGenerationQueue(self, *args):
        """Expand queued requests into the lowest runnable dependency tasks."""
        queue = self.generationQueue

        if len(queue) == 0:
            return

        logger.info(f"Handling generation queue {self.generationQueue}")

        # copying because we discard in loop
        keysToGenerate = {}
        for cacheKey in queue.copy():
            (dataTypeKey, model, dataset) = self.cacheKeyToComponents(cacheKey)

            if ("cluster" in cacheKey) and hasattr(dataset, 'isVariable') and dataset.isVariable:
                logger.info("The cluster errors feature is not supported for variable datasets")
                queue.discard(cacheKey)
                self.eventPush('CLUSTER_FOR_VARIABLE')
                continue

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
        """Ask the data type for the deepest currently generatable dependency set."""
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
        """Invalidate cached outputs when a dataset's membership changes."""
        toDelete = []
        for key in self.cache.keys():
            if datasetKey in key:
                toDelete.append(key)

        for key in toDelete:
            del self.cache[key]
            self.eventPush("DATA_UPDATED", key)

    def getCacheByKey(self, key, subChecks=True):
        """Resolve a cache key directly, with optional subdataset-aware lookup."""
        if subChecks:
            (dataTypeKey, model, dataset) = self.cacheKeyToComponents(key)
            return self.getData(dataTypeKey, model=model, dataset=dataset)
        else:
            return self.cache.get(key, None)

    def cacheKeyToComponents(self, key, dataTypeObject=False):
        """Decode a cache key back into datatype, model, and dataset references."""
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
        """Persist the session cache and object metadata so it can be restored later."""
        if not os.path.exists(path):
            os.mkdir(path)

        ## SAVE CACHE
        cacheDir = os.path.join(path, "cache")
        if not os.path.exists(cacheDir):
            os.mkdir(cacheDir)

        for key, entity in self.cache.items():
            if isinstance(entity, SubDataEntity):
                continue

            # Convert any inhomogeneous lists (e.g. variable-sized
            # dataset forces) to object arrays so numpy can save them.
            saveData = {}
            for k, v in entity.data.items():
                if isinstance(v, list):
                    saveData[k] = np.array(v, dtype=object)
                else:
                    saveData[k] = v
            np.savez_compressed(
                os.path.join(cacheDir, key),
                entityDataTypeKey=entity.dataType.key,
                cacheKey=key,
                **saveData,
            )

        ## GENERATE INFO
        info = {"objects": {}}
        for o in self.getAllDatasets(excludeSubs=True):
            obj_info = {
                "name": o.getName(),
                "path": o.path,
                "type": "dataset",
            }

            # Store ASE key selections if present
            if hasattr(o, 'selected_energy_key') and o.selected_energy_key:
                obj_info["ase_energy_key"] = o.selected_energy_key
            if hasattr(o, 'selected_force_key') and o.selected_force_key:
                obj_info["ase_force_key"] = o.selected_force_key

            info["objects"][o.fingerprint] = obj_info

        for o in self.getAllModels():
            info["objects"][o.fingerprint] = {
                "name": o.getName(),
                "path": o.path,
                "type": "model",
            }

        # Merge any additional info (including ghost models)
        if hasattr(self, 'info') and 'objects' in self.info:
            for fp, obj_info in self.info['objects'].items():
                if fp not in info['objects']:
                    info['objects'][fp] = obj_info

        # dataset/model names and paths

        ## SAVE INFO
        infoFile = os.path.join(path, "info.json")
        with open(infoFile, "w") as f:
            json.dump(info, f, indent=4)

    def taskLoad(self, path):
        """Queue restoration of a previously saved session."""
        self.newTask(
            self.load,
            args=(path,),
            visual=True,
            name="Loading save",
            threaded=True,
        )

    def load(self, path, taskID=None):
        """Rebuild datasets, ghost models, and cached entities from a saved session."""
        # LOAD INFO (names etc)
        infoFile = os.path.join(path, "info.json")
        info = None
        if os.path.exists(infoFile):
            with open(infoFile, "r") as f:
                info = json.load(f)
            self.loadInfo(info)

        ## LOAD DATASETS AND MODELS FROM INFO
        if info is not None and "objects" in info:
            for fingerprint, obj_info in info["objects"].items():
                obj_path = obj_info.get("path")
                obj_name = obj_info.get("name", "Unknown")
                obj_type = obj_info.get("type")

                # Models are recreated as ghosts from cached data below
                if obj_type == "model":
                    continue

                if obj_path is None or not os.path.exists(obj_path):
                    logger.warning(f"Skipping {obj_name}: path not found at {obj_path}")
                    continue

                # Load as dataset
                if obj_type == "dataset":
                    # Extract ASE-specific keys
                    ase_energy_key = obj_info.get("ase_energy_key")
                    ase_force_key = obj_info.get("ase_force_key")

                    # Find prediction keys associated with this dataset
                    prediction_keys = []
                    for ghost_fp, ghost_info in info.get('objects', {}).items():
                        if (ghost_info.get('type') == 'ghost_model' and
                                ghost_info.get('path') == obj_path):
                            prediction_keys.append((
                                ghost_info['energy_key'],
                                ghost_info['force_key'],
                                ghost_info['name']
                            ))

                    for loader_name, loader_class in self.datasetTypes.items():
                        try:
                            # Special handling for ASE loader with key selection
                            if loader_name == "ase (auto)" and (ase_energy_key or ase_force_key):
                                # Pass keys and disable dialog
                                result = loader_class(
                                    obj_path,
                                    selected_energy_key=ase_energy_key,
                                    selected_force_key=ase_force_key,
                                    prediction_keys=prediction_keys,
                                    show_dialog=False  # Don't show dialog when loading session
                                )

                                if isinstance(result, tuple):
                                    dataset, _ = result
                                else:
                                    dataset = result
                            else:
                                dataset = loader_class(obj_path)

                            if dataset is not None:
                                dataset.initialise()
                                self.setNewDataset(dataset)
                                logger.info(f"Loaded dataset {obj_name} from {obj_path}")

                                # Load predictions if this is an ASE dataset
                                if prediction_keys and loader_name == "ase (auto)":
                                    atomsList = dataset.atomsList if hasattr(dataset, 'atomsList') else None
                                    self._loadPredictionsFromKeys(dataset, obj_path, prediction_keys,
                                                                  atomsList=atomsList)

                                break
                        except Exception as e:
                            logger.debug(f"Failed to load with {loader_name}: {e}")
                            continue
                else:
                    # Legacy info.json without type field: guess by extension
                    ext = os.path.splitext(obj_path)[1].lower()
                    dataset_extensions = ['.xyz', '.extxyz', '.db', '.traj', '.npz']
                    if ext in dataset_extensions:
                        for loader_name, loader_class in self.datasetTypes.items():
                            try:
                                dataset = loader_class(obj_path)
                                if dataset is not None:
                                    dataset.initialise()
                                    self.setNewDataset(dataset)
                                    logger.info(f"Loaded dataset {obj_name} from {obj_path}")
                                    break
                            except Exception as e:
                                continue

        ## LOAD CACHE
        cacheDir = os.path.join(path, "cache")
        for npzPath in glob.glob(os.path.join(cacheDir, "*.npz")):
            d = dict(np.load(npzPath, allow_pickle=True))
            dataTypeKey = str(d.pop("entityDataTypeKey"))
            cacheKey = str(d.pop("cacheKey"))

            # Convert numpy object arrays back to Python lists.
            # Variable-sized data (e.g. forces for molecules with
            # different atom counts) is saved as np.array(list,
            # dtype=object). The rest of the code expects these
            # as Python lists.
            for k, v in d.items():
                if isinstance(v, np.ndarray) and v.dtype == object:
                    d[k] = list(v)

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
        """Merge persisted metadata into the current session state."""
        self.info.update(info)

    def saveDataset(self, dataset, datasetType, form, path, taskID=None):
        """Export a dataset through its loader-specific serializer."""
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
        """Queue dataset export so serialization does not block other work."""
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
        """Provide a stable display color for combined model/dataset views."""
        if dataset is None and model is None:
            return (255, 255, 255)
        elif dataset is None:
            return model.color
        elif model is None:
            return dataset.color
        else:
            return mixColors(model.color, dataset.color)

    def lookForGhosts(self):
        """Recreate ghost model placeholders for cached prediction-only data."""

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

    def taskLoadZeroModel(self):
        """Queue loading of the built-in zero baseline model."""
        self.newTask(
            self.loadZeroModel,
            args=(),
            visual=True,
            name="Loading model",
            threaded=True,
        )

    def loadZeroModel(self, taskID=None):
        """Ensure the singleton zero baseline model exists in the session."""
        fp = ZeroModelLoader.fingerprint
        if self.modelExists(fp):
            return
        model = ZeroModelLoader(self)
        model.initialise()
        self.setNewModel(model)

    def startInteract(self, **kwargs):
        """Drop into a REPL seeded with useful locals for manual debugging."""
        import code

        code.interact(local=kwargs)

    async def _disconnectRemoteSession(self):
        """Disconnect any active remote session on QUIT_EVENT."""
        session = self.remoteSession
        if session is not None:
            logger.info("Cleaning up remote session on quit…")
            await session.disconnect()
            self.remoteSession = None

    # ── remote array transfer ─────────────────────────────────────────────────

    def _onRemoteDatasetMeta(
        self,
        fingerprint,
        name=None,
        n=None,
        has_forces=True,
        is_sub=False,
    ):
        """Create a local CachedRemoteDataset proxy when the server loads a dataset.

        The proxy has no arrays yet (``is_remote_proxy=True``) but appears in
        the Loupe dataset ComboBox so the user can select it.  Actual array
        transfer is triggered by :meth:`taskFetchRemoteDataset`.
        """
        from cluster.remote_dataset import CachedRemoteDataset

        if self.getDataset(fingerprint) is not None:
            logger.debug("REMOTE_DATASET_META: proxy already exists for %r", fingerprint)
            return

        n_val = int(n) if n is not None else 0
        label = name if name else fingerprint[:12]
        proxy = CachedRemoteDataset(fingerprint, label, n_val)
        # slice_num=-2 skips the maxDatasetSize update (proxy has no arrays)
        self.setNewDataset(proxy, slice_num=-2)
        logger.info(
            "Remote proxy created: %r (n=%d, has_forces=%s)",
            label, n_val, has_forces,
        )

    def _onRemoteModelMeta(
        self,
        fingerprint,
        name=None,
        dataset_fingerprints=None,
    ):
        """Create a local GhostModelLoader when the server registers a ghost model.

        Called when ``REMOTE_MODEL_META`` arrives.  The server sends this event
        from the ``MODEL_LOADED`` handler, which fires *after*
        ``_loadPredictionsFromKeys`` and ``lookForGhosts()`` have run — so
        prediction arrays are already in ``env.cache`` on the server side.

        After creating the ghost model, auto-triggers ``taskFetchRemoteDataset``
        for every associated dataset that still has no arrays on the client
        (``is_remote_proxy=True``).  This pulls the arrays *including* the
        prediction data so plots work immediately.
        """
        from modelLoaders.ghost import GhostModelLoader

        if self.getModel(fingerprint) is not None:
            logger.debug(
                "REMOTE_MODEL_META: ghost model already exists for %r", fingerprint
            )
            return

        model_name = name if name else fingerprint[:8]
        # Register info so GhostModelLoader.initialise() finds the display name.
        self.info.setdefault("objects", {})[fingerprint] = {
            "path": "remote",
            "name": model_name,
            "type": "ghost_model",
        }
        model = GhostModelLoader(self, fingerprint)
        model.initialise()
        self.setNewModel(model)
        logger.info(
            "Remote ghost model created: %r (%s)", fingerprint[:8], model_name
        )

        # Auto-fetch arrays for associated datasets that are still proxies.
        # Prediction data is included in the array transfer, so after this
        # completes, the cache has everything plots need.
        for ds_fp in (dataset_fingerprints or []):
            dataset = self.getDataset(ds_fp)
            if dataset is not None and getattr(dataset, "is_remote_proxy", True):
                logger.info(
                    "Auto-fetching arrays for dataset %r (has new ghost model %r)",
                    ds_fp[:8], fingerprint[:8],
                )
                self.taskFetchRemoteDataset(ds_fp)

    async def _fetchRemoteDatasetTask(self, fingerprint, taskID=None):
        """Async task: transfer arrays from server and populate local proxy.

        Progress is reported through TASK_PROGRESS so the Tasks panel shows a
        progress bar during the transfer.
        """
        session = self.remoteSession
        if session is None:
            logger.error("taskFetchRemoteDataset: no remote session active")
            return

        self.eventPush(
            "TASK_PROGRESS",
            taskID,
            message="Requesting arrays from remote server…",
        )
        try:
            arrays = await session.request_subdataset_arrays(fingerprint)
        except asyncio.TimeoutError:
            self.eventPush(
                "TASK_PROGRESS",
                taskID,
                message="Timed out waiting for server response",
                error=True,
            )
            logger.error("Array transfer timed out for %r", fingerprint)
            return
        except Exception as exc:
            self.eventPush(
                "TASK_PROGRESS",
                taskID,
                message=f"Transfer error: {exc}",
                error=True,
            )
            logger.error("Array transfer failed for %r: %s", fingerprint, exc)
            return

        self.eventPush(
            "TASK_PROGRESS",
            taskID,
            message="Populating local cache…",
        )

        # Unpack payload — request_subdataset_arrays now returns a dict with
        # two top-level keys: "arrays" (coord/element arrays + pred__ entries)
        # and "model_names" (fp → display name).
        payload = arrays  # named "arrays" for historical reasons; it's the payload
        raw_arrays = payload.get("arrays", payload)   # back-compat if plain dict
        model_names = payload.get("model_names") or {}

        # Separate prediction entries from geometry/element arrays.
        pred_data: dict = {}   # model_fp → {dtype: np.ndarray}
        main_arrays: dict = {}
        for key, val in raw_arrays.items():
            if key.startswith("pred__"):
                parts = key.split("__", 2)
                if len(parts) == 3:
                    _, dt_key, model_fp = parts
                    pred_data.setdefault(model_fp, {})[dt_key] = val
            else:
                main_arrays[key] = val

        dataset = self.getDataset(fingerprint)
        if dataset is None:
            # No proxy was created yet — build one now
            from cluster.remote_dataset import CachedRemoteDataset

            n_val = len(main_arrays.get("R") or [])
            dataset = CachedRemoteDataset(fingerprint, fingerprint[:12], n_val)
            self.setNewDataset(dataset, slice_num=-2)

        dataset.populate(main_arrays)

        # ── Recreate prediction DataEntities from transferred arrays ─────────
        if pred_data:
            self.eventPush(
                "TASK_PROGRESS", taskID,
                message="Importing prediction data…",
            )

        offsets = main_arrays.get("offsets")   # present for variable datasets
        for model_fp, preds in pred_data.items():
            try:
                E = preds.get("energy")
                F = preds.get("forces")

                if E is not None:
                    energy_dt = self.getDataType("energy")
                    energy_de = energy_dt.newDataEntity(
                        energy=np.asarray(E).flatten()
                    )
                    self.setData(energy_de, "energy",
                                 model=model_fp, dataset=dataset)

                if F is not None:
                    forces_dt = self.getDataType("forces")
                    F_arr = np.asarray(F)
                    if offsets is not None:
                        # Variable dataset — F was flattened on the server;
                        # reconstruct as list of per-molecule arrays.
                        F_val = [
                            F_arr[offsets[i]:offsets[i + 1]]
                            for i in range(len(offsets) - 1)
                        ]
                    else:
                        F_val = F_arr  # uniform (N, natoms, 3)
                    forces_de = forces_dt.newDataEntity(forces=F_val)
                    self.setData(forces_de, "forces",
                                 model=model_fp, dataset=dataset)

                # Store model info so GhostModelLoader.initialise() finds it.
                model_name = model_names.get(model_fp, model_fp[:8])
                self.info.setdefault("objects", {})[model_fp] = {
                    "path": "remote",
                    "name": model_name,
                    "type": "ghost_model",
                }
                logger.info(
                    "Imported predictions for %r (model %s)",
                    model_name, model_fp[:8],
                )
            except Exception as exc:
                logger.error(
                    "Failed to import predictions for model %r: %s",
                    model_fp[:8], exc,
                )

        # Create GhostModelLoader objects for any newly-imported prediction data
        if pred_data:
            self.lookForGhosts()

        # Notify Loupe (and any other subscriber) that arrays are ready
        self.eventPush("REMOTE_ARRAY_FETCH_DONE", fingerprint)
        self.eventPush("DATASET_UPDATED", fingerprint)
        logger.info("Array transfer complete for %r", fingerprint)

    def taskFetchRemoteDataset(self, fingerprint: str) -> None:
        """Schedule an async task to transfer arrays for *fingerprint* from the server.

        Idempotent: if arrays are already cached in the session,
        :meth:`RemoteSession.request_subdataset_arrays` returns instantly.
        """
        self.newTask(
            self._fetchRemoteDatasetTask,
            args=(fingerprint,),
            visual=True,
            name="Fetching remote arrays",
        )


class HeadlessEnvironment(Environment, threading.Thread):
    def __init__(self):
        """Combine environment state with a dedicated thread for headless execution."""
        Environment.__init__(self, headless=True)
        threading.Thread.__init__(self)
        self.loop = None

    def run(self):
        """Own the asyncio event loop inside the headless worker thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.headlessEventLoop())

    async def headlessEventLoop(self):
        """Drive events, generation, and task execution until shutdown is requested."""
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
        """Signal the headless loop to stop cleanly."""
        self.quitReady = True

    def waitForTasks(self, verbose=False, dt=5):
        """Block scripted callers until queued, running, and deferred work has settled."""
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
                            prog = f'{task["progress"] * 100:.0f}%'

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
    """Bootstrap modules, logging, and the headless event thread for scripts."""
    from utils import setupLogger

    thread = HeadlessEnvironment()
    setupLogger()

    loadModules(None, thread, headless=True)
    thread.start()

    return thread
