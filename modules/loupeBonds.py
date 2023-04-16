import numpy as np
from config.userConfig import getConfig
from functools import partial
import logging
from utils import cleanBondIdxsArray
from UI.loupeProperties import VisualElement, CanvasProperty, AtomSelectionBase

logger = logging.getLogger("FFAST")
DEPENDENCIES = ["loupeCamera"]


class BondsElement(VisualElement):
    def __init__(self, *args, parent=None, width=200, **kwargs):
        from vispy import scene

        self.lines = scene.visuals.Line(
            pos=None,
            parent=parent,
            color=getConfig("loupeBondsColor"),
            width=width,
            connect="segments",
            antialias=True,
        )
        super().__init__(*args, **kwargs, singleElement=self.lines)
        self.width = width

    def onNewGeometry(self):
        self.queueVisualRefresh()

    def onCameraChange(self):
        dist = self.canvas.props["camera"].get("distance")

        if dist is None:
            dist = 1

        self.lines.set_data(width=self.width / dist)

    def _draw(self, picking=False, pickingColors=None):

        bondType = self.canvas.settings.get("bondType")
        if bondType == "Dynamic":
            bonds = self.canvas.props["dynamicBonds"].get("R")
        elif bondType == "Fixed":
            bondIndices = self.canvas.settings.get("bondIndices")
            if bondIndices is None:
                bonds = self.canvas.props["fixedBonds"].get("R")

        width = self.canvas.props["camera"].get("distance")

        if width is None:
            width = 1

        if bonds is None:
            self.lines.set_data(width=0)
        else:
            self.lines.set_data(pos=bonds, width=self.width / width)


class DynamicBondsProperty(CanvasProperty):

    key = "dynamicBonds"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def onNewGeometry(self):
        self.clear()

    def generate(self):
        R = self.canvas.getCurrentR()
        bonds = self.canvas.dataset.getBondIndices(self.canvas.index)
        bonds = np.array(bonds)

        nBonds = len(bonds)
        if nBonds > 0:
            bonds = R[bonds]
        else:
            bonds = None

        self.set(R=bonds)


class FixedBondsProperty(CanvasProperty):

    key = "fixedBonds"
    indices = None
    needsInit = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def onNewGeometry(self):
        self.clear()
        if self.needsInit:
            self.setPlaceholderIdxs()

    def generate(self):
        idxs = self.canvas.loupe.settings.get("fixedBondIndices")
        if idxs is None:
            idxs = self.setPlaceholderIdxs()

        idxs = np.array(idxs)
        R = self.canvas.getCurrentR()

        if len(idxs) == 0:
            self.set(R=None)
        else:
            bonds = R[idxs]
            self.set(R=bonds)

    def setPlaceholderIdxs(self):
        idxs = self.canvas.dataset.getBondIndices(0)
        self.canvas.loupe.settings.setParameter(
            "fixedBondIndices", idxs, refresh=True
        )
        self.needsInit = False
        return idxs

    def onDatasetInit(self):
        # we need to do it like this because setPlaceholderIdxs forces an onGeometry reset, which we dont want ot call during init
        self.needsInit = True


class BondSelect(AtomSelectionBase):
    multiselect = 2
    label = "Bond Selection"

    def __init__(self, canvas, **kwargs):
        super().__init__(canvas, **kwargs)

        self.bonds = []

    def selectCallback(self):
        if len(self.selectedPoints) != 2:
            return

        loupe = self.canvas.loupe
        bonds = loupe.settings.get("fixedBondIndices")

        bonds = set(bonds)
        (p1, p2) = self.selectedPoints
        p1, p2 = int(p1), int(p2)
        if p1 < p2:
            sel = (p1, p2)
        else:
            sel = (p2, p1)
        if sel in bonds:
            bonds.remove(sel)
        else:
            bonds.add(sel)

        self.clearSelection()
        self.updateBonds(bonds)

    def updateBonds(self, bonds):
        bonds = list(bonds)

        self.canvas.loupe.settings.setParameter(
            "fixedBondIndices", bonds, refresh=True
        )


def addSettings(UIHandler, loupe):
    def loupeClearBondProperty(loupe):
        loupe.canvas.props["fixedBonds"].clear()

    ## LOUPE SETTINGS
    settings = loupe.settings
    settings.addAction(
        "clearBondProperty", partial(loupeClearBondProperty, loupe)
    )
    settings.addParameters(
        **{
            "bondType": ["Fixed", "updateGeometry"],
            "fixedBondIndices": [None, "clearBondProperty", "updateGeometry"],
        }
    )

    ## CANVAS PROPERTIES
    loupe.addCanvasProperty(DynamicBondsProperty)
    loupe.addCanvasProperty(FixedBondsProperty)


def addBondsObject(UIHandler, loupe):

    loupe.addVisualElement(BondsElement, "BondsElement")


def addSettingsPane(UIHandler, loupe):
    from UI.Templates import SettingsPane, PushButton

    settings = loupe.settings

    pane = SettingsPane(UIHandler, loupe.settings, parent=loupe)

    pane.addSetting(
        "ComboBox",
        f"Bonds Type",
        settingsKey="bondType",
        items=["Fixed", "Dynamic"],
    )

    s = pane.addSetting(
        "CodeBox",
        "Bond Indices",
        settingsKey="fixedBondIndices",
        validationFunc=cleanBondIdxsArray,
    )
    s.setHideCondition(lambda: settings.get("bondType") != "Fixed")

    ## ADD BONDS BUTTONS
    container = pane.addSetting(
        "Container", "Bonds Indices Container", layout="horizontal"
    )
    container.setHideCondition(lambda: settings.get("bondType") != "Fixed")

    # DYNAMIC FILL BTN
    def bondsDynamicFill():
        dataset = loupe.getSelectedDataset()
        idxs = dataset.getBondIndices(loupe.index)
        loupe.settings.setParameter("fixedBondIndices", idxs, refresh=True)

    dynamicFillBtn = PushButton("Dynamic")
    dynamicFillBtn.clicked.connect(bondsDynamicFill)
    container.layout.addWidget(dynamicFillBtn)

    # SELECT BONDS BTN

    def selectBonds():
        loupe.setActiveAtomSelectTool(BondSelect)

    selectButton = PushButton("Select")
    selectButton.clicked.connect(selectBonds)
    container.layout.addWidget(selectButton)

    loupe.addSidebarPane("BONDS", pane)


def loadLoupe(UIHandler, loupe):
    addSettings(UIHandler, loupe)  # also sets the bonds property
    addBondsObject(UIHandler, loupe)
    addSettingsPane(UIHandler, loupe)
