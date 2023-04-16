DEPENDENCIES = ["loupeAtoms"]


def loadLoupe(UIHandler, loupe):
    from UI.loupeProperties import CanvasProperty
    import numpy as np

    # SETTINGS

    settings = loupe.settings
    settings.addParameters(**{"originCenterOfMass": [True, "updateGeometry"]})

    # SETTINGS PANE
    pane = loupe.getSettingsPane("ATOMS")

    pane.addSetting(
        "CheckBox", f"Origin COM", settingsKey="originCenterOfMass"
    )

    # PROPERTIES

    class CameraInfo(CanvasProperty):

        key = "camera"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.lastCOM = np.zeros(3)

        def generate(self):
            camera = self.canvas.camera
            self.set(distance=camera._actual_distance, center=camera.center)

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

    loupe.addCanvasProperty(CameraInfo)
