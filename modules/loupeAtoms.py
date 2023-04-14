import numpy as np
from config.atoms import atomColors, covalentRadii
from config.userConfig import getConfig

DEPENDENCIES = []


def addAtomsObject(UIHandler, loupe):

    from UI.Loupe import VisualElement
    from vispy import scene

    class AtomsElement(VisualElement):

        pickingVisible = True

        def __init__(self, *args, parent=None, **kwargs):
            self.scatter = scene.visuals.Markers(
                scaling=True,
                spherical=True,
                parent=parent,
                light_color=(0, 0, 0),
                light_ambient=1,
                antialias=1,
            )
            super().__init__(*args, **kwargs, singleElement=self.scatter)
            self.edge_width = 0.02 
            # self.colors = (1,1,1)

        def onDatasetInit(self):
            z = self.canvas.dataset.getElements()
            self.colors = (
                atomColors[z] / 255 * getConfig("loupeAtomColorDimming")
            )
            self.sizes = covalentRadii[z]

        def onNewGeometry(self):
            R = self.canvas.getCurrentR()
            self.pos = R
            self.queueVisualRefresh()

        def _draw(self, picking = False, pickingColors = None):
         
            self.scatter.set_data(
                self.pos,
                face_color= pickingColors if picking else self.colors,
                size=self.sizes,
                edge_width= 0 if picking else self.edge_width,
                edge_color= getConfig("loupeBondsColor"),
            )
            if picking:
                self.scatter.update_gl_state(blend=False)
            else:
                self.scatter.update_gl_state(blend=True)

    class AtomsHoverElement(VisualElement):
        def __init__(self, *args, parent=None, **kwargs):
            self.scatter = scene.visuals.Markers(
                scaling=True,
                parent=parent,
                light_color=(0, 0, 0),
                light_ambient=1,
                antialias=1,
            )
            super().__init__(*args, **kwargs, singleElement=self.scatter)

        def onDatasetInit(self):
            z = self.canvas.dataset.getElements()
            self.sizes = covalentRadii[z]

        def onNewGeometry(self):
            R = self.canvas.getCurrentR()
            self.pos = R
            self.queueVisualRefresh()

        def _draw(self, picking = False, pickingColors = None):
            
            hover, _ = self.canvas.getHoveredAtom(), self.canvas.getSelectedAtoms()

            if hover is not None:
                pos = np.array([self.pos[hover]])
                size = self.sizes[hover]
                if not self.scatter.visible:
                    self.scatter.visible = True

            else:
                self.scatter.visible = False
                return

            self.scatter.set_data(
                pos,
                size=size,
                edge_width = 0.12,
                edge_color= getConfig("loupeHoverColor"),
                face_color= "#00000000",
            )

    class AtomsSelectedElement(VisualElement):
        def __init__(self, *args, parent=None, **kwargs):
            self.scatter = scene.visuals.Markers(
                scaling=True,
                parent=parent,
                light_color=(0, 0, 0),
                light_ambient=1,
                antialias=1,
            )
            super().__init__(*args, **kwargs, singleElement=self.scatter)

        def onDatasetInit(self):
            z = self.canvas.dataset.getElements()
            self.sizes = covalentRadii[z]

        def onNewGeometry(self):
            R = self.canvas.getCurrentR()
            self.pos = R
            self.queueVisualRefresh()

        def _draw(self, picking = False, pickingColors = None):
            
            _, selected = self.canvas.getHoveredAtom(), self.canvas.getSelectedAtoms()

            if selected is not None:
                pos = self.pos[selected]
                size = self.sizes[selected]
                if not self.scatter.visible:
                    self.scatter.visible = True

            else:
                self.scatter.visible = False
                return

            self.scatter.set_data(
                pos,
                size=size,
                edge_width = 0.12,
                edge_color= getConfig("loupeSelectColor"),
                face_color= "#00000000",
            )

    loupe.addVisualElement(AtomsElement)
    loupe.addVisualElement(AtomsHoverElement)
    loupe.addVisualElement(AtomsSelectedElement)

def addSettings(UIHandler, loupe):
    settings = loupe.settings
    settings.addParameters(**{
        "atomColorType": ["Elements", "updateGeometry"],
    })


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

    addSettings(UIHandler, loupe)  # also sets the bonds property
    addAtomsObject(UIHandler, loupe)
    addSettingsPane(UIHandler, loupe)
