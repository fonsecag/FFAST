import hashlib
import re


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
    def __init__(self, *args, minValue=0, maxValue=1):
        self.setMinMax(minValue, maxValue)
        self.colors = args
        self.nPhases = len(args) - 1

    def setMinMax(minValue, maxValue):
        self.minValue = float(minValue)
        self.maxValue = float(maxValue)
        self.forkValue = self.maxValue - self.minValue

    def __call__(self, v):
        normV = (v - self.minValue)/self.forkValue
        nFork = int(normV)
        

