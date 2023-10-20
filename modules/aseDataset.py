import numpy as np
from loaders.datasetLoader import DatasetLoader
import ase.io
from collections.abc import Iterable


class aseDatasetLoader(DatasetLoader):
    datasetName = "ase"
    datasetFileExtension = "*"
    saveFormats = ["db", "xyz", "extxyz", "traj", "vasp", "dftb"]

    def __init__(self, path, *args, **kwargs):
        super().__init__(path)
        self.atomsList = ase.io.read(path, index=":")
        self.N = len(self.atomsList)

        exAtoms = self.atomsList[0]  # assumes all the same molecule!!

        self.nAtoms = len(exAtoms)
        self.z = exAtoms.get_atomic_numbers()

        if hasattr(exAtoms, "cell"):
            self.lattice = exAtoms.cell
        else:
            self.lattice = None

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
        return None

    @staticmethod
    def saveDataset(dataset, path, format=None, taskID=None):
        from ase import Atoms
        from ase.calculators.calculator import Calculator

        R, F = dataset.getCoordinates(), dataset.getForces()
        E, zStr = dataset.getEnergies(), dataset.getElementsName()

        atoms = []

        class FakeCalc(Calculator):
            def __init__(self):
                pass

        for i in range(R.shape[0]):
            atom = Atoms(positions=R[i], symbols=zStr)
            atom.calc = FakeCalc()
            atom.calc.results = {"forces": F[i], "energy": E[i]}
            atoms.append(atom)

        ase.io.write(path, atoms, format=format)


def loadData(env):
    env.initialiseDatasetType(aseDatasetLoader)
