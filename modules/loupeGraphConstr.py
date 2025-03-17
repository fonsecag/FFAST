import numpy as np
from config.userConfig import getConfig
from functools import partial
import logging
from utils import cleanBondIdxsArray
from UI.loupeProperties import VisualElement, CanvasProperty, AtomSelectionBase
# from modules.GraphSymSer import ffastInterfaceGraphConstruct, SymmRecover, GraphSymSer
# from modules.graph_construction import ffastInterfaceGraphConstruct
from modules.symmetry import GraphSymSer
import asyncio


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

        # bondType = self.canvas.settings.get("bondType")
        # if bondType == "Dynamic":
        #     bonds = self.canvas.props["dynamicBonds"].get("R")
        # elif bondType == "Fixed":
        bonds = self.canvas.props["fixedBonds"].get("R")

        width = self.canvas.props["camera"].get("distance")

        if width is None:
            width = 1

        if bonds is None:
            self.hide()
        else:
            self.show()
            self.lines.set_data(pos=bonds, width=self.width / width)


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
            "bondType": ["Fixed",],
            "fixedBondIndices": [None, "clearBondProperty", "updateGeometry"],
            "numberOfConfigurations": [100],
            "objectSymmetrySearch": [None, "updateGeometry"],#? what updateGeometry does mean?
            # "selectedIndx": [None, "updateGeometry"],
            "angleThreshold": [30],
            "freqAppearanceThreshold": [80],
        }
    )

    ## CANVAS PROPERTIES
    # loupe.addCanvasProperty(DynamicBondsProperty)
    loupe.addCanvasProperty(FixedBondsProperty)


def addBondsObject(UIHandler, loupe):

    loupe.addVisualElement(BondsElement, "BondsElement")

def GraphBuild(loupe):
    n_configs = loupe.canvas.settings.get("numberOfConfigurations")
    angle_threshold = loupe.canvas.settings.get("angleThreshold")
    freq_threshold = loupe.canvas.settings.get("freqAppearanceThreshold")/100.0
    R = loupe.canvas.getR()
    z = loupe.canvas.dataset.getElements()
    lattice = loupe.canvas.dataset.getLattice()

    graph_symm_serch = GraphSymSer(R, z, lattice, n_configs, angle_threshold, freq_threshold)
    idxs = graph_symm_serch.runFinalGraphConstruct()
    loupe.settings.setParameter("objectSymmetrySearch", graph_symm_serch, refresh=True)
    # indx = np.random.choice(len(R), n_configs, replace=False)
    # idxs = ffastInterfaceGraphConstruct(R[indx], z, lattice, angle_threshold, freq_threshold)
    # loupe.settings.setParameter("selectedIndx", indx, refresh=True)
    return idxs

def SymmetrySerch(loupe):
    # BondList = loupe.settings.get("fixedBondIndices")
    graph_symm_serch = loupe.settings.get("objectSymmetrySearch")
    graph_symm_serch.bondList = loupe.settings.get("fixedBondIndices")

    permut_num, permut_num_order, orb_num = graph_symm_serch.runSymmRecover()
    return permut_num, permut_num_order, orb_num

def addSettingsPane(UIHandler, loupe):
    from UI.Templates import SettingsPane, PushButton

    settings = loupe.settings

    pane = SettingsPane(UIHandler, loupe.settings, parent=loupe)

    s = pane.addSetting(
        "CodeBox",
        "Bond Indices",
        settingsKey="fixedBondIndices",
        validationFunc=cleanBondIdxsArray,
    )
    s.setHideCondition(lambda: settings.get("bondType") != "Fixed")
    s.setFixedHeight(200)

    #Add Hyperparamters

    pane.addSetting(
        "Slider",
        "# Configurations",
        settingsKey="numberOfConfigurations",
        toolTip="Change the number of configurations used in symmetry search",
        nMin=1,
        nMax=1000,
    )

    pane.addSetting(
        "Slider",
        "Angle Threshold",
        settingsKey="angleThreshold",
        toolTip="Change the angle used as threshold for bond creation",
        nMin=0,
        nMax=180,
    )
    
    pane.addSetting(
        "Slider",
        "Appearance Frequency",
        settingsKey="freqAppearanceThreshold",
        toolTip="Change the appearance frequency threshold for bond filtration",
        nMin=0,
        nMax=100,
    )

    ## ADD BONDS BUTTONS
    container = pane.addSetting(
        "Container", "Bonds Indices Container", layout="vertical"
    )
    container.setHideCondition(lambda: settings.get("bondType") != "Fixed")


    # Graph build button
    def bondsGraphFill():
        idxs = GraphBuild(loupe)
        loupe.settings.setParameter("fixedBondIndices", idxs, refresh=True)

    graphFillBtn = PushButton("Construct Graph")
    graphFillBtn.setToolTip(
        "Click to fill the bond indices based on the GraphSymSer algorithm"
    )
    graphFillBtn.clicked.connect(bondsGraphFill)
    container.layout.addWidget(graphFillBtn)

    # Symmery finder button
    def bondsSymFill():
        numSymm, genSymm, orbits = SymmetrySerch(loupe)
        loupe.canvas.atomSelectBar.show()
        loupe.canvas.atomSelectBar.label1.setText("Symmetry: " + str(numSymm) + " " + str(genSymm) + " " + str(orbits))

    symSerchBtn = PushButton("Symmetry Serch")
    symSerchBtn.setToolTip(
        "Click to obtain the symmetry of the system"
    )
    symSerchBtn.clicked.connect(bondsSymFill)
    container.layout.addWidget(symSerchBtn)

    # SELECT BONDS BTN
    def selectBonds():
        loupe.setActiveAtomSelectTool(BondSelect)

    selectButton = PushButton("Select")
    selectButton.setToolTip(
        "Click to manually add/remove bonds in the visualiser"
    )
    selectButton.clicked.connect(selectBonds)
    container.layout.addWidget(selectButton)

    loupe.addSidebarPane("SYMMETRY SEARCH", pane)


def loadLoupe(UIHandler, loupe):
    addSettings(UIHandler, loupe)  # also sets the bonds property
    addBondsObject(UIHandler, loupe)
    addSettingsPane(UIHandler, loupe)
