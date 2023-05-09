class CanvasProperty:

    canvas = None
    index = None
    cleared = False
    changesR = False

    def __init__(self, **kwargs):
        self.content = {}

    def onDatasetInit(self):
        pass

    def onNewGeometry(self):
        pass

    def onCameraChange(self):
        pass

    def onCanvasResize(self):
        pass

    def set(self, **kwargs):
        self.content.update(kwargs)
        self.cleared = False

    def _generate(self):
        self.generate()

    def generate(self):
        pass

    def get(self, key=None):
        if self.cleared:
            self._generate()

        if (key is None) and (len(self.content) == 1):
            return self.content.get(next(iter(self.content)))

        return self.content.get(key, None)

    def clear(self):
        self.cleared = True


class AtomSelectionBase:
    multiselect = 1
    cycle = False
    label = "N/A"

    def __init__(self, canvas):
        self.selectedPoints = []
        self.hoveredPoint = None
        self.canvas = canvas
        self.updateInfo()

    def clearSelection(self):
        nSel = len(self.selectedPoints)
        self.selectedPoints = []

    def selectCallback(self):
        pass

    def hoverAtom(self, idx):
        self.hoveredPoint = idx
        self.hoverCallback()

    def hoverCallback(self):
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

    def getTitleLabel(self):
        return self.label

    def getInfoLabel(self):
        return ""

    def updateInfo(self):
        self.canvas.atomSelectBar.label1.setText(
            f"Selecting: {self.getTitleLabel()}"
        )
        self.canvas.atomSelectBar.label2.setText(self.getInfoLabel())


class VisualElement(CanvasProperty):

    singleElement = None
    visualRefreshQueued = False
    pickingVisible = False
    disabled = False
    hidden = False

    def __init__(self, singleElement=None):
        self.setSingleElement(singleElement)

    def setSingleElement(self, element):
        self.singleElement = element

    def queueVisualRefresh(self):
        if self.disabled:
            return
        self.visualRefreshQueued = True

    def _draw(self, **kwargs):
        pass

    def draw(self, picking=False, **kwargs):

        if self.disabled:
            return

        if self.singleElement is None:
            return self._draw(picking=picking, **kwargs)

        if not picking:
            if not self.singleElement.visible:
                self.singleElement.visible = True
            return self._draw(picking=False, **kwargs)

        if not self.singleElement.visible and self.pickingVisible:
            self.singleElement.visible = True
            return

        if self.singleElement.visible and not self.pickingVisible:
            self.singleElement.visible = False

        return self._draw(picking=True, **kwargs)

    def disable(self):
        if self.singleElement is not None:
            self.singleElement.visible = False
        self.disabled = True

    def hide(self):
        self.hidden = True
        if self.singleElement:
            self.singleElement.visible = False

    def show(self):
        self.hidden = False
        if self.singleElement:
            self.singleElement.visible = True
