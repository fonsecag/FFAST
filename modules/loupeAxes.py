import numpy as np
from config.userConfig import getConfig
from UI.loupeProperties import VisualElement, CanvasProperty

DEPENDENCIES = ["loupeCamera"]


class AxesElement(VisualElement):
    def __init__(self, *args, parent=None, width=200, **kwargs):
        from vispy import scene
        from vispy.visuals.transforms import STTransform

        # Create an XYZAxis visual
        self.axes = scene.visuals.XYZAxis(parent=parent)
        s = STTransform(translate=(50, 50), scale=(50, 50, 50, 1))  # temporary
        affine = s.as_matrix()
        self.axes.transform = affine
        self.updateAxes()

        super().__init__(*args, **kwargs, singleElement=self.axes)

    def onCameraChange(self):
        self.updateAxes()

    def onCanvasResize(self):
        return self.updateAxes()

    def active(self):
        return self.canvas.settings.get("cameraAxes")

    def updateAxes(self):

        if self.canvas is None:
            return

        active = self.active()
        if self.hidden:
            if self.active():
                self.show()
            else:
                return

        elif (not self.hidden) and (not active):
            self.hide()
            return

        axes = self.axes
        cam = self.canvas.camera
        axes.transform.reset()

        axes.transform.rotate(cam.roll, (0, 0, 1))
        axes.transform.rotate(cam.elevation, (1, 0, 0))
        axes.transform.rotate(cam.azimuth, (0, 1, 0))

        w, h = self.canvas.size()
        axes.transform.scale((50, 50, 0.001))
        axes.transform.translate((w - 75.0, h - 75.0))
        axes.update()


def loadLoupe(UIHandler, loupe):
    loupe.addVisualElement(AxesElement, "AxesElement", viewParent=True)

    settings = loupe.settings
    settings.addParameters(**{"cameraAxes": [False, "cameraChange"]})

    pane = loupe.getSettingsPane("CAMERA")
    pane.addSetting("CheckBox", "Axes", settingsKey="cameraAxes")
