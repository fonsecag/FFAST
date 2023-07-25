from UI.loupeProperties import VisualElement, CanvasProperty
from client.dataWatcher import DataWatcher
import numpy as np
from config.userConfig import getConfig

DEPENDENCIES = ["loupeAtoms", "loupeForceError"]


class ColorBarVisual(VisualElement):
    # copied and re-implemented from loupeForceError
    # not the cleanest way to do it *at all* but hey, short on time...
    def __init__(self, *args, parent=None, **kwargs):
        super().__init__(*args, **kwargs, singleElement=None)
        self.colorBar = None  # gets inited when needed
        self.sceneParent = parent

    def getSize(self):
        w, h = self.canvas.size()
        return 0.8 * h, 10

    def update(self):
        # gets called by the Displacement Property whenever needed (manualUpdate)
        setting = self.canvas.settings.get("atomColorType")
        prop = self.canvas.props["displacementColor"]

        if setting == "Total Displacement":
            self.setParameters(
                visible=True,
                cmap=prop.colorMap,
                clim=(prop.get("minTot"), prop.get("maxTot")),
                label=setting,
            )
        elif setting == "Mean Displacement":
            self.setParameters(
                visible=True,
                cmap=prop.colorMap,
                clim=(prop.get("minMean"), prop.get("maxMean")),
                label=setting,
            )
        else:
            self.setParameters(visible=False)

    def setParameters(
        self, visible=False, cmap=None, clim=(0, 1), label="N/A"
    ):
        if self.colorBar is None:
            self.initColorBar()

        if visible and self.hidden:
            self.show()
        elif (not visible) and (not self.hidden):
            self.hide()

        if not visible:
            return

        self.colorBar.cmap = cmap
        self.colorBar.clim = (f"{clim[0]:.2f}", f"{clim[1]:.2f}")
        self.colorBar.label.text = label

    def initColorBar(self):
        from vispy import scene

        prop = self.canvas.props["displacementColor"]

        # preliminary, gets changed by .update when afterwards
        self.colorBar = scene.ColorBarWidget(
            # parent=self.sceneParent,
            cmap=prop.colorMap,  # gets updated by ForceErrorColorProperty
            label_color="lightgray",
            label="N/A",
            clim=(0, 1),
            orientation="right",
            border_color="lightgray",
            border_width=1,
        )
        self.colorBar.width_max = 70
        self.spacer = scene.Widget()

        self.canvas.gridDisplacement.add_widget(self.colorBar)
        self.canvas.gridDisplacement.add_widget(self.spacer)
        self.setSingleElement(self.colorBar)

        # hackey way to add spacing to the label
        cb = self.colorBar._colorbar
        _update_positions_ori = cb._update_positions

        def _update_positions_new(*args):
            _update_positions_ori(*args)
            pos = cb._label.pos
            pos[0][0] = pos[0][0] + 15

        cb._update_positions = _update_positions_new


class TotDisplacementColorProperty(CanvasProperty):
    key = "totDisplacementColor"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def onDatasetInit(self):
        self.clear()

    def generate(self):
        prop = self.canvas.props["displacementColor"]
        colors = prop.getTotColors()
        self.set(colors=colors)


class MeanDisplacementColorProperty(CanvasProperty):
    key = "meanDisplacementColor"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def onDatasetInit(self):
        self.clear()

    def generate(self):
        prop = self.canvas.props["displacementColor"]
        colors = prop.getMeanColors()
        self.set(colors=colors)


class DisplacementColorProperty(CanvasProperty):

    key = "displacementColor"

    def __init__(self, *args, **kwargs):
        from vispy.color import Colormap

        super().__init__(*args, **kwargs)

        self.colorMap = Colormap(
            [
                (0.1, 0.1, 0.9),
                (0.1, 0.9, 0.1),
                (0.9, 0.9, 0.1),
                (0.5, 0.1, 0.1),
                (0.9, 0.1, 0.1),
            ]
        )

    def onDatasetInit(self):
        self.clear()

    def getMeanColors(self):
        return self.colorMap[
            (self.get("dMean") - self.get("minMean")) / self.get("forkMean")
        ]

    def getTotColors(self):
        return self.colorMap[
            (self.get("dTot") - self.get("minTot")) / self.get("forkTot")
        ]

    def generate(self):
        dataset = self.canvas.dataset
        R = dataset.getCoordinates()

        # total displacement
        diff = R[-1] - R[0]  # nA, 3
        dTot = np.sqrt(np.mean(diff ** 2, axis=1))  # nA
        minTot, maxTot = np.min(dTot), np.max(dTot)
        forkTot = maxTot - minTot

        # average displacement
        diff = R[1:] - R[:-1]  # N, nA, 3
        dVec = np.sqrt(np.mean(diff ** 2, axis=2))  # N, nA
        dMean = np.mean(dVec, axis=0)
        minMean, maxMean = np.min(dMean), np.max(dMean)
        forkMean = maxMean - minMean

        self.set(
            dTot=dTot,
            minTot=minTot,
            maxTot=maxTot,
            forkTot=forkTot,
            dMean=dMean,
            minMean=minMean,
            maxMean=maxMean,
            forkMean=forkMean,
        )

    def manualUpdate(self):
        # gets called manually through an action when Coloring gets changed
        # or when the data loads

        if "ColorBarVisualDisplacement" in self.canvas.elements:
            self.canvas.elements["ColorBarVisualDisplacement"].update()

        setting = self.canvas.settings.get("atomColorType")
        atomsElement = self.canvas.elements["AtomsElement"]

        if setting == "Total Displacement":
            atomsElement.colorProperty = self.canvas.props[
                "totDisplacementColor"
            ]
        elif setting == "Mean Displacement":
            atomsElement.colorProperty = self.canvas.props[
                "meanDisplacementColor"
            ]
        else:
            cp = atomsElement.colorProperty
            # remove cp if it's one of the force ones
            if (
                cp is self.canvas.props["totDisplacementColor"]
                or cp is self.canvas.props["meanDisplacementColor"]
            ):
                atomsElement.colorProperty = None

        self.canvas.onNewGeometry()


def loadLoupe(UIHandler, loupe):

    pane = loupe.getSettingsPane("ATOMS")
    comboBox = pane.settingsWidgets.get("Coloring")
    comboBox.addItems(["Total Displacement", "Mean Displacement"])

    # add a new grid to put the visuals on
    loupe.canvas.gridDisplacement = loupe.canvas.newGrid()

    loupe.addCanvasProperty(DisplacementColorProperty)
    loupe.addCanvasProperty(TotDisplacementColorProperty)
    loupe.addCanvasProperty(MeanDisplacementColorProperty)
    loupe.addVisualElement(
        ColorBarVisual, "ColorBarVisualDisplacement", viewParent=True
    )

    # callbacks
    def updateDisplacementColor():
        prop = loupe.canvas.props["displacementColor"]
        prop.manualUpdate()

    settings = loupe.settings
    settings.addParameterActions("atomColorType", updateDisplacementColor)
