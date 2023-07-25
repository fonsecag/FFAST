import numpy as np
from config.userConfig import getConfig
from functools import partial
import logging
from UI.loupeProperties import VisualElement, CanvasProperty, AtomSelectionBase

logger = logging.getLogger("FFAST")
DEPENDENCIES = ["loupeAtoms"]


class ForceVectorsElement(VisualElement):
    # largely taken from loupeBonds
    pos = None

    def __init__(self, *args, parent=None, width=50, **kwargs):
        from vispy import scene

        self.lines = scene.visuals.Arrow(
            pos=None,
            parent=parent,
            color="white",
            width=width,
            connect="segments",
            arrow_size=1,
            arrows=None,
            # arrow_type = "triangle_30",
            arrow_color="white",
            # antialias=True,
            method="gl",
        )
        super().__init__(*args, **kwargs, singleElement=self.lines)
        self.width = width

    def onNewGeometry(self):
        self.update()

    def update(self):
        show = self.canvas.settings.get("showForceVectors")
        lengthFactor = self.canvas.settings.get("forceVectorsLength")
        window = self.canvas.settings.get("forceVectorsAvgWindow")
        normalised = self.canvas.settings.get("forceVectorsNormalised")

        if show:
            self.show()
        else:
            self.hide()
            return

        dataset = self.canvas.dataset
        R = self.canvas.getCurrentR()

        if window > 0:
            indices = np.arange(-window, window + 1) + self.canvas.index
            indices = indices[(indices >= 0) & (indices < dataset.getN())]
            F = self.canvas.dataset.getForces(indices=indices)
            F = np.mean(F, axis=0)
        else:
            F = self.canvas.dataset.getForces(indices=self.canvas.index)

        if normalised:
            normF = F / np.max(np.linalg.norm(F, axis=1)) * lengthFactor / 5
        else:
            normF = F * lengthFactor / 500

        pos = np.empty((R.shape[0] * 2, 3))
        pos[0::2, :] = R
        pos[1::2, :] = R + normF
        self.pos = pos

        self.queueVisualRefresh()

    def onCameraChange(self):
        dist = self.canvas.props["camera"].get("distance")

        if dist is None:
            dist = 1

        self.lines.set_data(width=self.width / dist)

    def _draw(self, picking=False, pickingColors=None):

        width = self.canvas.props["camera"].get("distance")

        if width is None:
            width = 1

        if self.pos is None:
            self.hide()
        else:
            self.show()
            self.lines.set_data(
                pos=self.pos,
                width=self.width / width,
                arrows=self.pos.reshape(-1, 6),
            )


def loadLoupe(UIHandler, loupe):
    from UI.Templates import SettingsPane

    loupe.addVisualElement(ForceVectorsElement, "ForceVectorsElement")

    settings = loupe.settings
    settings.addParameters(
        **{
            "showForceVectors": [False, "updateGeometry"],
            "forceVectorsLength": [5, "updateGeometry"],
            "forceVectorsAvgWindow": [0, "updateGeometry"],
            "forceVectorsNormalised": [False, "updateGeometry"],
        }
    )

    # SETTINGS PANE
    pane = SettingsPane(UIHandler, loupe.settings, parent=loupe)
    loupe.addSidebarPane("FORCE VECTORS", pane)

    pane.addSetting(
        "CheckBox",
        "Enable",
        settingsKey="showForceVectors",
        toolTip="Show a fector field corresponding to the forces",
    )
    pane.addSetting(
        "Slider",
        "Length",
        settingsKey="forceVectorsLength",
        toolTip="Change the length of the force vectors",
        nMin=1,
        nMax=50,
    )
    pane.addSetting(
        "Slider",
        "Avg. window",
        settingsKey="forceVectorsAvgWindow",
        toolTip="Set the number of points to average around for a smoother result.",
        nMin=0,
        nMax=10000,
    )
    pane.addSetting(
        "CheckBox",
        "Normalised",
        settingsKey="forceVectorsNormalised",
        toolTip="If enabled, set the longest vector for every frame to the same length",
    )
