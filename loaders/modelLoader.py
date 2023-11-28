import os
from events import EventClass
from utils import removeExtension
import torch
import logging
import numpy as np
from config.userConfig import getConfig
from utils import hexToRGB

logger = logging.getLogger("FFAST")
GLOBAL_MODELS_COUNTER = 0


class ModelLoader(EventClass):
    """
    Base class for any model. Contains all model-agnostic methods such as
    setting the display name and other parameters.

    Every model-dependent method, e.g. loading the model, predicting energies
    or forces, etc... are instead found in the specific ModelLoader subclasses.
    """

    isSubDataset = False  # for object handlers

    def __init__(self, env, path):
        super().__init__()
        self.env = env
        self.path = path

        global GLOBAL_MODELS_COUNTER

        colors = getConfig("modelColors")
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
    modelFileExtension = "*"
    name = "?"

    def setName(self, name):
        if name == "":
            return self.setName(self.name)
        self.name = name
        if self.loaded:
            self.eventPush("OBJECT_NAME_CHANGED", self.fingerprint)

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
        self.eventPush("OBJECT_COLOR_CHANGED", self.fingerprint)


class ModelLoaderACE(ModelLoader):
    modelName = "?"

    def __init__(self, env, path):
        super().__init__(env, path)

    def predict(self, dataset, indices=None, batchSize=1, taskID=None):
        from ase import Atoms

        if indices is None:
            R = dataset.getCoordinates()
        else:
            R = dataset.getCoordinates(indices=indices)

        z = dataset.getElements()
        lattice = dataset.getLattice()

        E, F = [], []
        for i in range(len(R)):
            r = R[i]
            if lattice is not None:
                atoms = Atoms(
                    numbers=z, positions=r, cell=lattice, pbc=[True] * 3
                )
            else:
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
