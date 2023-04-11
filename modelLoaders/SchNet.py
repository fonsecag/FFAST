from .loader import ModelLoader
import numpy as np
from utils import md5FromArraysAndStrings


class SchNetModelLoader(ModelLoader):
    """
    ModelLoader subclass specific to sGDML models.
    """

    # when True, implements just one predict function for forces and energies
    # when False, it's separate
    singlePredict = True
    modelName = "SchNet"

    def __init__(self, env, path, *args, **kwargs):
        """
        Initialises the ModelLoader given a path to the model. All methods
        that are only called once (i.e. loading the model) are performed here.

        Args:
            path (str): path to the model
        """
        super().__init__(env, path, *args, **kwargs)

        import torch
        import schnetpack

        self.model = torch.load(path, map_location=torch.device("cpu"))
        self.model.requires_stress = False
        for name, mod in self.model.named_modules():
            if isinstance(mod, schnetpack.atomistic.output_modules.Atomwise):
                mod.stress = None

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

        import schnetpack, os

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
        molecules, props = ([], [])
        for i in range(len(R)):
            r = R[i]
            atoms = Atoms(numbers=z, positions=r)
            molecules.append(atoms)
            props.append({"energy": 0, "forces": np.zeros(r.shape)})

        path = os.path.join(
            "temp", f"{self.fingerprint}_{dataset.fingerprint}.db"
        )
        if os.path.exists(path):
            os.remove(path)
        d = schnetpack.AtomsData(
            path, available_properties=["energy", "forces"]
        )
        d.add_systems(molecules, props)

        # molecules = schnetpack.AtomsData(molecules)
        loader = schnetpack.AtomsLoader(d, batch_size=10)
        for count, batch in enumerate(loader):
            results = self.model(batch)
            e = results["energy"].detach().cpu().numpy()
            f = results["forces"].detach().cpu().numpy()
            E.append(e)
            F.append(f)

            if taskID is not None:
                self.eventPush(
                    "TASK_PROGRESS",
                    taskID,
                    progMax=len(loader),
                    prog=count,
                    message=f"SchNet batch predictions",
                    quiet=True,
                    percent=True,
                )

                if not self.env.tm.isTaskRunning(taskID):
                    return None

        E, F = np.concatenate(E), np.concatenate(F)

        return (E.flatten(), F.reshape(F.shape[0], -1, 3))

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
