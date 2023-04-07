import numpy as np
from config.atoms import atomColors, covalentBonds
from config.userConfig import getConfig


def addAtomsObject(UIHandler, loupe):

    from UI.Loupe import VisualElement
    from vispy import scene

    class AtomsElement(VisualElement):
        def __init__(self, *args, parent=None, **kwargs):
            self.scatter = scene.visuals.Markers(
                scaling=True, spherical=True, parent=parent
            )
            super().__init__(*args, **kwargs, singleElement=self.scatter)
            # self.colors = (1,1,1)

        def onDatasetInit(self):
            z = self.canvas.dataset.getElements()
            self.colors = atomColors[z] / 255

        def onNewGeometry(self):
            R = self.canvas.getCurrentR()
            self.pos = R
            self.queueVisualRefresh()

        def draw(self):
            self.scatter.set_data(
                self.pos, face_color=self.colors, size=0.8, edge_width=0.001,
            )

    loupe.addVisualElement(AtomsElement)

def addBondsObject(UIHandler, loupe):


    from UI.Loupe import VisualElement
    from vispy import scene
    from scipy.spatial import distance_matrix

    class BondsElement(VisualElement):
        def __init__(self, *args, parent=None, **kwargs):
            self.lines = scene.visuals.Line(
                pos = None, parent=parent, color = getConfig("loupeBondsColor"), width = 5, connect = "segments"
            )
            super().__init__(*args, **kwargs, singleElement=self.lines)
            # self.colors = (1,1,1)

        def onDatasetInit(self):
            z = self.canvas.dataset.getElements()
            self.bondSizes = covalentBonds[z, z] * getConfig("loupeBondsLenience")

            # TODO TEST REMOVE
            l = []
            for i in range(self.canvas.dataset.getNAtoms()-1):
                l.append([i, i+1])
            l.append([i, 0])
            self.selectedBonds = np.array(l)

        def onNewGeometry(self):
            R = self.canvas.getCurrentR()
            bonds = self.getBonds(R)

            nBonds = len(bonds)
            if nBonds > 0:
                self.bonds = R[bonds]
            else:
                self.bonds = None

            self.queueVisualRefresh()

        def getBonds(self, r):
            if False: # TODO dynamic bonds
                d = distance_matrix(r, r)
                args = np.argwhere(d < self.bondSizes)
            else:
                args = np.array(list(self.selectedBonds))
            return args

        def draw(self):
            bonds = self.bonds

            if self.bonds is None:
                self.lines.set_data(width=0)
            else:
                self.lines.set_data(pos=bonds, width=5)


    class BondsTubeElement(VisualElement):
        def __init__(self, *args, parent=None, **kwargs):
            self.parent = parent
            super().__init__(*args, **kwargs)
            # self.colors = (1,1,1)

        def onDatasetInit(self):
            z = self.canvas.dataset.getElements()
            self.bondSizes = covalentBonds[z, z] * getConfig("loupeBondsLenience")

            # TODO TEST REMOVE
            l = []
            for i in range(self.canvas.dataset.getNAtoms()-1):
                l.append([i, i+1])
            l.append([i, 0])
            self.selectedBonds = np.array(l)

            self.tube = scene.visuals.Tube(
                points = np.ones((20, 3))*np.arange(20).reshape(-1,1) + np.random.normal(0, 2, size = (20, 3)), radius = 5
            )


            # z = np.zeros((2,3))
            # for i in range(len(l)):
            #     self.bondsElements.append(scene.visuals.Tube(points= np.random.random((2,3))*10, parent = self.parent, color = getConfig("loupeBondsColor"), radius = 2))

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
            if False: # TODO dynamic bonds
                d = distance_matrix(r, r)
                args = np.argwhere(d < self.bondSizes)
            else:
                args = np.array(list(self.selectedBonds))
            return args

        def draw(self):
            bonds = self.bonds

            self.tube.set_data(color = 'white', face_colors = 'white')
            
    loupe.addVisualElement(BondsTubeElement)


def addSettings(UIHandler, loupe):
    settings = loupe.settings
    settings.addParameters(**{"atomColorType": ["Elements", "updateIndex"]})


def addSettingsPane(UIHandler, loupe):
    from UI.Templates import SettingsPane

    pane = SettingsPane(UIHandler, loupe.settings, parent=loupe)

    pane.addSetting(
        "ComboBox",
        f"Coloring",
        settingsKey=f"atomColorType",
        items=["Elements", "Force Error"],
    )

    loupe.addSidebarPane("ATOMS", pane)


def loadLoupe(UIHandler, loupe):
    addAtomsObject(UIHandler, loupe)
    addBondsObject(UIHandler, loupe)
    addSettings(UIHandler, loupe)
    addSettingsPane(UIHandler, loupe)
