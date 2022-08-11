from collections import Counter
import numpy as np
import os
from Utils.misc import md5FromArraysAndStrings, removeExtension
import logging
from events import EventClass
from scipy.spatial.distance import pdist

logger = logging.getLogger("FFAST")

zStrToZInt = {
    "H": 1,
    "He": 2,
    "Li": 3,
    "Be": 4,
    "B": 5,
    "C": 6,
    "N": 7,
    "O": 8,
    "F": 9,
    "Ne": 10,
    "Na": 11,
    "Mg": 12,
    "Al": 13,
    "Si": 14,
    "P": 15,
    "S": 16,
    "Cl": 17,
    "Ar": 18,
    "K": 19,
    "Ca": 20,
    "Sc": 21,
    "Ti": 22,
    "V": 23,
    "Cr": 24,
    "Mn": 25,
    "Fe": 26,
    "Co": 27,
    "Ni": 28,
    "Cu": 29,
    "Zn": 30,
    "Ga": 31,
    "Ge": 32,
    "As": 33,
    "Se": 34,
    "Br": 35,
    "Kr": 36,
    "Rb": 37,
    "Sr": 38,
    "Y": 39,
    "Zr": 40,
    "Nb": 41,
    "Mo": 42,
    "Tc": 43,
    "Ru": 44,
    "Rh": 45,
    "Pd": 46,
    "Ag": 47,
    "Cd": 48,
    "In": 49,
    "Sn": 50,
    "Sb": 51,
    "Te": 52,
    "I": 53,
    "Xe": 54,
    "Cs": 55,
    "Ba": 56,
    "La": 57,
    "Ce": 58,
    "Pr": 59,
    "Nd": 60,
    "Pm": 61,
    "Sm": 62,
    "Eu": 63,
    "Gd": 64,
    "Tb": 65,
    "Dy": 66,
    "Ho": 67,
    "Er": 68,
    "Tm": 69,
    "Yb": 70,
    "Lu": 71,
    "Hf": 72,
    "Ta": 73,
    "W": 74,
    "Re": 75,
    "Os": 76,
    "Ir": 77,
    "Pt": 78,
    "Au": 79,
    "Hg": 80,
    "Tl": 81,
    "Pb": 82,
    "Bi": 83,
    "Po": 84,
    "At": 85,
    "Rn": 86,
    "Fr": 87,
    "Ra": 88,
    "Ac": 89,
    "Th": 90,
    "Pa": 91,
    "U": 92,
    "Np": 93,
    "Pu": 94,
    "Am": 95,
    "Cm": 96,
    "Bk": 97,
    "Cf": 98,
    "Es": 99,
    "Fm": 100,
    "Md": 101,
    "No": 102,
    "Lr": 103,
    "Rf": 104,
    "Db": 105,
    "Sg": 106,
    "Bh": 107,
    "Hs": 108,
    "Mt": 109,
    "Ds": 110,
    "Rg": 111,
    "Cn": 112,
    "Uuq": 114,
    "Uuh": 116,
}

zIntToZStr = {v: k for k, v in zStrToZInt.items()}


def toDistance(R):

    shape = R.shape
    try:
        dim = shape[2]
    except:
        return
    if shape[1] < 2:
        return

    y = []

    for i in range(len(R)):  ##goes through samples
        y.append(pdist(R[i]))

    y = np.array(y)
    return y


def loadDataset(path, fromCache=False):
    """
    Entry function for loading any dataset. This function simply decides which
    loader class should be used to load a dataset given a path, then returns
    a loaded object according.

    Args:
        path (str): path to the dataset
        fromCache (bool, optional): Flag controlling whether to load a dummy
            dataset. Used e.g. when the cache contains information on a dataset
            whose path is unknown or no longer exists. Defaults to False.

    Returns:
        DatasetLoader: DatasetLoader object for given path
    """

    from .sGDML import sGDMLDatasetLoader

    if not os.path.exists(path):
        logger.error(f"Tried to load dataset, but path `{path}` not found")
        return None

    dataset = sGDMLDatasetLoader(path)
    dataset.initialise()
    return dataset

class DatasetLoader(EventClass):
    """
    Base class for any dataset. Contains all dataset-agnostic methods.

    Every dataset-dependent method, e.g. loading the dataset, getting energies
    or forces, etc... are instead found in the specific DatasetLoader
    subclasses.
    """

    isSubDataset = False
    isGhost = False

    def __init__(self, path):
        self.path = path

    loadeeType = "dataset"

    zIntToZStr = zIntToZStr
    zStrToZInt = zStrToZInt

    color = (0, 0, 0, 255)

    name = "N/A"
    loaded = False
    active = True

    def zToChemicalFormula(self, z):
        """
        Converts a list of atomic numbers to a chemical formula (using organic
        chemistry conventions).

        Args:
            z (array): Array of integers representing atomic numbers.

        Returns:
            Formula (str): Chemical formula.
        """

        z = [zIntToZStr[x] for x in z]
        c = Counter(z)
        s = ""

        if "C" in c:
            s += f'C{c["C"]}'

        if "H" in c:
            s += f'H{c["H"]}'

        for atom, n in sorted(c.items()):
            if atom == "H" or atom == "C":
                continue

            if n < 2:
                n = ""
            s += f"{atom}{n}"

        return s

    def getFingerprint(self):

        z = self.getElements()
        r = self.getCoordinates()
        e = self.getEnergies()
        f = self.getForces()
        fp = md5FromArraysAndStrings(z, r, e, f)

        return fp

    def getKey(self):
        return self.getFingerprint()

    def setName(self, name):
        if name == "":
            return self.setName(self.name)
        self.name = name
        if self.loaded:
            self.eventPush("DATASET_NAME_CHANGED", self.fingerprint)

    def getName(self):
        return self.name

    def initialise(self):
        self.fingerprint = self.getFingerprint()

        name = removeExtension(os.path.basename(self.path))
        self.setName(name)

    def getPDist(self, indices=None):
        R = self.getCoordinates(indices=indices)
        return toDistance(R)

    def getDisplayName(self):

        tag = ""
        if self.isSubDataset:
            tag = "*"

        return f"{tag}{self.getName()}"

    def setActive(self, state):
        if self.active == state:
            return
        self.active = state
        self.eventPush("DATASET_STATE_CHANGED", self.fingerprint)

    def onDelete(self):
        pass

class SubDataset(DatasetLoader):

    loadeeType = "dataset"
    isSubDataset = True
    color = (0, 0, 0, 255)

    name = "N/A"
    loaded = False
    modelDep = None
    parent = None

    def __init__(self, parentDataset, model, indices, subName):
        self.subName = subName
        self.parent = parentDataset
        self.modelDep = model

        self.indices = indices
        self.updatePath()

    def updatePath(self):
        self.path = (
            f"{self.subName},{self.parent.getName()},{self.modelDep.getName()}"
        )

    def setIndices(self, indices):
        self.indices = indices
        self.eventPush("SUBDATASET_INDICES_CHANGED", self.fingerprint)
        self.eventPush("DATASET_UPDATED", self.fingerprint)

    def getFingerprint(self, parent=None, model=None, subName=None):
        if parent is None:
            parent = self.parent
        if model is None:
            model = self.modelDep
        if subName is None:
            subName = self.subName

        if model is None:
            fp = md5FromArraysAndStrings(parent.fingerprint, subName)
        else:
            fp = md5FromArraysAndStrings(
                parent.fingerprint, model.fingerprint, subName
            )

        return fp

    def initialise(self):
        self.fingerprint = self.getFingerprint()

        if self.fingerprint == self.parent.fingerprint:
            raise ValueError(
                f"SubDataset for dataset {self.parent} has same fingerprint. Aborted."
            )

        name = self.path
        self.setName(name)

        # r = self.getCoordinates()

    def getN(self):
        return len(self.indices)

    ## PARENT DEPENDENT METHODS HERE
    ## MOSTLY DEFINED IN SPECIFIC (e.g. sGDML) LOADERS
    def getCoordinates(self, indices=None):
        idx = self.indices
        if indices is not None:
            idx = idx[indices]
        a = self.parent.getCoordinates(indices=idx)
        return a

    def getEnergies(self, indices=None):
        idx = self.indices
        if indices is not None:
            idx = idx[indices]
        return self.parent.getEnergies(indices=idx)

    def getForces(self, indices=None):
        idx = self.indices
        if indices is not None:
            idx = idx[indices]
        return self.parent.getForces(indices=idx)

    def getPDist(self, indices=None):
        idx = self.indices
        if indices is not None:
            idx = idx[indices]
        return self.parent.getPDist(indices=idx)

    def getNAtoms(self):
        return self.parent.nAtoms

    def getChemicalFormula(self):
        return self.parent.chem

    def getElements(self):
        return self.parent.z