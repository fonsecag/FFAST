from config.atoms import atomColors
import numpy as np
from vispy.color import Colormap
from vispy import scene
from UI.utils import ColorBarVisual


class AtomColoringModeBase:
    def __init__(self, loupe):
        self.loupe = loupe

    hasColorBar = False
    colorMap = None
    colorBarVisible = False
    minValue = 0
    maxValue = 0
    label = ""

    def onGeometryUpdate(self):
        self._onGeometryUpdate()

    def _onGeometryUpdate(self):
        pass

    def updateColorBar(self, minValue=None, maxValue=None, label=None):
        if minValue is not None:
            self.minValue = minValue
        if maxValue is not None:
            self.maxValue = maxValue
        if label is not None:
            self.label = label
        if (
            self.colorBarVisible
            and (self.hasColorBar)
            and (self.colorMap is not None)
        ):  
            maxV = f'{self.maxValue:.2f}'
            minV = f'{self.minValue:.2f}'
            if self.loupe.colorBar is None:
                cb = ColorBarVisual(
                    orientation="right",
                    cmap=self.colorMap,
                    clim=(minV, maxV),
                    label_color="lightgray",
                    label=self.label,
                    parent=self.loupe.scene,
                    parentCanvas=self.loupe.canvas,
                )
                self.colorBar = cb
                self.loupe.colorBar = cb
            else:
                self.loupe.showColorBar()
                cb = self.loupe.colorBar
                cb.visual.cmap = self.colorMap
                cb.visual.clim = (minV, maxV)
                cb.onUpdate()
        else:
            self.loupe.hideColorBar()

    def initialise(self):
        self.onGeometryUpdate()
        self.updateColorBar()


class AtomicColoring(AtomColoringModeBase):
    def __init__(self, loupe):
        super().__init__(loupe)
        self.atomColors = None

    def _onGeometryUpdate(self):
        if self.loupe.dataset is None:
            return
        z = self.loupe.dataset.getElements()
        self.atomColors = atomColors[z]

    def getColors(self):
        return self.atomColors


class ForceErrorColoring(AtomColoringModeBase):
    def __init__(self, loupe, average = True):
        super().__init__(loupe)
        self.atomColors = None
        # self.colorGradient = ColorGradient((0.1,0.9,0.1),(0.9,0.9,0.1),(0.5,0.1,0.1),(0.9,0.1,0.1))
        self.colorMap = Colormap(
            [
                (0.1, 0.9, 0.1),
                (0.9, 0.9, 0.1),
                (0.5, 0.1, 0.1),
                (0.9, 0.1, 0.1),
            ]
        )
        self.average = average

    hasColorBar = True

    def _onGeometryUpdate(self):
        if self.loupe.dataset is None:
            return
        dataset = self.loupe.dataset
        model = self.getModel()

        self.initialiseModel()

        if model is None:
            return

        env = self.loupe.handler.env

        err = env.getData("forcesError", dataset=dataset, model=model)
        if err is None:
            self.atomColors = None
            return

        if self.average:
            d = self.fixedValues
        else:
            d = err.get()[self.loupe.getCurrentIndex()]
            d = np.mean(np.abs(d), axis=1)
        d = (d - self.minValue) / (self.maxValue - self.minValue)
        colors = self.colorMap[d]
        self.atomColors = colors

    def getModel(self):
        model = self.loupe.colorTabModelCB.currentKey()
        if len(model) == 0:
            return None
        else:
            return model[0]

    def initialiseModel(self):
        if self.loupe.dataset is None:
            return
        model = self.getModel()
        if model is None:
            return

        env = self.loupe.handler.env
        dataset = self.loupe.dataset
        err = env.getData("forcesError", dataset=dataset, model=model)
        if err is not None:
            d = np.mean(np.abs(err.get()), axis=2)
            if self.average:
                d = np.mean(d, axis = 0)
                self.fixedValues = d
            self.maxValue = np.max(d)
            self.minValue = np.min(d)
            self.colorBarVisible = True
            self.updateColorBar(
                minValue=self.minValue,
                maxValue=self.maxValue,
                label="Force MAE [kcal/mol A]",
            )
        else:
            self.colorBarVisible = False
            self.updateColorBar()

    def getColors(self):
        return self.atomColors
