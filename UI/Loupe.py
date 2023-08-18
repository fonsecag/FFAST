from events import EventChildClass
from UI.Templates import (
    Widget,
    ContentBar,
    ObjectComboBox,
    SettingsPane,
    Widget,
    Slider,
    ToolButton,
)
from PySide6 import QtCore, QtGui, QtWidgets
import logging
from vispy import scene
import numpy as np
from vispy.geometry.generation import create_sphere
import asyncio
from config.userConfig import Settings, getConfig
from vispy.scene.cameras.turntable import TurntableCamera
from vispy.visuals.transforms import STTransform
from vispy.util import keys
from UI.loupeProperties import VisualElement

logger = logging.getLogger("FFAST")


class RectangleSelection(VisualElement):
    def __init__(self, *args, parent=None, **kwargs):
        self.rectangle = scene.visuals.Rectangle(
            center=[0, 0],
            color=(0.5, 0.5, 1, 0.3),
            height=1,
            width=1,
            parent=parent,
            border_width=2,
            border_color=(0.5, 0.5, 1, 0.8),
        )
        self.rectangle.pos = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
        super().__init__(*args, **kwargs, singleElement=self.rectangle)

    def setPosition(self, arr):
        self.rectangle.pos = arr


class SideBar(ContentBar):
    def __init__(self, handler, **kwargs):
        super().__init__(handler, **kwargs)
        self.handler = handler
        self.setupContent()

    def setupContent(self):
        pass


class SceneCanvas(scene.SceneCanvas):

    mouseoverActive = False
    mouseClickActive = False
    rectangleSelectActive = False
    widget = None
    pickingColors = None
    isCtrlDragging = False
    draggingStart = [0, 0]

    def __init__(self, widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget = widget

    def getPickingRender(self, pos0=None, pos1=None):
        for element in self.widget.elements.values():
            element.draw(picking=True, pickingColors=self.pickingColors)

        tr = self.transforms.get_transform("canvas", "framebuffer")

        if (pos0 is not None) and (pos1 is not None):
            p0 = tr.map(pos0)[:2]
            p1 = tr.map(pos1)[:2]
            img = self.render(
                crop=(
                    min(p0[0], p1[0]),
                    min(p0[1], p1[1]),
                    np.abs(p1[0] - p0[0]),
                    np.abs(p1[1] - p0[1]),
                )
            )
        elif (pos0 is not None) and (pos1 is None):
            p = tr.map(pos0)[:2]
            img = self.render(crop=(p[0], p[1], 1, 1))
        else:
            img = self.render()
        return img

    def getAtomIndexAtPosition(self, pos, refresh=True):
        img = self.getPickingRender(pos)
        # single pixel right in the middle
        color = img[0, 0]
        idx = self.colorToIndex(color)

        if (idx is not None) and (idx >= self.widget.nAtoms):
            idx = None

        if refresh:
            self.widget.visualRefresh(force=True)
        return idx

    def getAtomIndicesInRectangle(self, pos0, pos1, refresh=False):
        img = self.getPickingRender(pos0, pos1)
        colors = img.reshape(-1, 4)
        colors = colors[colors[:, 2] == 255, :3]
        uniqueColors = np.unique(colors, axis=0)

        indices = []
        for color in uniqueColors:
            idx = self.colorToIndex(color)
            if idx is not None:
                indices.append(idx)

        if refresh:
            self.widget.visualRefresh(force=True)

        return indices

    def on_mouse_press(self, event):
        if not self.mouseClickActive:
            return
        # https://vispy.org/api/vispy.scene.events.html

        # left click only
        if event.button != 1:
            return

        if self.widget.loupe.selectedDatasetKey is None:
            return

        if keys.CONTROL in event.modifiers and self.rectangleSelectActive:
            self.isCtrlDragging = True
            self.draggingStart = event.pos
        else:
            point = self.getAtomIndexAtPosition(event.pos, refresh=False)
            self.widget.addSelectedAtom(point, refresh=True)

    def on_mouse_release(self, event):

        wasCtrlDragging = self.isCtrlDragging
        self.isCtrlDragging = False

        if not self.mouseClickActive:
            return
        # https://vispy.org/api/vispy.scene.events.html

        # left click only
        if event.button != 1:
            return

        if self.widget.loupe.selectedDatasetKey is None:
            return

        if wasCtrlDragging and self.rectangleSelectActive:
            pos0, pos1 = self.draggingStart, event.pos
            self.draggingStart = np.array([0, 0])

            d = np.sqrt(np.sum(pos1 - pos0) ** 2)
            if d > 1e-8:
                indices = self.getAtomIndicesInRectangle(
                    pos0, pos1, refresh=False
                )
                self.widget.hideSelectionRectangle()
                self.widget.addSelectedAtoms(indices, refresh=True)

    def on_mouse_move(self, event):

        if self.mouseClickActive and not event.is_dragging:
            # not refreshing because we know we will refresh after setting the hovered point
            point = self.getAtomIndexAtPosition(event.pos, refresh=False)
            self.widget.setHoveredPoint(point, refresh=True)

        if self.rectangleSelectActive and self.isCtrlDragging:
            self.widget.setSelectionRectanglePos(self.draggingStart, event.pos)

    def on_resize(self, *args):
        scene.SceneCanvas.on_resize(self, *args)
        # self.plotWidget.onResize()

    def refreshPickingColors(self, N):
        ids = np.arange(N)
        colors = np.ones((N, 4)) * 255
        colors[:, 0] = ids % 256
        colors[:, 1] = ids // 256

        self.pickingColors = colors / 255

    def colorToIndex(self, color):
        if color[2] != 255:
            return None
        idx = color[0] + color[1] * 256
        return idx


class Camera(TurntableCamera):

    parentCanvas = None

    def __init__(self, parentCanvas):
        self.parentCanvas = parentCanvas
        super().__init__()

    def view_changed(self):
        self.parentCanvas.onCameraChange()
        return TurntableCamera.view_changed(self)


class InteractiveCanvas(Widget):
    activeAtomSelectTool = None
    hoveredPoint = None
    nAtoms = -1
    hasBeenInited = False
    _currentR = None
    currentTransformations = []
    dataset = None

    def __init__(self, loupe, **kwargs):
        super().__init__(layout="vertical", **kwargs)

        self.canvas = SceneCanvas(self, bgcolor=getConfig("loupeBGColor"), create_native=False)

        self.elements = {}
        self.props = {}

        self.canvas.create_native()
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = Camera(self)
        self.camera = self.view.camera

        self.grid = self.newGrid()

        self.scene = self.view.scene
        self.loupe = loupe
        self.canvas.native.setParent(loupe)
        self.layout.addWidget(self.canvas.native)
        self.addAtomSelectToolbar()
        self.setActiveAtomSelectTool(None)

        self.createSelectionRectangle()

        self.freeze()

    ## VISUAL ELEMENTS & PROPERTIES

    def newGrid(self):
        return self.canvas.central_widget.add_grid(margin=4)

    def addVisualElement(self, Element, name, viewParent=False):
        if viewParent:
            el = Element(parent=self.view)
        else:
            el = Element(parent=self.scene)
        el.canvas = self
        self.elements[name] = el

        return el

    def visualRefresh(self, force=False):
        for element in self.elements.values():
            if (
                force or element.visualRefreshQueued
            ):  # and (not element.hidden):
                element.draw(picking=False, pickingColors=None)
                element.visualRefreshQueued = False

    def addProperty(self, Prop):
        prop = Prop()
        prop.canvas = self
        self.props[prop.key] = prop

    def addAtomSelectToolbar(self):
        self.atomSelectBar = Widget(color="@BGColor1", layout="horizontal")
        self.atomSelectBar.setFixedHeight(40)
        self.layout.insertWidget(0, self.atomSelectBar)

        self.atomSelectBar.setContentsMargins(8, 0, 8, 0)

        self.atomSelectBar.label1 = QtWidgets.QLabel("/")
        self.atomSelectBar.label2 = QtWidgets.QLabel("/")
        self.atomSelectBar.cancelButton = ToolButton(
            lambda x: self.setActiveAtomSelectTool(), "close"
        )

        self.atomSelectBar.layout.addWidget(self.atomSelectBar.label1)
        self.atomSelectBar.layout.addWidget(self.atomSelectBar.label2)
        self.atomSelectBar.layout.addWidget(self.atomSelectBar.cancelButton)

    ## INIT

    def setDataset(self, dataset):
        self.hasBeenInited = False
        self.dataset = dataset
        self.nAtoms = self.dataset.getNAtoms()

        for prop in self.props.values():
            prop.onDatasetInit()

        for element in self.elements.values():
            if not element.disabled:
                element.onDatasetInit()

        self.hasBeenInited = True
        self.visualRefresh()
        # self.onNewGeometry()
        self.canvas.refreshPickingColors(self.dataset.getNAtoms())

    def size(self):
        return self.canvas.size

    ## GEOMETRY

    def getR(self, index=None):
        return self.dataset.getCoordinates(indices=index)
        # return R - np.mean(R, axis=0)

    def applyTransformation(self, R, vOrM):
        # is vector
        if vOrM.ndim == 1:
            return R + vOrM
        elif vOrM.ndim == 2:
            return R @ vOrM
        else:
            return R

    def setCurrentR(self):
        R = self.getCurrentR()

        for vOrM in self.currentTransformations:
            R = self.applyTransformation(R, vOrM)

        self._currentR = R

    def getCurrentR(self):
        if self._currentR is None:
            return self.getR(self.index)
        else:
            return self._currentR

    def setIndex(self, index):
        if self.dataset is None:
            return
        index = min(index, self.dataset.getN() - 1)
        self.index = index
        self.onNewGeometry()

    def resetCurrentR(self):
        self._currentR = None
        self.currentTransformations = []

    def onNewGeometry(self):
        if not self.hasBeenInited:
            return

        self.resetCurrentR()

        postProps = []
        for prop in self.props.values():
            if prop.changesR:
                prop.onNewGeometry()
            else:
                postProps.append(prop)

        self.setCurrentR()

        for prop in postProps:
            prop.onNewGeometry()

        for element in self.elements.values():
            if not element.disabled:
                element.onNewGeometry()

        if self.activeAtomSelectTool is not None:
            self.activeAtomSelectTool.updateInfo()
        self.visualRefresh()

    ## CAMERA
    def onCameraChange(self):
        for prop in self.props.values():
            prop.onCameraChange()

        for element in self.elements.values():
            element.onCameraChange()

        self.visualRefresh()

    ## PICKING
    def setHoveredPoint(self, index, refresh=True):
        if self.activeAtomSelectTool is not None:
            self.activeAtomSelectTool.hoverAtom(index)
        if refresh:
            self.visualRefresh(force=True)

    def addSelectedAtom(self, index, refresh=True):
        if self.activeAtomSelectTool is not None:
            self.activeAtomSelectTool.selectAtom(index)
        if refresh:
            self.visualRefresh(force=True)

    def addSelectedAtoms(self, indices, refresh=True):
        if self.activeAtomSelectTool is not None:
            self.activeAtomSelectTool.selectAtoms(indices)
        if refresh:
            self.visualRefresh(force=True)

    def isActiveAtomSelectTool(self, tool):
        if tool is None:
            return self.activeAtomSelectTool is None
        return isinstance(self.activeAtomSelectTool, tool)

    def setActiveAtomSelectTool(self, tool=None):
        if (tool is not None) and self.isActiveAtomSelectTool(tool):
            self.setActiveAtomSelectTool(None)
            return

        if tool is None:
            self.activeAtomSelectTool = None
            self.canvas.mouseoverActive = False
            self.canvas.mouseClickActive = False
            self.canvas.rectangleSelectActive = False
            self.atomSelectBar.hide()
        else:
            self.activeAtomSelectTool = tool(self)
            self.canvas.mouseoverActive = True
            self.canvas.mouseClickActive = True
            self.canvas.rectangleSelectActive = (
                self.activeAtomSelectTool.rectangleSelect
            )
            self.atomSelectBar.show()

        self.onNewGeometry()

    def getSelectedAtoms(self):
        if self.activeAtomSelectTool is None:
            return None
        return self.activeAtomSelectTool.selectedPoints

    def getHoveredAtom(self):
        if self.activeAtomSelectTool is None:
            return None
        return self.activeAtomSelectTool.hoveredPoint

    def keyPressEvent(self, event):
        self.parent().keyPressEvent(event)

    ## SELECTION RECTANGLE
    def setSelectionRectanglePos(self, oldPos, newPos):
        if self.selectionRectangle.hidden:
            self.selectionRectangle.show()

        self.selectionRectangle.setPosition(
            np.array(
                [
                    [oldPos[0], oldPos[1]],
                    [newPos[0], oldPos[1]],
                    [newPos[0], newPos[1]],
                    [oldPos[0], newPos[1]],
                ]
            )
        )

    def createSelectionRectangle(self):
        self.selectionRectangle = self.addVisualElement(
            RectangleSelection, "SelectionRectangle", viewParent=True
        )

    def hideSelectionRectangle(self):
        self.selectionRectangle.hide()

    ## MISC
    def resizeEvent(self, event):
        self.onResize()
        return super(InteractiveCanvas, self).resizeEvent(event)

    def onResize(self):
        for prop in self.props.values():
            prop.onCanvasResize()

        for element in self.elements.values():
            element.onCanvasResize()

        self.visualRefresh()


class Loupe(Widget, EventChildClass):

    selectedDatasetKey = None
    index = 0
    videoPaused = True

    def __init__(self, handler, N, **kwargs):
        self.handler = handler
        self.env = handler.env
        super().__init__(layout="horizontal")
        EventChildClass.__init__(self)

        # SETTINGS
        self.initialiseSettings()

        self.resize(1100, 800)
        self.setWindowTitle(f"Loupe {N}")

        # SIDEBAR HERE
        self.sideBarContainer = Widget(layout="vertical", parent=self)
        self.sideBarContainer.setFixedWidth(300)
        self.layout.addWidget(self.sideBarContainer)

        self.datasetComboBox = ObjectComboBox(handler, hasDatasets=True)
        self.datasetComboBox.setOnIndexChanged(self.onDatasetSelected)
        self.datasetComboBox.setToolTip("Select dataset to show")
        self.sideBarContainer.layout.addWidget(self.datasetComboBox)

        self.sideBar = SideBar(handler, parent=self)
        self.sideBarContainer.layout.addWidget(self.sideBar)
        self.panes = {}

        # MAIN WINDOW HERE
        self.contentWindow = Widget(
            color="@BGColor2", layout="horizontal", parent=self
        )
        self.contentLayout = self.contentWindow.layout
        self.layout.addWidget(self.contentWindow)

        # CANVAS
        self.canvas = InteractiveCanvas(self, parent=self)
        self.canvas.settings = self.settings
        self.contentLayout.addWidget(self.canvas)

        # VIDEO PANE
        self.initialiseVideoPane()

        # EVENTS
        self.eventSubscribe("SUBDATASET_INDICES_CHANGED", self.onSubChanged)

    # SETTINGS
    def initialiseSettings(self):
        self.settings = Settings()
        self.settings.addAction("updateIndex", self.updateCurrentIndex)
        self.settings.addAction("updateGeometry", self.updateCurrentIndex)
        self.settings.addAction("cameraChange", self.onCameraChange)
        self.settings.addAction("pause", self.onPause)
        self.settings.addAction("datasetSelected", self.onDatasetSelected)
        self.settings.addAction("visualRefresh", self.visualRefresh)

        self.settings.addParameters(
            **{"videoFPS": [30], "videoSkipFrames": [0]}
        )

    def initialiseVideoPane(self):
        pane = Widget(parent=self, layout="vertical")

        # PLAYBACK
        playbackWindow = Widget(parent=pane, layout="vertical")
        self.indexSlider = Slider()
        self.indexSlider.setCallbackFunc(self.setIndex)
        playbackWindow.layout.addWidget(self.indexSlider)

        arrowBar = Widget(parent=pane, layout="horizontal")
        self.indexLeftArrow = ToolButton(self.onPrevious, "leftArrow")
        self.indexLeftArrow.setToolTip("Previous frame")
        self.playButton = ToolButton(self.toggleVideo, "start")
        self.playButton.setToolTip("Toggle animation")
        self.indexRightArrow = ToolButton(self.onNext, "rightArrow")
        self.indexRightArrow.setToolTip("Next frame")

        arrowBar.layout.addStretch()
        arrowBar.layout.addWidget(self.indexLeftArrow)
        arrowBar.layout.addWidget(self.playButton)
        arrowBar.layout.addWidget(self.indexRightArrow)
        arrowBar.layout.addStretch()

        playbackWindow.layout.addWidget(arrowBar)
        pane.layout.addWidget(playbackWindow)

        # SETTINGS

        settingsPane = SettingsPane(self.handler, self.settings, parent=pane)
        settingsPane.addSetting(
            "LineEdit",
            "FPS",
            settingsKey="videoFPS",
            isInt=True,
            nMin=1,
            nMax=5000,
        )

        settingsPane.addSetting(
            "LineEdit",
            "Skip frames",
            settingsKey="videoSkipFrames",
            isInt=True,
            nMin=0,
            nMax=99999,
        )

        pane.layout.addWidget(settingsPane)

        self.addSidebarPane("INDEX / VIDEO", pane)

    # DATASET
    def forceUpdate(self):
        self.datasetComboBox.forceUpdate()  # activate the selection
        if self.selectedDatasetKey is None:
            return
        self.updateCurrentIndex()

    def onDatasetSelected(self, key, force=False):
        # we force when sub indices change, becasue thats not reflected in the key
        if (not force) and (key == self.selectedDatasetKey):
            return
        self.selectedDatasetKey = key

        dataset = self.getSelectedDataset()
        self.canvas.setDataset(dataset)

        self.index = 0
        self.indexSlider.setMinMax(0, dataset.getN() - 1)
        self.updateCurrentIndex()

    def getSelectedDataset(self):
        if self.selectedDatasetKey is None:
            return None
        return self.env.getDataset(self.selectedDatasetKey)

    def onSubChanged(self, key):
        if self.selectedDatasetKey != key:
            return

        self.onDatasetSelected(key, force=True)

    # INDEX
    def updateCurrentIndex(self):
        self.indexSlider.setValue(self.index, quiet=True)
        self.canvas.setIndex(self.index)

    def setIndex(self, index):
        self.index = index
        if index == self.getNMax():
            self.onPause()

        self.updateCurrentIndex()

    # ELEMENTS
    def addVisualElement(self, Element, name, viewParent=False):
        self.canvas.addVisualElement(Element, name, viewParent=viewParent)

    def addCanvasProperty(self, Prop):
        self.canvas.addProperty(Prop)

    #  VIDEO/MOVING GEOMETRIES
    def toggleVideo(self):
        if self.videoPaused:
            self.onStart()
        else:
            self.onPause()

        if self.videoPaused:
            self.playButton.setIconByName("start")
        else:
            self.playButton.setIconByName("pause")

    def onPause(self):
        self.videoPaused = True

    def onStart(self):
        self.videoPaused = False
        self.videoTask = self.env.tm.simpleTask(self.runOnNext)

    async def runOnNext(self):
        while not self.videoPaused:
            if self.selectedDatasetKey is None:
                return
            self.onNext(skip=self.settings.get("videoSkipFrames"))
            await asyncio.sleep(1 / self.settings.get("videoFPS"))

    def onPrevious(self):
        index = max(0, self.index - 1)
        self.setIndex(index)

    def getNMax(self):
        return self.getSelectedDataset().getN() - 1

    def onNext(self, skip=0):
        index = min(self.getNMax(), self.index + 1 + skip)

        self.setIndex(index)

    def visualRefresh(self):
        self.canvas.visualRefresh(force=True)

    # SETTINGS PANE
    def addSidebarPane(self, name, pane):
        if name in self.panes:
            logger.error(
                f"Tried to add settings pane with name {name} but already exists"
            )
            return
        self.panes[name] = pane
        collapsibleWidget = self.sideBar.addContent(name, pane)
        # collapsibleWidget.setMaximumWidth(self.sideBar.width())
        if isinstance(pane, SettingsPane):
            collapsibleWidget.setCallback(pane.updateVisibilities)

    def getSettingsPane(self, name):
        return self.panes.get(name, None)

    def setSettingsPaneVisibility(self, *args):
        return self.sideBar.setContentVisibility(*args)

    # PICKING
    def setActiveAtomSelectTool(self, *args):
        return self.canvas.setActiveAtomSelectTool(*args)

    def isActiveAtomSelectTool(self, *args):
        return self.canvas.isActiveAtomSelectTool(*args)

    # SHORTCUTS
    # not yet working
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Q:
            print("Killing")
        elif event.key() == QtCore.Qt.Key_Enter:
            print("enter")
        # print(event.key(), QtCore.Qt.Key_Escape)
        # print(event.key()==QtCore.Qt.Key_Escape)
        event.accept()

    def onCameraChange(self):
        self.canvas.onCameraChange()
