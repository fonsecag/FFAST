from events import EventWidgetClass
import os
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtUiTools import QUiLoader
from Utils.uiLoader import loadUi
from collections import defaultdict
import logging
import numpy as np
from vispy import scene
from config.atoms import atomColors, covalentRadii, covalentBonds
from scipy.spatial import distance_matrix
from UI.utils import CodeTextEdit, CollapseButton, getIcon
import vispy
import ast
from client.mathUtils import alignConfiguration

logger = logging.getLogger("FFAST")
lightGrayValue = 0.7


class BottomTabWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        self.layout = layout


class InteractiveCanvas(scene.SceneCanvas):

    plotWidget = None

    def __init__(self, plotWidget):
        super().__init__(
            keys="interactive", bgcolor="black", create_native=False
        )
        self.plotWidget = plotWidget
        self.create_native()

    def getPickingRender(self, refresh=True, pos=None):
        av = self.plotWidget.atomsVis
        bv = self.plotWidget.bondsVis

        bv.visible = False
        av.spherical = False

        r = self.plotWidget.getCurrentR()
        colors = self.plotWidget.colorIDs
        av.set_data(
            pos=r,
            size=self.plotWidget.atomSizes,
            face_color=colors,
            edge_width=0,
        )
        av.update_gl_state(blend=False)

        tr = self.transforms.get_transform("canvas", "framebuffer")
        p = tr.map(pos)[:2]
        if pos is None:
            img = self.render()
        else:
            img = self.render(crop=(p[0], p[1], 1, 1))

        av.spherical = True

        if refresh:
            self.plotWidget.refresh()

        return img

    def getPointAtPosition(self, pos, refresh=True):

        img = self.getPickingRender(refresh=refresh, pos=pos)
        # single pixel right in the middle
        color = img[0, 0]
        idx = self.plotWidget.colorToIndex(color)
        return idx

    def on_mouse_press(self, event):
        # https://vispy.org/api/vispy.scene.events.html

        # left click only
        if event.button != 1:
            return

        if self.plotWidget.selectedDatasetKey is None:
            return

        point = self.getPointAtPosition(event.pos, refresh=False)
        self.plotWidget.setSelectedPoint(point)

    def on_mouse_move(self, event):

        if self.plotWidget.selectedDatasetKey is None:
            return

        # not refreshing because we know we will refresh after setting the hovered point
        point = self.getPointAtPosition(event.pos, refresh=False)
        self.plotWidget.setHoveredPoint(point)


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

        p1, p2 = self.selectedPoints
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
        s, n, l = "", len(self.selectedBonds), list(self.selectedBonds)
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


class Loupe(QtWidgets.QWidget, EventWidgetClass):
    """
    Widget class of a popout window with 3D viewer and plots.

    This widget is mostly meant to be used on subdatasets, giving more detailed
    information on specific parts of a dataset. Creation and handling of loupes
    is done by the UIHandler, see `UIHandler.newLoupe`.
    """

    def __init__(self, handler, N, **kwargs):
        """Initialisation function.

        Args:
            handler: UIHandler passes itself to Loupe creation
            N (int): Integer that identifies which Loupe window this is
        """
        self.handler = handler
        super().__init__()
        loadUi(os.path.join(self.handler.uiFilesPath, "loupe.ui"), self)

        self.datasetSelection = []
        self.nPlotWidget = N

        self.setWindowTitle(f"Loupe {N}")
        self.comboBox.activated.connect(self.onComboBoxSelect)

        self.initialise3DPlot()
        self.initialiseVideoPlayback()
        self.initialiseSelections()

        self.eventSubscribe("DATASET_LOADED", self.refreshDatasetList)
        self.eventSubscribe("DATASET_NAME_CHANGED", self.refreshDatasetList)
        self.eventSubscribe(
            "SUBDATASET_INDICES_CHANGED", self.refreshDatasetSelection
        )
        self.eventSubscribe("DATASET_STATE_CHANGED", self.refreshDatasetList)

        self.selectedBonds = set()
        self.selectedPoints = []

        self.connectSidebar()
        self.applyVisualConfig()

        # self.refreshDatasetList(None)

    def applyVisualConfig(self):
        sheet = """
            QWidget#header,
            QWidget#sidebarWidget,
            QTabBar#sidebarWidget,
            QFrame#leftContainer,
            QFrame#rightContainer{
                background-color:@BGColor1;
            }

            QWidget#leftContent{
                background-color:@BGColor2;
            }
        """

        self.setStyleSheet(self.handler.applyConfigToStyleSheet(sheet))

        self.leftButton.setIcon(getIcon("leftarrow2"))
        self.startButton.setIcon(getIcon("rightarrow"))
        self.pauseButton.setIcon(getIcon("checklist_indeterminate"))
        self.rightButton.setIcon(getIcon("rightarrow2"))

    def refreshDatasetSelection(self, key=None):
        if (key is not None) and (key != self.selectedDatasetKey):
            return

        self.applyConfig()
        self.refresh()

    def initialiseSelections(self):
        self.selectedAlignAtoms = []
        self.selectedAlignConfIndex = None

        self.cancelAtomSelectionButton.clicked.connect(
            lambda: self.setActiveAtomSelectTool(None)
        )
        self.cancelAtomSelectionButton.hide()

    def initialise3DPlot(self):

        canvas = InteractiveCanvas(self)
        view = canvas.central_widget.add_view()
        view.camera = scene.TurntableCamera(up="z", fov=60)

        l = 0.90
        self.atomsVis = scene.visuals.Markers(
            pos=None,
            face_color=None,
            size=1,
            spherical=True,
            scaling=True,
            antialias=1,
            # edge_width=0.0015,
            edge_width=0,
            light_color=(1 - l, 1 - l, 1 - l),
            light_ambient=l,
            parent=view.scene,
        )
        view.add(self.atomsVis)

        # self.bondsVis = []
        self.bondsVis = scene.visuals.Line(
            pos=None,
            color=(lightGrayValue, lightGrayValue, lightGrayValue, 1),
            width=5,
            connect="segments",
            antialias=1,
            parent=view.scene,
        )
        view.add(self.bondsVis)

        self.canvas = canvas
        self.view = view
        self.mainFrameLayout.replaceWidget(self.plot3dPH, canvas.native)
        self.plot3dPH.deleteLater()
        self.plot3dPH = None

        self.n = 0
        self.updateCurrentR()

    def initialiseVideoPlayback(self):
        self.leftButton.clicked.connect(self.onPrevious)
        self.rightButton.clicked.connect(self.onNext)

        # TODO fps user controlled etc
        # Set timer for animation
        timer = QtCore.QTimer()
        timer.timeout.connect(self.onNext)
        timer.setInterval(int((1 / 60) * 1000))  # milliseconds
        self.timer = timer

        self.startButton.clicked.connect(self.onStart)
        self.pauseButton.clicked.connect(self.onPause)

    def connectSidebar(self):

        # add collapse button
        self.collapseSidebarButton = CollapseButton(
            self.handler, self.rightContainer, "right", 300
        )
        self.headerLayout.insertWidget(-1, self.collapseSidebarButton)

        # DYNAMIC BONDS
        self.dynamicBondsCB.stateChanged.connect(self.updateDynamicBonds)
        self.selectBondsButton.clicked.connect(
            lambda: self.setActiveAtomSelectTool(BondSelect)
        )

        self.bondsTextEdit = CodeTextEdit()
        self.bondsTextEdit.setEnabled(False)
        self.bondsTabLayout.insertWidget(2, self.bondsTextEdit)
        self.bondsTextEdit.setReturnCallback(self.readSelectedBonds)

        # ALIGN CONFIGS
        self.alignConfigsCB.stateChanged.connect(self.updateAlignConfigs)
        self.selectAlignAtomsButton.clicked.connect(
            lambda: self.setActiveAtomSelectTool(AtomAlignSelect)
        )


    def connectLoupe(self, loupePlotWidget):
        if loupePlotWidget is not None:
            lpw = loupePlotWidget(self.handler)
            self.bottomLayout.insertWidget(0, lpw)
            self.loupePlotWidget = lpw

    def readSelectedBonds(self):
        s = self.bondsTextEdit.toPlainText()
        l = ast.literal_eval(s)

        self.selectedBonds.clear()

        for bond in l:
            p1, p2 = int(bond[0]), int(bond[1])
            if p1 < p2:
                sel = (p1, p2)
            else:
                sel = (p2, p1)
            self.selectedBonds.add(sel)

        self.refresh()

    def updateDynamicBonds(self):
        dyn = self.dynamicBondsCB.isChecked()
        self.bondsTextEdit.setEnabled(not dyn)
        self.selectBondsButton.setEnabled(not dyn)

        if self.isActiveAtomSelectTool(BondSelect):
            self.setActiveAtomSelectTool(None)

        self.refresh()

    def updateAlignConfigs(self):
        al = self.alignConfigsCB.isChecked()
        self.alignConfigurations = al
        self.selectAlignAtomsButton.setEnabled(al)

        if self.isActiveAtomSelectTool(AtomAlignSelect):
            self.setActiveAtomSelectTool(None)

        self.updateCurrentR()
        self.refresh()

    def toggleSidebar(self):
        w = self.rightContainer.width()
        if w == 0:
            self.rightContainer.setFixedWidth(300)
        else:
            self.rightContainer.setFixedWidth(0)

    def getColorIDs(self):
        n = len(self.dataset.getElements())
        ids = np.arange(n)
        colors = np.ones((n, 4)) * 255
        colors[:, 0] = ids % 256
        colors[:, 1] = ids // 256

        return colors

    def colorToIndex(self, color):
        if color[2] == 0:
            return None
        idx = color[0] + color[1] * 256
        if idx >= len(self.dataset.getElements()):
            return None
        else:
            return idx

    def onStart(self):
        self.timer.start()

    def onPause(self):
        self.timer.stop()

    def onPrevious(self):
        self.n = max(0, self.n - 1)
        self.updateCurrentR()
        self.refresh()

    def onNext(self):
        nMax = self.getNMax() - 1
        self.n = min(nMax, self.n + 1)
        if self.n == nMax:
            self.onPause()

        self.updateCurrentR()
        self.refresh()

    def getNMax(self):

        activeIndices = self.getActiveIndices()
        if activeIndices is None:
            return self.dataset.getN()
        else:
            return len(activeIndices)

    def onComboBoxSelect(self, idx):
        key = self.datasetSelection[idx]
        self.onPause()
        self.n = 0
        self.selectDatasetKey(key)

    def refreshDatasetList(self, key=None):

        # self.applyConfig()
        # self.refresh()

        datasets = self.handler.env.getAllDatasets()
        self.datasetSelection.clear()

        if len(datasets) == 0:
            return

        cb = self.comboBox
        cb.clear()

        for dataset in datasets:
            self.datasetSelection.append(dataset.fingerprint)
            name = f"{dataset.getDisplayName()}"
            cb.addItem(name)

        key = self.selectedDatasetKey
        if key not in self.datasetSelection:
            key = None
        if key is None:
            key = self.datasetSelection[0]

        self.selectDatasetKey(key)

    def isActiveAtomSelectTool(self, tool):
        if tool is None:
            return self.activeAtomSelectTool is None
        return isinstance(self.activeAtomSelectTool, tool)

    def setActiveAtomSelectTool(self, tool=None):
        if self.isActiveAtomSelectTool(tool):
            return

        if tool is None:
            self.activeAtomSelectTool = None
            self.currentAtomSelectionLabel.setText("")
            self.cancelAtomSelectionButton.hide()
        else:
            self.activeAtomSelectTool = tool(self)
            label = self.activeAtomSelectTool.label
            self.currentAtomSelectionLabel.setText(
                f"Current selection tool: {label}"
            )
            self.cancelAtomSelectionButton.show()

        self.selectedPoints = []
        self.refresh()

    selectedDatasetKey = None
    dataset = None

    def selectDatasetKey(self, key):
        if self.selectedDatasetKey == key:
            return

        logger.info(f"loupe selected dataset is now: {key}")
        self.selectedDatasetKey = key

        for plotWidget in self.registeredPlots:
            plotWidget.setDatasetDependencies([key])

        self.applyConfig()
        self.refresh()

    def applyConfig(self):
        key = self.selectedDatasetKey
        if key is None:
            return

        dataset = self.handler.env.getDataset(key)
        self.dataset = dataset
        if dataset is None:
            logger.warning(f"loupe has {key} selected, but no dataset found")
            return

        self.n = 0
        z = dataset.getElements()

        self.atomColors = atomColors[z]
        self.atomSizes = covalentRadii[z] * 0.7
        self.atomSizesCurrent = np.zeros_like(self.atomSizes)

        # TODO put arbitrary scaling in a user-config file
        self.bondSizes = covalentBonds[z, z] * 1.1
        # TODO put arbitrary lenience in user-config file
        self.colorIDs255 = self.getColorIDs()
        self.colorIDs = self.colorIDs255 / 255

        self.edgeColor = np.ones((len(z), 4))
        self.updateCurrentR()

    def isDynamicBonds(self):
        return self.dynamicBondsCB.isChecked()

    def getBonds(self, r):
        if self.isDynamicBonds():
            d = distance_matrix(r, r)
            args = np.argwhere(d < self.bondSizes)
        else:
            args = np.array(list(self.selectedBonds))
        return args

    centralise = True
    alignConfigurations = True
    currentR = None

    def updateCurrentR(self):
        if self.dataset is None:
            return

        idx = self.n
        activeIndices = self.getActiveIndices()

        if activeIndices is not None:
            idx = activeIndices[idx]

        r = self.dataset.getCoordinates(idx)

        if (
            self.alignConfigurations
            and (self.selectedAlignConfIndex is not None)
            and (self.n != self.selectedAlignConfIndex)
        ):
            r0 = self.dataset.getCoordinates(self.selectedAlignConfIndex)
            if self.centralise:
                r0 = r0 - np.mean(r0, axis=0)
            r = alignConfiguration(
                r, r0, along=self.selectedAlignAtoms, com=True
            )

        elif self.centralise:
            r = r - np.mean(r, axis=0)

        self.currentR = r

    def getCurrentR(self):
        return self.currentR

    currentNMax = 0

    def refresh(self, bonds=True, renderReset=False):
        import time as time

        nMax = self.getNMax()
        self.currentNMax = nMax
        n = self.n

        r = self.getCurrentR()

        self.atomsVis.visible = True

        ec = self.edgeColor
        ec[:, :-1] = lightGrayValue
        # ew = np.zeros(ec.shape[0])
        size = self.atomSizesCurrent
        size[:] = self.atomSizes

        if self.hoveredPoint is not None:
            ec[self.hoveredPoint] = (0.5, 1, 0.5, 1)
            size[self.hoveredPoint] = self.atomSizes[self.hoveredPoint] * 1.1
            # ew[self.hoveredPoint] = 0.005

        if self.activeAtomSelectTool is not None:
            s = self.activeAtomSelectTool.getSelectedPoints()
            for idx in s:
                ec[idx] = (0.5, 0.5, 1, 1)
                size[idx] = self.atomSizes[idx] * 1.1
                # ew[idx] = 0.005

        self.atomsVis.set_data(
            pos=r,
            size=size,
            face_color=self.atomColors,
            edge_width=0.003,
            edge_color=ec,
        )
        self.bondsVis.visible = True  # TODO dependent on config or w/e

        if renderReset:
            # means the refresh got called after a canvas.getPickingRender
            # so labels dont need to get reset (nor bonds)
            return

        if bonds:
            bonds = self.getBonds(r)
            nBonds = len(bonds)

            if nBonds > 0:
                bonds = r[bonds]
                self.bondsVis.set_data(pos=bonds, width=5)
                self.bondsVis.visible = True
            else:
                self.bondsVis.set_data(width=0)

        # self.selectedIndicesLabel.setText(self.dataset.selectedIndicesLabel)
        self.nFramesLabel.setText(f"{n+1}/{nMax}")

    activeIndices = None

    def getActiveIndices(self):
        return self.activeIndices

    def setActiveIndices(self, idx):
        if (idx is None) or (len(idx) == 0):
            return
        self.activeIndices = idx
        self.onActiveIndicesChanged()

    def onActiveIndicesChanged(self):

        if self.currentNMax != self.getNMax():
            self.n = 0

        self.updateCurrentR()
        self.refresh()

    hoveredPoint = None

    def setHoveredPoint(self, idx):
        self.hoveredPoint = idx
        self.refresh(renderReset=True)

    multiselect = 4
    activeAtomSelectTool = None

    def setSelectedPoint(self, idx):
        if self.activeAtomSelectTool is not None:
            self.activeAtomSelectTool.selectAtom(idx)
        self.refresh(renderReset=True)

    def clearSelectedPoints(self):
        self.selectedPoints.clear()

    def resetMode(self):
        self.multiselect = 4
        self.clearSelectedPoints()

    def newTab(self, name):
        tabWidget = BottomTabWindow()
        self.bottomTabWidget.addTab(tabWidget, name)

        return tabWidget

    registeredPlots = []

    def registerLoupePlot(self, plotWidget):
        self.registeredPlots.append(plotWidget)
