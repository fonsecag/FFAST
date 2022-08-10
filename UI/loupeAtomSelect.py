class AtomSelectionBase:

    multiselect = 1
    cycle = False
    label = "N/A"

    def __init__(self, loupe):
        self.selectedPoints = []
        self.loupe = loupe

    def clearSelection(self):
        nSel = len(self.selectedPoints)
        self.selectedPoints = []
        if nSel > 0:
            self.loupe.refresh()

    def selectCallback(self):
        pass

    def selectAtom(self, idx):
        if idx is None:
            return

        sp = self.selectedPoints

        if idx in sp:
            sp.remove(idx)
        else:
            sp.append(idx)

        if self.cycle and (len(sp) > self.multiselect):
            self.selectedPoints = sp[-self.multiselect :]

        self.selectCallback()

    def getSelectedPoints(self):
        return self.selectedPoints


class BondSelect(AtomSelectionBase):

    multiselect = 2
    label = "Bond Selection"

    def __init__(self, loupe, **kwargs):
        super().__init__(loupe, **kwargs)

        self.bonds = []
        self.selectedBonds = loupe.selectedBonds

    def selectCallback(self):
        if len(self.selectedPoints) != 2:
            return

        (p1, p2) = self.selectedPoints
        p1, p2 = int(p1), int(p2)
        if p1 < p2:
            sel = (p1, p2)
        else:
            sel = (p2, p1)
        if sel in self.selectedBonds:
            self.selectedBonds.remove(sel)
        else:
            self.selectedBonds.add(sel)

        self.clearSelection()
        self.writeSelectedBonds()

    def writeSelectedBonds(self):
        s, n, l = ("", len(self.selectedBonds), list(self.selectedBonds))
        for i in range(n):
            bond = l[i]
            s += f"    [{bond[0]}, {bond[1]}]"
            if i < n - 1:
                s += ",\n"
            else:
                s += "\n"
        self.loupe.bondsTextEdit.setText(f"[\n{s}]")


class AtomAlignSelect(AtomSelectionBase):
    multiselect = 3
    label = "Align Atoms Selection"

    def __init__(self, loupe, **kwargs):
        super().__init__(loupe, **kwargs)

        self.atoms = []
        self.selectedAtoms = loupe.selectedAlignAtoms

    def selectCallback(self):
        if len(self.selectedPoints) != 3:
            return

        self.applySelectedAtoms()
        self.clearSelection()

    def applySelectedAtoms(self):
        self.loupe.selectedAlignAtoms = self.selectedPoints
        self.loupe.selectedAlignConfIndex = self.loupe.n

        self.loupe.updateCurrentR()
        self.loupe.refresh()
