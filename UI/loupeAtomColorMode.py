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
    minValue = ""
    maxValue = ""
    label = ""

    def onGeometryUpdate(self):
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
            if self.loupe.colorBar is None:
                cb = ColorBarVisual(
                    orientation="right",
                    cmap=self.colorMap,
                    clim=(self.minValue, self.maxValue),
                    label_color="lightgray",
                    label=self.label,
                    parent=self.loupe.scene,
                    parentCanvas=self.loupe.canvas,
                )
                self.colorBar = cb
                self.loupe.colorBar = cb

                # # self.loupe.grid.add_widget(cb, col=20)
                # self.loupe.colorBar = cb
                # cb.label.font_size = 9
                # for x in cb.ticks:
                #     x.font_size = 9

                # cbText = scene.visuals.Text("TESTTESTTESTTEST",parent=self.loupe.scene, color = 'lightgray')
                # cbText.font_size = 25
                # cbText.pos = 0.5, 0.3
            else:
                self.loupe.showColorBar()
                # cb = self.loupe.colorBar
                # cb._colorbar.cmap = self.colorMap

                # cb._colorbar.clim = (self.minValue, self.maxValue)
                # cb._colorbar.label = self.label
                # cb._update_colorbar()

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
            [
                (0.1, 0.9, 0.1),
                (0.9, 0.9, 0.1),
                (0.5, 0.1, 0.1),
                (0.9, 0.1, 0.1),
            ]
        )

    hasColorBar = True

    def onGeometryUpdate(self):
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
            self.colorBarVisible = True
            self.updateColorBar(
                minValue=0,
                maxValue=f"{self.maxValue:.2f}",
                label="Force MAE [kcal/mol A]",
            )
        else:
            self.colorBarVisible = False
            self.updateColorBar()

    def getColors(self):
        return self.atomColors
