from UI.loupeProperties import AtomSelectionBase, CanvasProperty
import numpy as np
import logging
from scipy.spatial.transform import Rotation
from client.mathUtils import getVV0Angle, getVV0RotationMatrix, getPerpComponent

logger = logging.getLogger("FFAST")

DEPENDENCIES = ["loupeAtoms"]



def getTransform(r, r0, along=None):
    n1, n2, n3 = along
    transforms = []

    r = np.copy(r)
    r0 = np.copy(r0)

    # translate to overlap first atom
    d = r0[n1] - r[n1]
    r = r + d
    transforms.append(d)

    # align v12
    rotMatrix = getVV0RotationMatrix(r[n2] - r[n1], r0[n2] - r0[n1])

    # change origin to get rotation around (0,0,0)
    r = r - r0[n1]
    r = np.matmul(r, rotMatrix)
    transforms.append(-r0[n1])
    transforms.append(rotMatrix)

    # rotate around v12 to align third atom
    v12 = r[n2] - r[n1]
    u12 = v12 / np.linalg.norm(v12)
    vpp = getPerpComponent(
        r[n3], u12, unitary=True
    )  # remember that r[n1] is origin atm
    vpp0 = getPerpComponent(r0[n3] - r0[n1], u12, unitary=True)
    angle = getVV0Angle(vpp, vpp0, directionVector=u12)
    rotMatrix = Rotation.from_rotvec(angle * u12).as_matrix()

    transforms.append(rotMatrix)
    transforms.append(r0[n1])

    return transforms


def cleanAlignAtomsIndices(arr):
    try:
        s = set([int(x) for x in arr])
        t = tuple(s)
        if len(t) != 3:
            raise ValueError

    except Exception as e:
        logger.exception(
            f"Tried to clean indices arr, but failed for: {e}. Array/List needs contain 3 dinstinct integers"
        )
        return False, None

    return True, list(s)


class AlignAtomsProperty(CanvasProperty):

    key = "alignAtoms"
    changesR = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def onNewGeometry(self):
        canvas = self.canvas
        settings = self.canvas.loupe.settings

        if not settings.get("alignAtoms"):
            return

        idxs = settings.get("alignAtomsIndices")
        confIdx = settings.get("alignAtomsConfIndex")

        if idxs is None:
            return

        if self.canvas.index == confIdx:
            return

        r0 = canvas.getR(confIdx)
        r = canvas.getCurrentR()

        transforms = getTransform(r, r0, along=idxs)

        self.canvas.currentTransformations = (
            self.canvas.currentTransformations + transforms
        )


class AtomAlignSelect(AtomSelectionBase):
    multiselect = 3
    label = "Align Atoms Selection"

    def __init__(self, canvas, **kwargs):
        super().__init__(canvas, **kwargs)
        self.atoms = []

    def selectCallback(self):
        N = len(self.selectedPoints)
        self.updateInfo()
        if N != 3:
            return

        self.applySelectedAtoms()
        self.clearSelection()
        self.canvas.setActiveAtomSelectTool(None)

    def applySelectedAtoms(self):
        self.canvas.loupe.settings.setParameter(
            "alignAtomsIndices", self.selectedPoints
        )

    def getInfoLabel(self):
        N = len(self.selectedPoints)
        return f'Select{3-N} more points'

def addSettings(UIHandler, loupe):
    from UI.Templates import PushButton

    def updateAlignAtomsConfIndex():
        index = loupe.canvas.index
        loupe.settings.setParameter("alignAtomsConfIndex", index)

    ## SETTINGS
    settings = loupe.settings
    settings.addParameters(
        **{
            "alignAtoms": [False, "updateGeometry"],
            "alignAtomsIndices": [None, "updateGeometry"],
            "alignAtomsConfIndex": [0, "updateGeometry"],
        }
    )
    settings.addParameterActions(
        "alignAtomsIndices", updateAlignAtomsConfIndex
    )

    ## MAKE IT EXCLUSIVE WITH COM
    settings.addParameterActions(
        "alignAtoms",
        lambda: settings.setParameter("originCenterOfMass", False)
        if settings.get("alignAtoms")
        else None,
    )
    settings.addParameterActions(
        "originCenterOfMass",
        lambda: settings.setParameter("alignAtoms", False)
        if settings.get("originCenterOfMass")
        else None,
    )

    ## SETTINGS PANE
    pane = loupe.getSettingsPane("ATOMS")
    pane.addSetting("CheckBox", "Align Atoms", settingsKey="alignAtoms")

    container = pane.addSetting(
        "Container", "Align Atoms Indices Container", layout="horizontal"
    )
    container.setHideCondition(lambda: not settings.get("alignAtoms"))
    container.setFixedHeight(30)

    codeBox = pane.addSetting(
        "CodeBox",
        "Indices",
        settingsKey="alignAtomsIndices",
        validationFunc=cleanAlignAtomsIndices,
        labelDirection="horizontal",
        singleLine=True,
    )
    container.layout.addWidget(codeBox)

    ## SELECT BUTTON
    def selectAlignAtomIndices():
        loupe.setActiveAtomSelectTool(AtomAlignSelect)

    selectButton = PushButton("Select")
    selectButton.clicked.connect(selectAlignAtomIndices)
    container.layout.addWidget(selectButton)


def loadLoupe(UIHandler, loupe):
    addSettings(UIHandler, loupe)
    loupe.addCanvasProperty(AlignAtomsProperty)
