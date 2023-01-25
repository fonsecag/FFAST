from .loader import ModelLoader
import numpy as np
from Utils.misc import md5FromArraysAndStrings
import torch 

class nequipModelLoader(ModelLoader):
    
    singlePredict = True

    def __init__(self, env, path):
        super().__init__(env, path)
        self.path = path

        from nequip.ase.nequip_calculator import nequip_calculator
        calc = nequip_calculator(path)
        self.calculator = calc

    def getFingerprint(self):
        from Utils.misc import md5FromArraysAndStrings
        from nequip.scripts.deploy import _ALL_METADATA_KEYS

        metadata = {k: "" for k in _ALL_METADATA_KEYS}
        model = torch.jit.load(self.path,_extra_files=metadata)
        lst = list(metadata.values())
        for child in model.children():
            for param in child.parameters():
                lst.append(param.detach().numpy())

        fp = md5FromArraysAndStrings(*lst)
        return fp


    def predict(self, dataset, indices=None, batchSize=50, taskID=None):
        from ase import Atoms

        if indices is None:
            R = dataset.getCoordinates()
        else:
            R = dataset.getCoordinates(indices=indices)
        z = dataset.getElements()

        E, F = [], []
        for i in range(len(R)):
            r = R[i]
            atoms = Atoms(numbers=z, positions=r)
            atoms.calc = self.calculator
            F.append(atoms.get_forces())
            E.append(atoms.get_potential_energy())

            if (taskID is not None) and (i%batchSize==0):
                self.eventPush(
                    "TASK_PROGRESS",
                    taskID,
                    progMax=len(R),
                    prog=i,
                    message=f"Nequip batch predictions",
                    quiet=True,
                    percent=True,
                )

                if not self.env.tm.isTaskRunning(taskID):
                    return None
        F = np.array(F)
        return (np.array(E).flatten(), F.reshape(F.shape[0], -1, 3))
