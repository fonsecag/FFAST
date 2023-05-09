from UI.loupeProperties import CanvasProperty
import numpy as np

DEPENDENCIES = ["loupeAtoms"]


class CameraInfo(CanvasProperty):

    key = "camera"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lastCOM = np.zeros(3)

    def generate(self):
        camera = self.canvas.camera

        if camera._viewbox is None:
            return

        # Calculate viewing range for x and y
        fx = fy = camera._scale_factor

        # Correct for window size
        w, h = camera._viewbox.size

        if (w == 0) or (h == 0):
            return

        if w / h > 1:
            fx *= w / h
        else:
            fy *= h / w

        # self.set(distance=camera._actual_distance, center=camera.center)
        self.set(distance=fy, center=camera.center)

    def centeringCOM(self):
        return self.canvas.settings.get("originCenterOfMass")

    def onNewGeometry(self):
        wasActive = np.sum(np.abs(self.lastCOM)) > 0
        if self.centeringCOM():
            r = self.canvas.getCurrentR()
            com = np.mean(r, axis=0)

            if wasActive:
                dr = com - self.lastCOM
                self.canvas.camera.center = self.canvas.camera.center + dr
            else:
                self.canvas.camera.center = com

            self.lastCOM = com

        elif wasActive:
            self.canvas.camera.center = self.canvas.camera.center
            self.lastCOM = np.zeros(3)

    def onCameraChange(self):
        self.clear()


def loadLoupe(UIHandler, loupe):
    from UI.Templates import SettingsPane

    # SETTINGS
    def updateOrthographicCamera(*args):
        ortho = loupe.canvas.settings.get("cameraOrthographic")
        if ortho:
            loupe.canvas.camera.fov = 0
        else:
            loupe.canvas.camera.fov = 45

    settings = loupe.settings
    settings.addParameters(
        **{
            "originCenterOfMass": [True, "updateGeometry"],
            "cameraOrthographic": [
                False,
                updateOrthographicCamera,
                "onCameraChange",
            ],
        }
    )

    # SETTINGS PANE
    pane = SettingsPane(UIHandler, loupe.settings, parent=loupe)

    pane.addSetting("CheckBox", "Origin COM", settingsKey="originCenterOfMass")
    pane.addSetting(
        "CheckBox", "Orthographic", settingsKey="cameraOrthographic"
    )

    # add pane
    loupe.addSidebarPane("CAMERA", pane)

    # PROPERTIES
    loupe.addCanvasProperty(CameraInfo)
