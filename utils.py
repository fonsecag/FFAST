import hashlib
import re
import numpy as np
import glob
import importlib
import os
import logging

logger = logging.getLogger("FFAST")


def setupLogger():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
        handlers=[logging.FileHandler("debug.log"), logging.StreamHandler()],
    )


def kahnsAlgorithm(graph):
    degreeMap = {node: 0 for node in graph}

    for name, dependencies in graph.items():
        for dep in dependencies:
            degreeMap[dep] += 1

    queue = [node for node in graph if degreeMap[node] == 0]
    sortedNodes = []

    while queue:
        node = queue.pop(0)
        sortedNodes.append(node)

        for dep in graph[node]:
            degreeMap[dep] -= 1
            if degreeMap[dep] == 0:
                queue.append(dep)

    sortedNodes.reverse()
    if len(sortedNodes) == len(graph):
        return sortedNodes, degreeMap
    else:
        return None, degreeMap


def checkForInvalidDependencies(graph):
    validNodes = set(graph.keys())
    cleanedGraph = {}

    for node, dependencies in graph.items():
        valid = True
        for dep in dependencies:
            if dep not in validNodes:
                logger.error(
                    f"Module {node} cannot be loaded due to depending on inexistant module {dep}"
                )
                valid = False
        if valid:
            cleanedGraph[node] = dependencies

    if len(cleanedGraph) < len(graph):
        # need to cascade down if a node is removed
        return checkForInvalidDependencies(cleanedGraph)
    else:
        return cleanedGraph


def cleanBondIdxsArray(arr):
    try:
        s = set()
        for x in arr:
            if x[0] == x[1]:
                continue
            elif x[0] < x[1]:
                s.add((x[0], x[1]))
            else:
                s.add((x[1], x[0]))

    except Exception as e:
        logger.exception(
            f"Tried to clean bond arr, but failed for: {e}. Array/List needs to be Nx2"
        )
        return False, None

    return True, list(s)


def loadModules(UI, env, headless=False):
    mods = {}
    depGraph = {}

    for path in glob.glob(os.path.join("modules", "*.py")):
        name = os.path.basename(path).replace(".py", "")

        spec = importlib.util.spec_from_file_location(f"module_{name}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        mods[name] = mod
        depGraph[name] = mod.DEPENDENCIES

    depGraph = checkForInvalidDependencies(depGraph)
    order, degreeMap = kahnsAlgorithm(depGraph)
    if order is None:
        logger.error(
            f"Cycle in module dependency graph. Remaining nodes: {degreeMap}"
        )
        return

    for name in order:
        mod = mods[name]
        if hasattr(mod, "loadData"):
            mod.loadData(env)
        if (not headless) and hasattr(mod, "loadUI"):
            mod.loadUI(UI, env)
        if (not headless) and hasattr(mod, "loadLoupe"):
            UI.registerLoupeModule(mod.loadLoupe)


def md5FromArraysAndStrings(*args):
    fp = hashlib.md5()

    for arg in args:
        if isinstance(arg, str):
            d = arg.encode("utf8")
        elif isinstance(arg, np.ndarray):
            d = arg.ravel()
        else:
            continue
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


def rgbToHex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def hexToRGB(sHex):
    sHex = sHex.lstrip("#")

    r = int(sHex[0:2], 16)
    g = int(sHex[2:4], 16)
    b = int(sHex[4:6], 16)

    # return the RGB tuple as an array with values between 0 and 255
    return [r, g, b]


def mixColors(c1, c2):
    return np.array((np.array(c1) + np.array(c2)) / 2).astype(int)


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
