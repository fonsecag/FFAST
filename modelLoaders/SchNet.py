from .loader import ModelLoader
import numpy as np
from Utils.misc import md5FromArraysAndStrings


class SchNetModelLoader(ModelLoader):
    """
    ModelLoader subclass specific to sGDML models.
    """

    # when True, implements just one predict function for forces and energies
    # when False, it's separate
    singlePredict = True

    def __init__(self, env, path, *args, **kwargs):
        """
        Initialises the ModelLoader given a path to the model. All methods
        that are only called once (i.e. loading the model) are performed here.

        Args:
            path (str): path to the model
        """
        super().__init__(env, path, *args, **kwargs)

        import torch

        self.model = torch.load(path, map_location=torch.device("cpu"))

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

        import schnetpack

        # import schnetpack.transform as trn
        # see https://schnetpack.readthedocs.io/en/dev/tutorials/tutorial_03_force_models.html#Using-the-model
        # except it doesnt work :)
        from ase import Atoms

        if indices is None:
            R = dataset.getCoordinates()
        else:
            R = dataset.getCoordinates(indices=indices)
        z = dataset.getElements()

        E, F = [], []

        # batch size is useless here because of how this whole Atoms conversion
        # nBatches = len(R) // batchSize + 1
        # rBatches = np.array_split(R, nBatches)
        # nBatches = len(rBatches)

        # converter = schnetpack.interfaces.AtomsConverter(
        #     neighbor_list=trn.ASENeighborList(cutoff=5.0), dtype=torch.float32
        # )

        for i in range(len(R)):
            atoms = Atoms(numbers=z, positions=R[i])
            # inputs = converter(atoms)
            inputs = atoms
            results = self.model(inputs)
            e = results["energy"].detach().cpu().numpy()
            f = results["forces"].detach().cpu().numpy()
            E.append(e)
            F.append(f)

            if taskID is not None:
                self.eventPush(
                    "TASK_PROGRESS",
                    taskID,
                    progMax=nBatches,
                    prog=i,
                    message=f"SchNet batch predictions",
                    quiet=True,
                    percent=True,
                )

                if not self.env.tm.isTaskRunning(taskID):
                    return None

        E, F = np.array(E), np.array(F)

        return E, F.reshape(F.shape[0], -1, 3)

    def getFingerprint(self):
        """
        Mandatory method which should output a string acting as a unique
        identifier for this model.

        Returns:
            s (str): Unique fingerprint
        """

        # TODO: not unique enough, thats just architecture!!
        fp = md5FromArraysAndStrings(str(self.model))

        return fp
