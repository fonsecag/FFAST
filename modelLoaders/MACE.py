from .loader import ModelLoaderACE
import numpy as np
from Utils.misc import md5FromArraysAndStrings
import torch


class MACEModelLoader(ModelLoaderACE):
    singlePredict = True
    modelName = "MACE"

    def __init__(self, env, path):
        super().__init__(env, path)
        self.path = path

        from mace.calculators.mace import MACECalculator

        self.calculator = MACECalculator(path, "cpu")
        self.calculator.model.to(torch.float32).to("cpu")

    def getFingerprint(self):
        from Utils.misc import md5FromArraysAndStrings

        model = torch.load(self.path)
        lst = []
        for child in model.children():
            for param in child.parameters():
                lst.append(param.detach().cpu().numpy())

        fp = md5FromArraysAndStrings(*lst)
        return fp
