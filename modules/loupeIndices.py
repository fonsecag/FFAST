import numpy as np
from config.userConfig import getConfig
from UI.loupeProperties import VisualElement, CanvasProperty

DEPENDENCIES = []


class IndicesElement(VisualElement):
    def __init__(self, *args, parent=None, width=200, **kwargs):
        from vispy.scene.visuals import Text

        self.textVisual = Text(
            "", parent=parent, color="black", method="gpu", bold=True
        )
        self.textVisual.font_size = 140

        self.nAtoms = 0
        super().__init__(*args, **kwargs, singleElement=self.textVisual)

    def active(self):
        return self.canvas.settings.get("indicesText")

    def onNewGeometry(self):
        self.update()
        self.queueVisualRefresh()

    def update(self):

        active = self.active()
        if self.hidden:
            if active:
                self.show()
            else:
                return
        elif (not self.hidden) and (not active):
            self.hide()
            return

        R = self.canvas.getCurrentR()
        self.textVisual.pos = R

        self.textVisual.font_size = self.canvas.settings.get(
            "indicesTextFontSize"
        )

        self.nAtoms = R.shape[0]
        self.textVisual.text = [str(i) for i in range(self.nAtoms)]


def loadLoupe(UIHandler, loupe):
    from UI.Templates import SettingsPane

    loupe.addVisualElement(IndicesElement, "IndicesElement")

    settings = loupe.settings
    settings.addParameters(
        **{
            "indicesText": [False, "updateGeometry"],
            "indicesTextFontSize": [140, "updateGeometry"],
        }
    )

    # SETTINGS PANE
    pane = SettingsPane(UIHandler, loupe.settings, parent=loupe)
    pane.addSetting("CheckBox", "Indices", settingsKey="indicesText")
    pane.addSetting(
        "Slider",
        "Font size",
        settingsKey="indicesTextFontSize",
        nMin=5,
        nMax=1000,
    )

    # add pane
    loupe.addSidebarPane("INDICES", pane)
