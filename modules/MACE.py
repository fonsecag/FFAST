from loaders.modelLoader import ModelLoaderACE
import torch
import logging

logger = logging.getLogger("FFAST")


class MACEModelLoader(ModelLoaderACE):
    singlePredict = True
    modelName = "MACE"
    modelFileExtension = "*.model"

    def __init__(self, env, path):
        super().__init__(env, path)
        self.path = path

        from mace.calculators.mace import MACECalculator

        # NOTE: This is *terrible* practice but the only way I have found
        # to make this workable on CPU. Unfortunately this will have to do.
        torchJitLoad = torch.jit.load

        def jitLoadWrapper(*args, **kwargs):
            kwargs.update(map_location="cpu")
            return torchJitLoad(*args, **kwargs)

        torch.jit.load = jitLoadWrapper

        self.calculator = MACECalculator(path, "cpu")
        self.calculator.model.to("cpu").to(torch.double)
        torch.jit.load = torchJitLoad

        dtype = None
        model = self.calculator.model
        for x in model.named_buffers():
            if x[0].startswith("interactions"):
                dtype = x[1].dtype
                break

        if dtype is None:
            logger.warn(
                f"MACE model did not find a named buffed starting with `interactions` to determined dtype. Did the versions change? Defaulting to float64"
            )
            dtype = torch.float64

        if dtype == torch.float64:
            self.dtype = "float64"
        elif dtype == torch.float32:
            self.dtype = "float32"

    def getFingerprint(self):
        from utils import md5FromArraysAndStrings

        # NOTE: This is *terrible* practice but the only way I have found
        # to make this workable on CPU. Unfortunately this will have to do.
        torchJitLoad = torch.jit.load

        def jitLoadWrapper(*args, **kwargs):
            kwargs.update(map_location="cpu")
            return torchJitLoad(*args, **kwargs)

        torch.jit.load = jitLoadWrapper

        model = torch.load(self.path, map_location="cpu")
        torch.jit.load = torchJitLoad

        lst = []
        for child in model.children():
            for param in child.parameters():
                lst.append(param.detach().cpu().numpy())

        fp = md5FromArraysAndStrings(*lst)
        return fp


def loadData(env):
    env.initialiseModelType(MACEModelLoader)
