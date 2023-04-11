import numpy as np
from config.atoms import atomColors, covalentRadii
from config.userConfig import getConfig

DEPENDENCIES = []


def addAtomsObject(UIHandler, loupe):

    from UI.Loupe import VisualElement
    from vispy import scene

    class AtomsElement(VisualElement):
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

        def draw(self, picking = False, pickingColors = None):

            self.scatter.set_data(
                self.pos,
                face_color= pickingColors if picking else self.colors,
                size=self.sizes,
                edge_width= 0 if picking else self.edge_width,
                edge_color=getConfig("loupeBondsColor"),
            )

    loupe.addVisualElement(AtomsElement)



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
