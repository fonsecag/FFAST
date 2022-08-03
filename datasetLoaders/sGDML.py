from .loader import DatasetLoader
import numpy as np


class sGDMLDatasetLoader(DatasetLoader):
    def __init__(self, path, *args, **kwargs):
        super().__init__(path)
        self.data = np.load(path, allow_pickle=True)
        self.chem = self.zToChemicalFormula(self.data["z"])
        self.R = self.data["R"]
        self.E = self.data["E"]
        self.F = self.data["F"]
        self.z = self.data["z"]
        self.N = self.R.shape[0]
        self.nAtoms = self.R.shape[1]

    def getN(self):
        return self.N

    def getNAtoms(self):
        return self.nAtoms

    def getChemicalFormula(self):
        return self.chem

    def getCoordinates(self, indices=None):
        if indices is None:
            return self.R
        else:
            return self.R[indices]

    def getEnergies(self, indices=None):
        if indices is None:
            return self.E.reshape(-1)
        else:
            return self.E[indices].reshape(-1)

    def getForces(self, indices=None):
        if indices is None:
            return self.F
        else:
            return self.F[indices]

    def getElements(self):
        return self.z
