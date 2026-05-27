from collections import Counter
from ase.calculators.calculator import PropertyNotImplementedError
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
    isAtomFiltered = False
    isGhost = False
    frozen = False
    isVariable = False  # Flag for uniform (False) vs variable-sized (True) datasets

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
    saveFormats = [None]

    name = "?"
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
        try:
            e = self.getEnergies()
        except (PropertyNotImplementedError, RuntimeError):
            logger.warning("Energy not available for fingerprint. Using coordinates only.")
            e = None
        try:
            f = self.getForces()
        except (PropertyNotImplementedError, RuntimeError):
            logger.warning("Forces not available for fingerprint. Using coordinates only.")
            f = None
        fp = md5FromArraysAndStrings(*(x for x in (z, r, e, f) if x is not None))

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
        self.bondSizes = covalentBonds[z][:, z] * getConfig(
            "loupeBondsLenience"
        )

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

    def getBondMatrix(self, index):
        r = self.getCoordinates(index)
        d = distance_matrix(r, r)

        return d < self.bondSizes

    def getBondIndices(self, index):
        idxs = np.argwhere(self.getBondMatrix(index))
        _, idxs = cleanBondIdxsArray(idxs)

        return idxs

    def isDependentOn(self, fp):
        # base datasets cant depend on other things, thats for subdatasets
        return False

    def isUniform(self):
        """Check if this dataset has uniform molecular structures."""
        return not self.isVariable

    def toMetaDict(self) -> dict:
        """Return lightweight metadata for RPC transfer (REMOTE_DATASET_META).

        Used by ffast-server to announce loaded datasets to connected clients
        without transferring coordinate arrays.

        Returns
        -------
        dict with keys: name, n, has_forces, is_sub
        """
        has_forces = False
        try:
            self.getForces()
            has_forces = True
        except Exception:
            pass
        return {
            "name": self.getName(),
            "n": self.getN(),
            "has_forces": has_forces,
            "is_sub": bool(self.isSubDataset),
        }

    def to_transfer_arrays(self) -> dict:
        """Serialize geometry arrays for SubDataset transfer over the RPC channel.

        Returns a dict ready to be passed to ``cluster.rpc.pack_arrays``.
        Handles uniform datasets (R shape N×natoms×3).

        Keys always present: ``n``, ``variable``, ``R``, ``E``.
        Optional keys (None when unavailable): ``F``, ``z``.

        See Also
        --------
        VariableDatasetLoader.to_transfer_arrays : override for variable datasets.
        """
        arrays: dict = {
            "n": np.array([self.getN()]),
            "variable": np.array([0]),
            "R": self.getCoordinates(),
        }
        try:
            arrays["F"] = self.getForces()
        except Exception:
            arrays["F"] = None
        try:
            arrays["z"] = self.getElements()
        except Exception:
            arrays["z"] = None
        try:
            arrays["E"] = np.asarray(
                self.getEnergies(), dtype=np.float64
            ).reshape(-1)
        except Exception:
            arrays["E"] = None
        return arrays


class VariableDatasetLoader(EventClass):
    """
    Base class for datasets with variable-sized molecules.
    Uses flat arrays with offsets for efficient storage and access.

    Data structure:
        R_flat: (total_atoms, 3)        - All positions concatenated
        F_flat: (total_atoms, 3)        - All forces concatenated
        E: (N,)                         - Energies (unchanged from uniform)
        z_flat: (total_atoms,)          - Atomic numbers concatenated
        molecule_offsets: (N+1,)        - Start indices [0, n1, n1+n2, ..., total]
    """

    isVariable = True
    isSubDataset = False
    isAtomFiltered = False
    isGhost = False
    frozen = False
    loadeeType = "dataset"

    zIntToZStr = zIntToZStr
    zStrToZInt = zStrToZInt

    datasetName = "Variable Dataset"
    datasetFileExtension = "*"
    saveFormats = [None]

    name = "?"
    loaded = False
    active = True

    def __init__(self, path):
        self.path = path

        global GLOBAL_DATASETS_COUNTER

        colors = getConfig("datasetColors")
        nColors = len(colors)
        self.color = hexToRGB(colors[GLOBAL_DATASETS_COUNTER % nColors])

        GLOBAL_DATASETS_COUNTER += 1

        # To be set by subclasses:
        self.R_flat = None          # (total_atoms, 3)
        self.F_flat = None          # (total_atoms, 3)
        self.E = None               # (N,)
        self.z_flat = None          # (total_atoms,)
        self.molecule_offsets = None  # (N+1,)
        self.N = None               # Number of molecules

    def isUniform(self):
        """Check if this dataset has uniform molecular structures."""
        return False

    def toMetaDict(self) -> dict:
        """Return lightweight metadata for RPC transfer (REMOTE_DATASET_META).

        Same interface as DatasetLoader.toMetaDict — used by ffast-server
        to announce loaded datasets without transferring coordinate arrays.

        Returns
        -------
        dict with keys: name, n, has_forces, is_sub
        """
        has_forces = False
        try:
            self.getForces()
            has_forces = True
        except Exception:
            pass
        return {
            "name": self.getName(),
            "n": self.getN(),
            "has_forces": has_forces,
            "is_sub": bool(self.isSubDataset),
        }

    def to_transfer_arrays(self) -> dict:
        """Serialize geometry arrays for SubDataset transfer over the RPC channel.

        Returns a dict ready to be passed to ``cluster.rpc.pack_arrays``.
        Uses the flat array format (R_flat, offsets, F_flat, z_flat).

        Keys always present: ``n``, ``variable``, ``R_flat``, ``offsets``.
        Optional keys (None when unavailable): ``F_flat``, ``z_flat``, ``E``.

        See Also
        --------
        DatasetLoader.to_transfer_arrays : base implementation for uniform datasets.
        """
        arrays: dict = {
            "n": np.array([self.getN()]),
            "variable": np.array([1]),
            "R_flat": self.R_flat,
            "offsets": self.molecule_offsets,
            "F_flat": self.F_flat,
            "z_flat": self.z_flat,
        }
        try:
            arrays["E"] = np.asarray(
                self.getEnergies(), dtype=np.float64
            ).reshape(-1)
        except Exception:
            arrays["E"] = None
        return arrays

    def getNAtoms(self, index=None):
        """
        Return atom count(s).

        Args:
            index: If None, returns array of all counts. If int, returns count for that molecule.

        Returns:
            int or ndarray: Atom count(s)
        """
        if index is None:
            return np.diff(self.molecule_offsets)
        else:
            return int(self.molecule_offsets[index+1] - self.molecule_offsets[index])

    def getN(self):
        """Return number of molecules/configurations."""
        return self.N

    def getCoordinates(self, indices=None):
        """
        Get atomic coordinates for molecule(s).

        Args:
            indices: None (all), int (single), or array (multiple)

        Returns:
            Single molecule: ndarray (n_atoms_i, 3)
            Multiple molecules: list of ndarrays
        """
        if indices is None:
            indices = np.arange(self.N)
        elif not isinstance(indices, np.ndarray) and not hasattr(indices, '__iter__'):
            # Single molecule - return array directly
            start = self.molecule_offsets[indices]
            end = self.molecule_offsets[indices+1]
            return self.R_flat[start:end]

        # Multiple molecules - return list
        result = []
        for idx in indices:
            start = self.molecule_offsets[idx]
            end = self.molecule_offsets[idx+1]
            result.append(self.R_flat[start:end])
        return result

    def getEnergies(self, indices=None):
        """Get energies for molecule(s)."""
        if indices is None:
            return self.E
        else:
            return self.E[indices]

    def getForces(self, indices=None):
        """
        Get forces for molecule(s).

        Returns:
            Single molecule: ndarray (n_atoms_i, 3)
            Multiple molecules: list of ndarrays
        """
        if indices is None:
            indices = np.arange(self.N)
        elif not isinstance(indices, np.ndarray) and not hasattr(indices, '__iter__'):
            # Single molecule
            start = self.molecule_offsets[indices]
            end = self.molecule_offsets[indices+1]
            return self.F_flat[start:end]

        # Multiple molecules
        result = []
        for idx in indices:
            start = self.molecule_offsets[idx]
            end = self.molecule_offsets[idx+1]
            result.append(self.F_flat[start:end])
        return result

    def getElements(self, index=None):
        """
        Get atomic numbers.

        Args:
            index: If None, returns z_flat (all atoms). If int, returns z for that molecule.

        Returns:
            ndarray: Atomic numbers
        """
        if index is None:
            return self.z_flat
        else:
            start = self.molecule_offsets[index]
            end = self.molecule_offsets[index+1]
            return self.z_flat[start:end]

    def getElementsName(self):
        """Get element names for all atoms."""
        return [zIntToZStr[x] for x in self.z_flat]

    def zToChemicalFormula(self, z):
        """Convert atomic numbers to chemical formula."""
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

    def getChemicalFormula(self):
        """Get chemical formula showing atom range."""
        atom_counts = self.getNAtoms()
        return f"Variable ({atom_counts.min()}-{atom_counts.max()} atoms)"

    def getFingerprint(self):
        """Generate fingerprint from all data."""
        # Use all flat arrays for fingerprint
        fp = md5FromArraysAndStrings(self.z_flat, self.R_flat, self.E, self.F_flat)
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
        """Initialize dataset after loading."""
        self.fingerprint = self.getFingerprint()

        name = removeExtension(os.path.basename(self.path))
        self.setName(name)

        # Note: bondSizes cannot be precomputed for variable datasets
        # Each molecule will need its own bond matrix
        self.bondSizes = None

    def getPDist(self, indices=None):
        """Get pairwise distances - handle variable sizes."""
        coords = self.getCoordinates(indices=indices)

        if isinstance(coords, list):
            # Multiple molecules
            result = []
            for r in coords:
                if len(r) >= 2:
                    result.append(pdist(r))
                else:
                    result.append(None)
            return result
        else:
            # Single molecule
            if len(coords) >= 2:
                return pdist(coords)
            else:
                return None

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
        atom_counts = self.getNAtoms()
        return [
            ("N. conf.", f"{self.getN()}"),
            ("N. atoms", f"{atom_counts.min()}-{atom_counts.max()}"),
            ("Chem. form.", self.getChemicalFormula()),
        ]

    def getInfo(self):
        # To be overwritten by specific dataset types
        return []

    def setColor(self, r, g, b):
        self.color = [r, g, b]
        self.eventPush("OBJECT_COLOR_CHANGED", self.fingerprint)

    def getBondMatrix(self, index):
        """Get bond matrix for a specific molecule."""
        r = self.getCoordinates(index)
        z = self.getElements(index)
        bondSizes = covalentBonds[z][:, z] * getConfig("loupeBondsLenience")
        d = distance_matrix(r, r)
        return d < bondSizes

    def getBondIndices(self, index):
        """Get bond indices for a specific molecule."""
        idxs = np.argwhere(self.getBondMatrix(index))
        _, idxs = cleanBondIdxsArray(idxs)
        return idxs

    def isDependentOn(self, fp):
        # base datasets cant depend on other things, thats for subdatasets
        return False


class SubDataset(DatasetLoader):
    loadeeType = "dataset"
    isSubDataset = True

    datasetName = "SubDataset"
    datasetType = "SubDataset"

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

        # Bond sizes handling: None for variable parents
        if hasattr(parentDataset, 'isVariable') and parentDataset.isVariable:
            self.bondSizes = None
        else:
            self.bondSizes = parentDataset.bondSizes

    @property
    def isVariable(self):
        """Forward isVariable flag from parent."""
        return hasattr(self.parent, 'isVariable') and self.parent.isVariable

    def updatePath(self):
        if self.modelDep is None:
            self.path = f"{self.subName},{self.parent.getName()}"
        else:
            self.path = f"{self.subName},{self.parent.getName()},{self.modelDep.getName()}"

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

    def getNAtoms(self, index=None):
        """
        Get atom count(s) for subdataset.

        Args:
            index: If None and parent is variable, returns array of counts for sub-indices.
                   If index is int, returns count for that molecule in subdataset.
        """
        if hasattr(self.parent, 'isVariable') and self.parent.isVariable:
            if index is None:
                # Return atom counts for all molecules in subdataset
                return self.parent.getNAtoms()[self.indices]
            else:
                # Remap index to parent
                parent_idx = self.indices[index]
                return self.parent.getNAtoms(parent_idx)
        else:
            # Uniform parent
            return self.parent.getNAtoms()

    def getChemicalFormula(self):
        if hasattr(self.parent, 'isVariable') and self.parent.isVariable:
            # For variable parents, show range
            atom_counts = self.getNAtoms()
            if isinstance(atom_counts, np.ndarray):
                return f"Variable ({atom_counts.min()}-{atom_counts.max()} atoms)"
            else:
                return f"{atom_counts} atoms"
        return self.parent.chem

    def getElements(self, index=None):
        """
        Get elements for subdataset.

        Args:
            index: If specified and parent is variable, get elements for that molecule.
        """
        if hasattr(self.parent, 'isVariable') and self.parent.isVariable:
            if index is not None:
                # Get elements for specific molecule in subdataset
                parent_idx = self.indices[index]
                return self.parent.getElements(parent_idx)
            else:
                # Return all elements (z_flat) from parent
                return self.parent.getElements()
        else:
            # Uniform parent
            return self.parent.z

    def getLattice(self):
        return self.parent.getLattice()

    def getElementsName(self):
        return self.parent.getElementsName()

    def getInfo(self):
        model = "None"
        if self.modelDep is not None:
            model = self.modelDep.getDisplayName()
        return [
            ("Parent", self.parent.getDisplayName()),
            ("Model", model),
            ("Plots", self.subName),
        ]

    def isDependentOn(self, obj):
        if obj is None:
            return False

        if self.parent is obj:
            return True

        if self.modelDep is obj:
            return True

        return False


class FrozenSubDataset(SubDataset):

    frozen = True
    datasetName = "SubDataset (frozen)"
    datasetType = "FrozenSubDataset"

    def __init__(self, *args):
        super().__init__(*args)

    def setIndices(self):
        pass

    def getFingerprint(
        self, parent=None, model=None, subName=None, indices=None
    ):
        if parent is None:
            parent = self.parent
        if model is None:
            model = self.modelDep
        if subName is None:
            subName = self.subName
        if indices is None:
            indices = self.indices

        if model is None:
            fp = md5FromArraysAndStrings(parent.fingerprint, subName, indices)
        else:
            fp = md5FromArraysAndStrings(
                parent.fingerprint, model.fingerprint, subName, indices
            )

        return fp


class AtomFilteredDataset(DatasetLoader):
    loadeeType = "dataset"
    isSubDataset = True
    isAtomFiltered = True

    datasetName = "Atom-Filtered Dataset"
    datasetType = "AtomFilteredDataset"

    indices = None
    loaded = False
    parent = None

    def __init__(self, parentDataset, indices):
        super().__init__("")
        self.parent = parentDataset
        self.loaded = parentDataset.loaded

        if indices is None:
            return None

        self.indices = indices
        self.updatePath()

        self.z = parentDataset.getElements()[indices]
        self.chem = self.zToChemicalFormula(self.z)

        self.bondSizes = parentDataset.bondSizes[self.indices][:, self.indices]

    def updatePath(self):
        self.path = f"{self.parent.getName()},atomFilter"

    def getFingerprint(self, parent=None, indices=None):
        if indices is None:
            indices = self.indices
        if parent is None:
            parent = self.parent

        fp = md5FromArraysAndStrings(parent.fingerprint, indices)

        return fp

    def initialise(self):
        self.fingerprint = self.getFingerprint()

        if self.fingerprint == self.parent.fingerprint:
            raise ValueError(
                f"SubDataset for dataset {self.parent} has same fingerprint. Aborted."
            )

        name = self.path
        self.setName(name)

    def getN(self):
        return self.parent.getN()

    ## PARENT DEPENDENT METHODS HERE
    ## MOSTLY DEFINED IN SPECIFIC (e.g. sGDML) LOADERS
    def getCoordinates(self, indices=None):
        a = self.parent.getCoordinates(indices=indices)
        if len(a.shape) == 3:
            return a[:, self.indices]
        else:
            return a[self.indices]

    def getEnergies(self, indices=None):
        e = self.parent.getEnergies(indices=indices)
        return e

    def getForces(self, indices=None):
        f = self.parent.getForces(indices=indices)
        if len(f.shape) == 3:
            return f[:, self.indices]
        else:
            return f[self.indices]

    def getPDist(self, indices=None):
        R = self.getCoordinates(indices=indices)
        return toDistance(R)

    def getNAtoms(self):
        return len(self.indices)

    def getChemicalFormula(self):
        return self.chem

    def getElements(self):
        return self.z

    def getLattice(self):
        return self.parent.getLattice()

    def getElementsName(self):
        return [zIntToZStr[x] for x in self.getElements()]

    def getInfo(self):
        chems = ",".join(set(self.getElementsName()))
        return [
            ("Parent", self.parent.getDisplayName()),
            ("Viewed Elements", chems),
        ]

    def isDependentOn(self, obj):
        if obj is None:
            return False

        return self.parent is obj
