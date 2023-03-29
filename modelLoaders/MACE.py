from .loader import ModelLoaderACE
import numpy as np
from Utils.misc import md5FromArraysAndStrings
import torch


class MACEModelLoader(ModelLoaderACE):

    singlePredict = True
    modelName = "MACE"
    inputType = np.double

    def __init__(self, env, path):
        super().__init__(env, path)
        self.path = path

        from mace.calculators.mace import MACECalculator

        # NOTE: This is *terrible* practice but the only way I have found
        # to make this workable on CPU. Unfortunately this will have to do.
        torchJitLoad = torch.jit.load
        def jitLoadWrapper(*args, **kwargs):
            kwargs.update(map_location='cpu')
            return torchJitLoad(*args, **kwargs)
        torch.jit.load=jitLoadWrapper

        self.calculator = MACECalculator(path, "cpu")
        self.calculator.model.to("cpu").to(torch.double)
        torch.jit.load=torchJitLoad

    def getFingerprint(self):
        from Utils.misc import md5FromArraysAndStrings

        # NOTE: This is *terrible* practice but the only way I have found
        # to make this workable on CPU. Unfortunately this will have to do.
        torchJitLoad = torch.jit.load
        def jitLoadWrapper(*args, **kwargs):
            kwargs.update(map_location='cpu')
            return torchJitLoad(*args, **kwargs)
        torch.jit.load=jitLoadWrapper

        model = torch.load(self.path, map_location='cpu')
        torch.jit.load=torchJitLoad

        lst = []
        for child in model.children():
            for param in child.parameters():
                lst.append(param.detach().cpu().numpy())

        fp = md5FromArraysAndStrings(*lst)
        return fp
