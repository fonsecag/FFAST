from loaders.modelLoader import ModelLoader
import numpy as np
from utils import md5FromArraysAndStrings
from loaders.datasetLoader import DatasetLoader


class sGDMLModelLoader(ModelLoader):
    """
    ModelLoader subclass specific to sGDML models.
    """

    # when True, implements just one predict function for forces and energies
    # when False, it's separate
    singlePredict = True
    modelName = "sGDML"
    modelFileExtension = "*.npz"

    def __init__(self, env, path, *args, **kwargs):
        """
        Initialises the ModelLoader given a path to the model. All methods
        that are only called once (i.e. loading the model) are performed here.

        Args:
            path (str): path to the model
        """
        super().__init__(env, path, *args, **kwargs)

        from sgdml.predict import GDMLPredict

        model = np.load(path, allow_pickle=True)
        self.modelInfo = model
        self.fpArrays = (model["perms"], model["R_d_desc_alpha"])
        self.model = GDMLPredict(model)

    def predict(self, dataset, indices=None, batchSize=50, taskID=None):
        """
        Prediction function for energies and forces using the loaded sGDML
        model.

        Args:
            dataset (DatasetLoader): DatasetLoader object from which to
                calculate predictions.
            indices (array, optional): Array of indices at which to predict
                energies and forces. Defaults to None.

        Returns:
            E (array): Nx1 array containing calculated energies.
            F (array): NxMx3 array containing calculated forces.
        """

        if indices is None:
            R = dataset.getCoordinates()
        else:
            R = dataset.getCoordinates(indices=indices)

        E, F = [], []
        nBatches = len(R) // batchSize + 1
        rBatches = np.array_split(R, nBatches)
        nBatches = len(rBatches)

        for i in range(nBatches):
            r = rBatches[i]
            (e, f) = self.model.predict(r.reshape((r.shape[0], -1)))
            E.append(e)
            F.append(f)

            if taskID is not None:
                self.eventPush(
                    "TASK_PROGRESS",
                    taskID,
                    progMax=nBatches,
                    prog=i,
                    message=f"sGDML batch predictions",
                    quiet=True,
                    percent=True,
                )

                if not self.env.tm.isTaskRunning(taskID):
                    return None

        E, F = np.concatenate(E), np.concatenate(F)

        return E, F.reshape(F.shape[0], -1, 3)

    def getFingerprint(self):
        """
        Mandatory method which should output a string acting as a unique
        identifier for this model.

        Returns:
            s (str): Unique fingerprint
        """

        fp = md5FromArraysAndStrings(*self.fpArrays)

        return fp

    def getInfo(self):
        return [
            ("N. perms", f"{len(self.modelInfo['perms'])}"),
            ("Sigma", f"{self.modelInfo['sig']}"),
            ("N. atoms", f"{self.model.n_atoms}"),
            ("N. train", f"{len(self.modelInfo['idxs_train'])}"),
            ("Code ver.", f"{self.modelInfo['code_version']}"),
        ]


class sGDMLDatasetLoader(DatasetLoader):
    datasetName = "sGDML"
    datasetFileExtension = "*.npz"

    def __init__(self, path, *args, **kwargs):
        super().__init__(path)
        self.data = np.load(path, allow_pickle=True)
        self.chem = self.zToChemicalFormula(self.data["z"])

        data = {key.lower(): value for key, value in self.data.items()}

        self.R = data["r"]
        self.E = data["e"]
        self.F = data["f"]
        self.z = data["z"]
        self.N = self.R.shape[0]
        self.nAtoms = self.R.shape[1]

        if "lattice" in data:
            self.lattice = data["lattice"]
        else:
            self.lattice = np.eye(3)

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

    def getLattice(self):
        return self.lattice

    @staticmethod
    def saveDataset(dataset, path, format=None, taskID=None):
        data = {
            "R": dataset.getCoordinates(),
            "E": dataset.getEnergies(),
            "F": dataset.getForces(),
            "z": dataset.getElements(),
            "lattice": dataset.getLattice(),  # not yet used at all
            "name": path,
        }

        md5 = md5FromArraysAndStrings(data["R"], data["E"], data["F"])
        data["md5"] = md5

        np.savez_compressed(path, **data)


def loadData(env):
    env.initialiseModelType(sGDMLModelLoader)
    env.initialiseDatasetType(sGDMLDatasetLoader)
