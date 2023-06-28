import logging
import time
from events import EventClass

logger = logging.getLogger("FFAST")


class DataEntity:
    unitType = None
    unit = None
    timestamp = 0
    dataType = None

    def __init__(self, dataType, **kwargs):
        self.dataType = dataType
        self.data = {}
        for k, v in kwargs.items():
            self.data[k] = v

        self.timestamp = time.time()

    def get(self, key=None):
        if key is None:
            keys = self.keys()
            if len(keys) == 1:
                return self.data[keys[0]]
            else:
                return None

        return self.data.get(key, None)

    def keys(self):
        return list(self.data.keys())

    def getSubEntity(self, indices):
        if indices is None:
            return self
        return SubDataEntity(self, indices)

    def getAtomFilteredEntity(self, indices):
        if indices is None:
            return self
        return AtomFilteredEntity(self, indices)


class SubDataEntity(DataEntity):
    def __init__(self, parent, indices):
        self.parent = parent
        self.indices = indices

        self.unitType = parent.unitType
        self.unit = parent.unit
        self.timestamp = parent.timestamp
        self.dataType = parent.dataType
        self.data = parent.data

    def get(self, key=None):
        return self.parent.get(key=key)[self.indices]


class AtomFilteredEntity(DataEntity):
    def __init__(self, parent, indices):
        self.parent = parent
        self.indices = indices

        self.unitType = parent.unitType
        self.unit = parent.unit
        self.timestamp = parent.timestamp
        self.dataType = parent.dataType
        self.data = parent.data

    def get(self, key=None):
        return self.parent.get(key=key)[:, self.indices]


class DataType(EventClass):
    modelDependent = False
    datasetDependent = False
    key = None
    data = None
    dependencies = None

    iterable = False  # if True, results are per-config (e.g. forces, energies..., as opposed to distributions)
    atomFilterable = False  # if True, results are per-atom (e.g. forces)
    atomConstant = False  # if True, results are independent of atom filter (e.g. energy, kind of)

    def __init__(self, env):
        super().__init__()
        self.env = env

    def getCacheKey(self, model=None, dataset=None):
        keys = [self.key]

        if self.modelDependent:
            if model is None:
                logger.error(
                    f"Getting cache key of model dependent DataType"
                    + f"{self}, key {self.key}, but no model was given"
                )
                return None
            if isinstance(model, str):
                keys.append(model)
            else:
                keys.append(model.fingerprint)
        else:
            keys.append("nil")

        if self.datasetDependent:
            if dataset is None:
                logger.exception(
                    f"Getting cache key of dataset dependent DataType"
                    + f"{self}, key {self.key}, but no dataset was given"
                )
                return None

            if isinstance(dataset, str):
                keys.append(dataset)
            else:
                keys.append(dataset.fingerprint)
        else:
            keys.append("nil")

        key = "__".join(keys)

        return key

    def generateData(self, dataset=None, model=None, taskID=None):
        if self.datasetDependent and (dataset is None):
            logger.error(
                f"Getting data of dataset dependent DataType"
                + f"{self}, key {self.key}, but no dataset was given"
            )
            return None

        if self.modelDependent and (model is None):
            logger.error(
                f"Getting data of model dependent DataType"
                + f"{self}, key {self.key}, but no model was given"
            )
            return None

        data = None
        if dataset.isSubDataset and dataset.isAtomFiltered:
            if self.atomFilterable or self.atomConstant:
                return self.generateData(
                    dataset=dataset.parent, model=model, taskID=taskID
                )

        (deps, canGenerate) = self.checkDependencies(
            dataset=dataset, model=model
        )
        if canGenerate:
            data = self.data(dataset, model, taskID=taskID)

            if data is None:
                logger.error(
                    f"DataType {self} generated data but returned None. "
                    + "The .data() method needs to return something when"
                    + " successful"
                )

        return data is not None

    def checkDependencies(self, dataset=None, model=None):
        if self.dependencies is None:
            return [], True

        env = self.env
        deps = []
        for dep in self.dependencies:
            if env.hasData(dep, dataset=dataset, model=model):
                continue

            key = env.getCacheKey(dep, dataset=dataset, model=model)
            deps.append(key)

        # IF ATOM-FILTERED, PARENT DATA CAN BE DEPENDENCY
        if dataset.isSubDataset and dataset.isAtomFiltered:
            if self.atomFilterable or self.atomConstant:
                if not env.hasData(dep, dataset=dataset.parent, model=model):
                    key = env.getCacheKey(
                        dep, dataset=dataset.parent, model=model
                    )
                    deps.append(key)

        return (deps, len(deps) == 0)

    def getGeneratableComponent(self, dataset=None, model=None):
        if self.dependencies is None:
            return [], True

        env = self.env
        generatableComps = []

        comps = [env.getCacheKey(self.key, model=model, dataset=dataset)]

        for i in range(100):
            # 100 instead of a while loop just to avoid crashing if infinite
            # loops are created unvoluntarily. Still catching them to fix it
            if i == 99:
                logger.exception(
                    f"Infinite loop in lowest generatable components."
                )

            newComps = []
            for compKey in comps:

                dt, m, d = env.cacheKeyToComponents(
                    compKey, dataTypeObject=True
                )

                (deps, canGenerate) = dt.checkDependencies(dataset=d, model=m)
                if canGenerate:
                    generatableComps.append((compKey))
                else:
                    for dep in deps:
                        newComps.append(dep)

            if len(newComps) == 0:
                break

            comps = newComps

        return set(generatableComps)

    def newDataEntity(self, *args, **kwargs):
        de = DataEntity(self, *args, **kwargs)
        return de


class EnergyPredictionData(DataType):
    modelDependent = True
    datasetDependent = True
    key = "energy"
    iterable = True
    atomConstant = True

    def __init__(self, *args):
        super().__init__(*args)

    def data(self, dataset=None, model=None, taskID=None):
        env = self.env

        if model.singlePredict:
            (e, f) = model.predict(dataset, taskID=taskID)
            fData = self.newDataEntity(forces=f)
            env.setData(fData, "forces", model=model, dataset=dataset)

        else:
            e = model.predictE(dataset, taskID=taskID)

        eData = self.newDataEntity(energy=e)
        env.setData(eData, "energy", model=model, dataset=dataset)

        return True


class ForcesPredictionData(DataType):
    modelDependent = True
    datasetDependent = True
    key = "forces"
    iterable = True
    atomFilterable = True

    def __init__(self, *args):
        super().__init__(*args)

    def data(self, dataset=None, model=None, taskID=None):
        env = self.env

        if model.singlePredict:
            (e, f) = model.predict(dataset, taskID=taskID)
            eData = self.newDataEntity(energy=e)
            env.setData(eData, "energy", model=model, dataset=dataset)

        else:
            f = model.predictF(dataset, taskID=taskID)

        fData = self.newDataEntity(forces=f)
        env.setData(fData, "forces", model=model, dataset=dataset)

        return True
