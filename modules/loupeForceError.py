from UI.loupeProperties import VisualElement, CanvasProperty
from client.dataWatcher import DataWatcher
import numpy as np
from config.userConfig import getConfig

DEPENDENCIES = ["basicErrors", "loupeAtoms"]


class ColorBarVisual(VisualElement):
    def __init__(self, *args, parent=None, **kwargs):
        super().__init__(*args, **kwargs, singleElement=None)
        self.colorBar = None  # gets inited when needed
        self.sceneParent = parent

    def getSize(self):
        w, h = self.canvas.size()
        return 0.8 * h, 10

    def update(self):
        # gets called by the ForceErrorColorProperty whenever needed (manualUpdate)

        dw = self.canvas.loupe.forceErrorDataWatcher
        data = dw.getWatchedData(dataOnly=True)
        hasData = len(data) > 0

        setting = self.canvas.settings.get("atomColorType")
        prop = self.canvas.props["forceErrorColor"]
        zeroModel = prop.get("isZeroModel")

        if prop.get("atomicMAE") is None:
            hasData = False

        if hasData and (setting == "Mean Force Error"):
            label = "Mean avg. abs. force" if zeroModel else "Force MAE" #"Mean Force MAE"
            self.setParameters(
                visible=True,
                cmap=prop.colorMap,
                clim=(prop.get("meanMin"), prop.get("meanMax")),
                label=label,
            )
        elif hasData and (setting == "Force Error"):
            label = "Avg. abs. force" if zeroModel else "Force Absolute Error" #"Force MAE"
            self.setParameters(
                visible=True,
                cmap=prop.colorMap,
                clim=(prop.get("min"), prop.get("max")),
                label=label,
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

        prop = self.canvas.props["forceErrorColor"]

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

        self.canvas.grid.add_widget(self.colorBar)
        self.canvas.grid.add_widget(self.spacer)
        self.setSingleElement(self.colorBar)

        # hackey way to add spacing to the label
        cb = self.colorBar._colorbar
        _update_positions_ori = cb._update_positions

        def _update_positions_new(*args):
            _update_positions_ori(*args)
            pos = cb._label.pos
            pos[0][0] = pos[0][0] + 15

        cb._update_positions = _update_positions_new


class ForceErrorColorProperty(CanvasProperty):

    key = "forceErrorColor"

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
        # UPDATE THE DATAWATCHER'S DEPENDENCIES
        dw = self.canvas.loupe.forceErrorDataWatcher
        dw.setDatasetDependencies(self.canvas.dataset.fingerprint)
        self.clear()
        self.manualUpdate()

    def getColors(self, r):
        return self.colorMap[r]

    def generate(self):
        dw = self.canvas.loupe.forceErrorDataWatcher
        data = dw.getWatchedData()
        if len(data) < 1:
            return
        de = data[0][
            "dataEntry"
        ]  # just one dataset-model combination is watched
        atomicMAE = de.get("atomicMAE")
        if atomicMAE is None:
            return
        meanAtomicMAE = np.mean(atomicMAE, axis=0)
        perc = getConfig("loupeForceErrorPercentile") * 100

        self.set(
            atomicMAE=atomicMAE,
            meanAtomicMAE=meanAtomicMAE,
            min=0,
            max=np.percentile(atomicMAE, perc),
            meanMin=np.min(meanAtomicMAE),
            meanMax=np.max(meanAtomicMAE),
            isZeroModel=data[0]["model"].fingerprint == "zeroModel",
        )

    def manualUpdate(self):
        # gets called manually through an action when Coloring gets changed
        # or when the data loads
        self.clear()
        self.canvas.props["meanForceError"].clear()
        self.canvas.props["forceError"].clear()

        if "ColorBarVisual" in self.canvas.elements:
            self.canvas.elements["ColorBarVisual"].update()

        dw = self.canvas.loupe.forceErrorDataWatcher
        data = dw.getWatchedData(dataOnly=True)
        hasData = len(data) > 0

        setting = self.canvas.settings.get("atomColorType")
        atomsElement = self.canvas.elements["AtomsElement"]
        if hasData and (setting == "Mean Force Error"):
            atomsElement.colorProperty = self.canvas.props["meanForceError"]
        elif hasData and (setting == "Force Error"):
            atomsElement.colorProperty = self.canvas.props["forceError"]
        else:
            cp = atomsElement.colorProperty
            # remove cp if it's one of the force ones
            if (
                cp is self.canvas.props["meanForceError"]
                or cp is self.canvas.props["forceError"]
            ):
                atomsElement.colorProperty = None

        self.canvas.onNewGeometry()


class MeanForceErrorProperty(CanvasProperty):

    key = "meanForceError"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def onDatasetInit(self):
        self.clear()

    def generate(self):
        prop = self.canvas.props["forceErrorColor"]
        meanAtomicMAE = prop.get("meanAtomicMAE")
        if prop.cleared:
            return
        meanMin = prop.get("meanMin")
        meanMax = prop.get("meanMax")
        fork = meanMax - meanMin
        colors = prop.getColors((meanAtomicMAE - meanMin) / fork)
        self.set(colors=colors)


class ForceErrorProperty(CanvasProperty):

    key = "forceError"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def onDatasetInit(self):
        self.clear()

    def generate(self):
        prop = self.canvas.props["forceErrorColor"]
        atomicMAE = prop.get("atomicMAE")
        if prop.cleared:
            return
        atomicMAE = atomicMAE[self.canvas.index]
        minV = prop.get("min")
        maxV = prop.get("max")
        fork = maxV - minV
        colors = prop.getColors((atomicMAE - minV) / fork)
        self.set(colors=colors)

    def onNewGeometry(self):
        self.clear()


def addSettings(UIHandler, loupe):
    from UI.Templates import ObjectComboBox

    ## ADDING DATAWATCHER
    ## Dataset dependency set by ForceErrorColorProperty
    dw = DataWatcher(loupe.env)
    loupe.forceErrorDataWatcher = dw
    dw.setDataDependencies("forcesErrorMetrics")

    pane = loupe.getSettingsPane("ATOMS")
    comboBox = pane.settingsWidgets.get("Coloring")
    comboBox.addItems(["Mean Force Error", "Force Error"])

    loupe.addCanvasProperty(ForceErrorColorProperty)
    loupe.addCanvasProperty(MeanForceErrorProperty)
    loupe.addCanvasProperty(ForceErrorProperty)

    ## ADD BUTTONS AND SHIT
    # CONTAINER
    container = pane.addSetting(
        "Container",
        "Force Error Container",
        layout="horizontal",
        insertIndex=1,
    )
    container.setHideCondition(
        lambda: not (
            settings.get("atomColorType") == "Mean Force Error"
            or settings.get("atomColorType") == "Force Error"
        )
    )

    # MODEL SELECTOR
    modelsComboBox = ObjectComboBox(
        UIHandler, hasDatasets=False, watcher=loupe.forceErrorDataWatcher
    )
    container.layout.addWidget(modelsComboBox)

    # LOAD BUTTON
    from UI.Plots import DataloaderButton

    btn = DataloaderButton(UIHandler, dw)
    container.layout.addWidget(btn)
    btn.setFixedWidth(80)

    # ADD CALLBACKS
    def updateForceErrorColor():
        prop = loupe.canvas.props["forceErrorColor"]
        prop.manualUpdate()

    settings = loupe.settings
    settings.addParameterActions("atomColorType", updateForceErrorColor)
    dw.addCallback(updateForceErrorColor)


def loadLoupe(UIHandler, loupe):
    addSettings(UIHandler, loupe)

    loupe.addVisualElement(ColorBarVisual, "ColorBarVisual", viewParent=True)
