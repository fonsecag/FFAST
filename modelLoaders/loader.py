import os
from events import EventClass
from Utils.misc import removeExtension
import torch
import logging
import numpy as np
from config.userConfig import config
from Utils.misc import hexToRGB

logger = logging.getLogger("FFAST")
GLOBAL_MODELS_COUNTER = 0


def loadModel(env, path):
    """
    Entry function for loading any model. This function simply decides which
    loader class should be used to load a model given a path, then returns
    a loaded object according.

    Args:
        path (str): path to the model
        fromCache (bool, optional): Flag controlling whether to load a dummy
            model. Used e.g. when the cache contains information on a model
            whose path is unknown or no longer exists. Defaults to False.

    Returns:
        ModelLoader: ModelLoader object for given path
    """
    model = None

    from .sGDML import sGDMLModelLoader
    from .SchNet import SchNetModelLoader
    from .Nequip import NequipModelLoader
    from .MACE import MACEModelLoader
    from .SpookyNet import SpookyNetModelLoader

    if not os.path.exists(path):
        logger.error(f"Tried to load model, but path `{path}` not found")
        return None

    # TODO put each of those into the respective model files
    if path.endswith(".npz"):
        model = sGDMLModelLoader(env, path)
    elif "." not in path:
        model = SchNetModelLoader(env, path)
    elif path.endswith(".pth"):
        from nequip.scripts.deploy import _ALL_METADATA_KEYS

        metadata = {k: "" for k in _ALL_METADATA_KEYS}
        fil = torch.jit.load(path, _extra_files=metadata)
        if metadata["nequip_version"] == "":
            logger.warn(f"Tried loading {path} as Nequip model, but failed.")
            model = None
        else:
            model = NequipModelLoader(env, path)
    elif path.endswith(".pt"):
        model = SpookyNetModelLoader(env, path)
    elif path.endswith(".model"):
        model = MACEModelLoader(env, path)
    else:
        model = None

    if model is not None:
        model.initialise()

    return model


class ModelLoader(EventClass):
    """
    Base class for any model. Contains all model-agnostic methods such as
    setting the display name and other parameters.

    Every model-dependent method, e.g. loading the model, predicting energies
    or forces, etc... are instead found in the specific ModelLoader subclasses.
    """

    def __init__(self, env, path):
        super().__init__()
        self.env = env
        self.path = path

        global GLOBAL_MODELS_COUNTER

        colors = config["modelColors"]
        nColors = len(colors)
        self.color = hexToRGB(colors[GLOBAL_MODELS_COUNTER % nColors])

        GLOBAL_MODELS_COUNTER += 1

    color = [255, 255, 255]
    fingerprint = None
    loadeeType = "model"
    loaded = False
    isGhost = False
    singlePredict = False
    modelName = "N/A"

    def setName(self, name):
        if name == "":
            return self.setName(self.name)
        self.name = name
        if self.loaded:
            self.eventPush("MODEL_NAME_CHANGED", self.fingerprint)

    def getDisplayName(self):
        return self.name

    def getName(self):
        return self.name

    def initialise(self):
        self.fingerprint = self.getFingerprint()

        name = removeExtension(os.path.basename(self.path))
        self.setName(name)

    def onDelete(self):
        pass

    # to be overwritten
    def getInfo(self):
        return []

    def setColor(self, r, g, b):
        self.color = [r, g, b]
        self.eventPush("MODEL_COLOR_CHANGED", self.fingerprint)


class ModelLoaderACE(ModelLoader):
    modelName = "?"

    def __init__(self, env, path):
        super().__init__(env, path)

    def predict(self, dataset, indices=None, batchSize=50, taskID=None):
        from ase import Atoms

        if indices is None:
            R = dataset.getCoordinates()
        else:
            R = dataset.getCoordinates(indices=indices)
        z = dataset.getElements()

        E, F = [], []
        for i in range(len(R)):
            r = R[i]
            atoms = Atoms(numbers=z, positions=r)
            atoms.calc = self.calculator
            F.append(atoms.get_forces())
            E.append(atoms.get_potential_energy())

            if (taskID is not None) and (i % batchSize == 0):
                self.eventPush(
                    "TASK_PROGRESS",
                    taskID,
                    progMax=len(R),
                    prog=i,
                    message=f"{self.modelName} batch predictions",
                    quiet=True,
                    percent=True,
                )

                if not self.env.tm.isTaskRunning(taskID):
                    return None

        F = np.array(F)
        return (np.array(E).flatten(), F.reshape(F.shape[0], -1, 3))
