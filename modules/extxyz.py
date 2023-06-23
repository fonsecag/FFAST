import numpy as np
from loaders.datasetLoader import DatasetLoader
import ase.io
from collections.abc import Iterable


class aseDatasetLoader(DatasetLoader):
    datasetName = "ase"
    datasetFileExtension = "*"

    def __init__(self, path, *args, **kwargs):
        super().__init__(path)
        self.atomsList = ase.io.read(path, index=":")
        self.N = len(self.atomsList)

        exAtoms = self.atomsList[0]  # assumes all the same molecule!!

        self.nAtoms = len(exAtoms)
        self.z = exAtoms.get_atomic_numbers()
        self.chem = self.zToChemicalFormula(self.z)

    def getN(self):
        return self.N

    def getNAtoms(self):
        return self.nAtoms

    def getChemicalFormula(self):
        return self.chem

    def getCoordinates(self, indices=None):
        # probably should just do it once at the start and save it as np arrays?
        if indices is None:
            indices = np.arange(self.N)
        elif not isinstance(indices, Iterable):
            return self.atomsList[indices].get_positions()

        R = []
        for idx in indices:
            R.append(self.atomsList[idx].get_positions())

        return np.array(R)

    def getEnergies(self, indices=None):
        # probably should just do it once at the start and save it as np arrays?
        if indices is None:
            indices = np.arange(self.N)
        elif not isinstance(indices, Iterable):
            return self.atomsList[indices].get_potential_energy()

        R = []
        for idx in indices:
            R.append(self.atomsList[idx].get_potential_energy())

        return np.array(R)

    def getForces(self, indices=None):
        # probably should just do it once at the start and save it as np arrays?
        if indices is None:
            indices = np.arange(self.N)
        elif not isinstance(indices, Iterable):
            return self.atomsList[indices].get_forces()

        R = []
        for idx in indices:
            R.append(self.atomsList[idx].get_forces())

        return np.array(R)

    def getElements(self):
        return self.z

    def getLattice(self):
        return


def loadData(env):
    env.initialiseDatasetType(aseDatasetLoader)
