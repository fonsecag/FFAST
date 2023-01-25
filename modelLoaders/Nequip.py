from .loader import ModelLoaderACE
from .loader import ModelLoaderACE
import numpy as np
from Utils.misc import md5FromArraysAndStrings
import torch


class NequipModelLoader(ModelLoaderACE):

    singlePredict = True
    modelName = "Nequip"

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
        model = torch.jit.load(self.path, _extra_files=metadata)
        lst = list(metadata.values())
        for child in model.children():
            for param in child.parameters():
                lst.append(param.detach().numpy())

        fp = md5FromArraysAndStrings(*lst)
        return fp
