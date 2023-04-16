from UI.loupeProperties import VisualElement, CanvasProperty
import numpy as np

DEPENDENCIES = ["loupeAtoms"]


class TranslationProperty(CanvasProperty):

    key = "translationTest"
    changesR = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def onNewGeometry(self):
        self.canvas.rotationMatrix = np.eye(3)


def loadLoupe(UIHandler, loupe):
    if False:
        loupe.addCanvasProperty(TranslationProperty)
