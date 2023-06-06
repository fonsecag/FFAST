from collections import Counter
import numpy as np
import os
from utils import md5FromArraysAndStrings, removeExtension
import logging
from events import EventClass
from scipy.spatial.distance import pdist
from config.userConfig import getConfig
from utils import hexToRGB
from config.atoms import zIntToZStr, zStrToZInt
from config.atoms import covalentBonds
from scipy.spatial import distance_matrix
from utils import cleanBondIdxsArray

logger = logging.getLogger("FFAST")
GLOBAL_DATASETS_COUNTER = 0


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

        global GLOBAL_DATASETS_COUNTER

        colors = getConfig("datasetColors")
        nColors = len(colors)
        self.color = hexToRGB(colors[GLOBAL_DATASETS_COUNTER % nColors])

        GLOBAL_DATASETS_COUNTER += 1

    loadeeType = "dataset"

    zIntToZStr = zIntToZStr
    zStrToZInt = zStrToZInt

    datasetName = "N/A"
    datasetFileExtension = "*"

    name = "N/A"
    loaded = False
    active = True

    def getElementsName(self):
        return [zIntToZStr[x] for x in self.getElements()]

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
            self.eventPush("OBJECT_NAME_CHANGED", self.fingerprint)

    def getName(self):
        return self.name

    def initialise(self):
        self.fingerprint = self.getFingerprint()

        name = removeExtension(os.path.basename(self.path))
        self.setName(name)

        z = self.getElements()
        self.bondSizes = covalentBonds[z, z] * getConfig("loupeBondsLenience")

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

    def getBaseInfo(self):
        return [
            ("N. conf.", f"{self.getN()}"),
            ("N. atoms", f"{self.getNAtoms()}"),
            ("Chem. form.", self.getChemicalFormula()),
        ]

    def getInfo(self):
        # specific info to be overwritten by specific dataset types
        return []

    def setColor(self, r, g, b):
        self.color = [r, g, b]
        self.eventPush("OBJECT_COLOR_CHANGED", self.fingerprint)

    def getBondIndices(self, index):

        r = self.getCoordinates(index)
        d = distance_matrix(r, r)

        idxs = np.argwhere(d < self.bondSizes)
        _, idxs = cleanBondIdxsArray(idxs)

        return idxs


class SubDataset(DatasetLoader):
    loadeeType = "dataset"
    isSubDataset = True

    datasetType = "Sub-dataset"
    loaded = False
    modelDep = None
    parent = None

    def __init__(self, parentDataset, model, indices, subName):
        super().__init__("")
        self.parent = parentDataset
        self.modelDep = model
        self.subName = subName
        self.loaded = parentDataset.loaded

        if indices is None:
            indices = np.array([0])

        self.indices = indices
        self.updatePath()

        self.bondSizes = parentDataset.bondSizes

    def updatePath(self):
        self.path = (
            f"{self.subName},{self.parent.getName()},{self.modelDep.getName()}"
        )

    def setIndices(self, indices):
        if indices is None:
            indices = np.array([0])
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

    def getLattice(self):
        return self.parent.getLattice()

    def getElementsName(self):
        return self.parent.getElementsName()