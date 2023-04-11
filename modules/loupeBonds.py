import numpy as np
from config.atoms import covalentBonds
from config.userConfig import getConfig
from functools import partial

DEPENDENCIES = ["loupeCamera"]


def addSettings(UIHandler, loupe):

    def loupeClearBondProperty(loupe):
        loupe.canvas.props['fixedBonds'].clear()

    ## LOUPE SETTINGS
    settings = loupe.settings
    settings.addAction("clearBondProperty", partial(loupeClearBondProperty, loupe))
    settings.addParameters(**{
        "bondType": ["Fixed", "updateGeometry"],
        "fixedBondIndices": [None, "clearBondProperty", "updateGeometry"],
    })

    ## CANVAS PROPERTIES

    from UI.Loupe import CanvasProperty, AtomSelectionBase
    from scipy.spatial import distance_matrix

    class DynamicBondsProperty(CanvasProperty):

        key = "dynamicBonds"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def onNewGeometry(self):
            self.clear()

        def generate(self):
            R = self.canvas.getCurrentR()
            bonds = self.getBondIndices(R)

            nBonds = len(bonds)
            if nBonds > 0:
                bonds = R[bonds]
            else:
                bonds = None

            self.set(R=bonds)

        def getBondIndices(self, r):
            d = distance_matrix(r, r)
            args = np.argwhere(d < self.bondSizes)
            return args

        def onDatasetInit(self):
            z = self.canvas.dataset.getElements()
            self.bondSizes = covalentBonds[z, z] * getConfig(
                "loupeBondsLenience"
            )

    class FixedBondsProperty(DynamicBondsProperty):

        key = "fixedBonds"
        indices = None

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def onNewGeometry(self):
            self.clear()

        def generate(self):
            R = self.canvas.getCurrentR()
            bonds = R[self.idxs]

            if self.nBonds is None:
                self.set(R=None)
            else:
                self.set(R=bonds)

        def getBondIndices(self, r):
            d = distance_matrix(r, r)
            args = np.argwhere(d < self.bondSizes)
            return args

        def onDatasetInit(self):
            z = self.canvas.dataset.getElements()
            self.bondSizes = covalentBonds[z, z] * getConfig(
                "loupeBondsLenience"
            )

            idxs = self.getBondIndices(self.canvas.getR(0))
            self.idxs = idxs
            self.nBonds = len(self.idxs)

    loupe.addCanvasProperty(DynamicBondsProperty)
    loupe.addCanvasProperty(FixedBondsProperty)

    class BondSelect(AtomSelectionBase):
        multiselect = 2
        label = "Bond Selection"

        def __init__(self, loupe, **kwargs):
            super().__init__(loupe, **kwargs)

            self.bonds = []
            self.selectedBonds = loupe.selectedBonds

        def selectCallback(self):
            if len(self.selectedPoints) != 2:
                return

            (p1, p2) = self.selectedPoints
            p1, p2 = int(p1), int(p2)
            if p1 < p2:
                sel = (p1, p2)
            else:
                sel = (p2, p1)
            if sel in self.selectedBonds:
                self.selectedBonds.remove(sel)
            else:
                self.selectedBonds.add(sel)

            self.clearSelection()
            self.writeSelectedBonds()

        def writeSelectedBonds(self):
            s, n, l = ("", len(self.selectedBonds), list(self.selectedBonds))
            for i in range(n):
                bond = l[i]
                s += f"    [{bond[0]}, {bond[1]}]"
                if i < n - 1:
                    s += ",\n"
                else:
                    s += "\n"
            self.loupe.bondsTextEdit.setText(f"[\n{s}]")

    # loupe.setActiveAtomSelectTool(BondSelect)

def addBondsObject(UIHandler, loupe):

    from UI.VispyTemplates import Tube
    from UI.Loupe import VisualElement
    from vispy import scene
    from scipy.spatial import distance_matrix


    class BondsElement(VisualElement):
        def __init__(self, *args, parent=None, width=200, **kwargs):
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

        def draw(self, picking = False, pickingColors = None):

            if picking:
                self.lines.visible = False
                return
            
            if not self.lines.visible:
                self.lines.visible = True

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

    if False:
       class BondsTubeElement(VisualElement):
        # NOT UPDATED WITH NEW PROPERTIES FUNCTIONALITY
        tubeVisual = None

        def __init__(self, *args, parent=None, **kwargs):
            self.tube = Tube(
                radius=0.1, shading="smooth", tube_points=10, parent=parent
            )
            super().__init__(*args, **kwargs, singleElement=self.tube)

        def onDatasetInit(self):
            z = self.canvas.dataset.getElements()
            self.bondSizes = covalentBonds[z, z] * getConfig(
                "loupeBondsLenience"
            )

            # TODO TEST REMOVE
            l = []
            for i in range(self.canvas.dataset.getNAtoms() - 1):
                l.append([i, i + 1])
            l.append([i, 0])
            self.selectedBonds = np.array(l)

        def onNewGeometry(self):
            R = self.canvas.getCurrentR()
            bonds = self.getBonds(R)
            self.R = R

            nBonds = len(bonds)
            if nBonds > 0:
                self.bonds = R[bonds]
            else:
                self.bonds = None

            self.queueVisualRefresh()

        def getBonds(self, r):
            if False:  # TODO dynamic bonds
                d = distance_matrix(r, r)
                args = np.argwhere(d < self.bondSizes)
            else:
                args = np.array(list(self.selectedBonds))
            return args

        def draw(self):
            bonds = self.bonds

            self.tube.set_new_points(bonds.reshape(-1, 3))

    loupe.addVisualElement(BondsElement)


def addSettingsPane(UIHandler, loupe):
    from UI.Templates import SettingsPane
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
    )
    s.setHideCondition(lambda: settings.get("bondType") != "Fixed")

    loupe.addSidebarPane("BONDS", pane)


def loadLoupe(UIHandler, loupe):
    addSettings(UIHandler, loupe)  # also sets the bonds property
    addBondsObject(UIHandler, loupe)
    addSettingsPane(UIHandler, loupe)
