from UI.loupeProperties import AtomSelectionBase
import numpy as np
from client.mathUtils import getVV0Angle, getDihedral

DEPENDENCIES = ["loupeAtoms"]

class AtomInfoSelect(AtomSelectionBase):
    multiselect = 4
    label = "Atoms Info"
    cycle = True

    def __init__(self, canvas, **kwargs):
        super().__init__(canvas, **kwargs)

    def selectCallback(self):
        self.updateInfo()

    def applySelectedAtoms(self):
        self.canvas.loupe.settings.setParameter(
            "alignAtomsIndices", self.selectedPoints
        )

    def getInfoLabel(self):
        idxs = self.selectedPoints
        N = len(idxs)
        if N == 1:
            return self.singleAtomInfo(*idxs)
        elif N == 2:
            return self.distanceInfo(*idxs)
        elif N == 3:
            return self.angleInfo(*idxs)
        elif N == 4:
            return self.dihedralInfo(*idxs)
        
    
    def singleAtomInfo(self, i):
        R = self.canvas.getCurrentR()[i]
        z = self.canvas.dataset.getElementsName()[i]

        return f'Atom {i} / Element {z} / ({R[0]:.2f},{R[1]:.2f},{R[2]:.2f})'

    def distanceInfo(self, i, j):
        R = self.canvas.getCurrentR()
        z = self.canvas.dataset.getElementsName()

        d = np.sqrt(np.sum((R[i] - R[j])**2))

        return f'Atoms {i},{j} / Elements {z[i]},{z[j]} / Distance: {d:.2f}'
    
    def angleInfo(self, i, j, k):
        R = self.canvas.getCurrentR()
        z = self.canvas.dataset.getElementsName()

        a = getVV0Angle(R[k] - R[j], R[i] - R[j])
        a *= 180 / np.pi
        return f'Atoms {i},{j},{k} / Elements {z[i]},{z[j]},{z[k]} / Angle: {a:.1f}'
    
    def dihedralInfo(self,i, j, k, l):
        R = self.canvas.getCurrentR()
        z = self.canvas.dataset.getElementsName()

        a = getDihedral(R[i], R[j], R[k], R[l])
        a *= 180 / np.pi

        return f'Atoms {i},{j},{k},{l} / Elements {z[i]},{z[j]},{z[k]},{z[l]} / Dihedral: {a:.1f}'
        
def loadLoupe(UIHandler, loupe):
    from PySide6 import QtWidgets
    from UI.Templates import PushButton

    ## ADD BUTTON
    pane = loupe.getSettingsPane("ATOMS")
    container = pane.addSetting(
        "Container", "Atoms Info Container", layout="horizontal"
    )
    container.layout.addWidget(QtWidgets.QLabel("Atom Info"))

    ## SELECT BUTTON
    def selectAtomInfoIndices():
        loupe.setActiveAtomSelectTool(AtomInfoSelect)

    selectButton = PushButton("Select")
    selectButton.clicked.connect(selectAtomInfoIndices)
    container.layout.addWidget(selectButton)
