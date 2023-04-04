import numpy as np
from config.atoms import atomColors


def addAtomsObject(UIHandler, loupe):

    from UI.Loupe import VisualElement
    from vispy import scene

    class AtomsElement(VisualElement):
        def __init__(self, *args, parent=None, **kwargs):
            scatter = scene.visuals.Markers(
                scaling=True, spherical=True, parent=parent
            )
            super().__init__(*args, **kwargs, element=scatter)
            # self.colors = (1,1,1)

        def onDatasetInit(self):
            z = self.canvas.dataset.getElements()
            self.colors = atomColors[z] / 255

        def onNewGeometry(self):
            R = self.canvas.getCurrentR()
            self.pos = R
            self.queueVisualRefresh()

        def draw(self):
            self.element.set_data(
                self.pos, face_color=self.colors, size=0.8, edge_width=0.001,
            )

    loupe.addVisualElement(AtomsElement)


def addSettingsPane(UIHandler, loupe):
    from UI.Templates import Widget, SettingsPane

    pane = SettingsPane(UIHandler)
    for i in range(10):
        pane.addSetting("ComboBox", f"Test {i}")
    loupe.addSidebarPane("TEEST", pane)


def loadLoupe(UIHandler, loupe):
    addAtomsObject(UIHandler, loupe)
    addSettingsPane(UIHandler, loupe)
