import hashlib
import re
import numpy as np


def md5FromArraysAndStrings(*args):
    fp = hashlib.md5()

    for arg in args:
        if isinstance(arg, str):
            d = arg.encode("utf8")
        else:
            d = arg.ravel()

        fp.update(hashlib.md5(d).digest())

    return fp.hexdigest()


def removeExtension(path):
    if "." not in path:
        return path

    if path.startswith("."):
        return path.replace(".", "")

    match = re.match("^(.*)\.(.*)$", path)
    if match is None:
        return path.replace(".", "")
    else:
        return match.group(1).replace(".", "")


class ColorGradient:
    # DEPRECATED, NOW USING VISPY'S COLORMAP
    def __init__(self, *args, minValue=0, maxValue=1):
        self.setMinMax(minValue, maxValue)
        self.colors = [np.array(x) for x in args]
        self.nPhases = len(args) - 1

    def setMinMax(self, minValue, maxValue):
        self.minValue = float(minValue)
        self.maxValue = float(maxValue)
        self.forkValue = self.maxValue - self.minValue

    def __call__(self, v):
        if isinstance(v, (list, np.ndarray)):
            return [self.getColor(x) for x in v]
        else:
            return self.getColor(v)

    def getColor(self, v):
        if v <= self.minValue:
            return self.colors[0]
        elif v >= self.maxValue:
            return self.colors[-1]

        normV = (v - self.minValue) / self.forkValue * self.nPhases
        nFork = int(normV)
        fact = normV - nFork
        c1, c2 = (self.colors[nFork], self.colors[nFork + 1])

        return c2 * fact + c1 * (1 - fact)
