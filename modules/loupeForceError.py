from UI.loupeProperties import VisualElement, CanvasProperty
from client.dataWatcher import DataWatcher
import numpy as np

DEPENDENCIES = ["basicErrors", "loupeAtoms"]


class ForceErrorColorProperty(CanvasProperty):

    key = "forceErrorColor"

    def __init__(self, *args, **kwargs):
        from vispy.color import Colormap

        super().__init__(*args, **kwargs)
        self.colorMap = Colormap(
            [
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
        data = dw.getWatchedData(dataOnly=True)
        if len(data) < 1:
            return
        de = data[0]  # just one dataset-model combination is watched
        atomicMAE = de.get("atomicMAE")
        meanAtomicMAE = np.mean(atomicMAE, axis=0)

        self.set(
            atomicMAE=atomicMAE,
            meanAtomicMAE=meanAtomicMAE,
            min=0,
            max=np.max(atomicMAE),
            meanMin=np.min(meanAtomicMAE),
            meanMax=np.max(meanAtomicMAE),
        )

    def manualUpdate(self):
        # gets called manually through an action when Coloring gets changed
        # or when the data loads
        self.clear()
        self.get()
        self.canvas.props["meanForceError"].clear()
        self.canvas.props["forceError"].clear()


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

    def onNewGeometry(self):
        if self.canvas.settings.get("atomColorType") == "Mean Force Error":
            self.canvas.elements["AtomsElement"].colorProperty = self


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
        if self.canvas.settings.get("atomColorType") == "Force Error":
            self.canvas.elements["AtomsElement"].colorProperty = self

        self.clear()


def addSettings(UIHandler, loupe):

    from UI.Templates import ObjectComboBox

    settings = loupe.settings

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

    btn = DataloaderButton(UIHandler, loupe.forceErrorDataWatcher)
    container.layout.addWidget(btn)
    btn.setFixedWidth(80)


def addDataWatcher(UIHandler, loupe):
    def updateForceErrorColor():
        prop = loupe.canvas.props["forceErrorColor"]
        prop.manualUpdate()

    dw = DataWatcher(loupe.env)
    loupe.forceErrorDataWatcher = dw
    dw.setDataDependencies("forcesError")
    dw.addCallback(updateForceErrorColor)


def loadLoupe(UIHandler, loupe):
    addDataWatcher(UIHandler, loupe)
    addSettings(UIHandler, loupe)
