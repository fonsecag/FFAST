from config.atoms import atomColors
import numpy as np
from vispy.color import Colormap
from vispy import scene


class AtomColoringModeBase:
    def __init__(self, loupe):
        self.loupe = loupe

    hasColorBar = False
    colorMap = None
    colorBarVisible = False

    def onGeometryUpdate(self):
        pass

    def updateColorBar(self, minValue="", maxValue=""):
        if (
            self.colorBarVisible
            and (self.hasColorBar)
            and (self.colorMap is not None)
        ):
            if self.loupe.colorBar is None:
                cb = scene.ColorBarWidget(
                    orientation="left",
                    cmap=self.colorMap,
                    clim=(minValue, maxValue),
                    label_color="lightgray",
                )
                self.loupe.grid.add_widget(cb, col=20)
                self.loupe.colorBar = cb

            else:
                self.loupe.showColorBar()
                cb = self.loupe.colorBar
                cb._colorbar.cmap = self.colorMap

                cb._colorbar.clim = (minValue, maxValue)
                cb._update_colorbar()

        else:
            self.loupe.hideColorBar()

    def initialise(self):
        self.onGeometryUpdate()
        self.updateColorBar()


class AtomicColoring(AtomColoringModeBase):
    def __init__(self, loupe):
        super().__init__(loupe)
        self.atomColors = None

    def onGeometryUpdate(self):
        if self.loupe.dataset is None:
            return
        z = self.loupe.dataset.getElements()
        self.atomColors = atomColors[z]

    def getColors(self):
        return self.atomColors


class ForceErrorColoring(AtomColoringModeBase):
    def __init__(self, loupe):
        super().__init__(loupe)
        self.atomColors = None
        # self.colorGradient = ColorGradient((0.1,0.9,0.1),(0.9,0.9,0.1),(0.5,0.1,0.1),(0.9,0.1,0.1))
        self.colorMap = Colormap(
            [(0.1, 0.9, 0.1), (0.9, 0.9, 0.1), (0.5, 0.1, 0.1), (0.9, 0.1, 0.1)]
        )

    hasColorBar = True
    initialisedModel = None

    def onGeometryUpdate(self):
        if self.loupe.dataset is None:
            return
        dataset = self.loupe.dataset
        model = self.getModel()

        if model is None:
            return

        if self.initialisedModel != model:
            self.initialiseModel()

        env = self.loupe.handler.env

        err = env.getData("forcesError", dataset=dataset, model=model)
        if err is None:
            self.atomColors = None
            return

        d = err.get()[self.loupe.getCurrentIndex()]
        d = np.mean(np.abs(d), axis=1)
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
            self.maxValue = np.max(d)
            self.initialisedModel = model
            self.colorBarVisible = True
            self.updateColorBar(minValue=0, maxValue=f"{self.maxValue:.2f}")
        else:
            self.colorBarVisible = False
            self.updateColorBar()

    def getColors(self):
        return self.atomColors
