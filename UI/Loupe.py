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

logger = logging.getLogger("FFAST")

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
    widget = None
    pickingColors = None

    def __init__(self, widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget = widget

    def getPickingRender(self, pos):
        for element in self.widget.elements:
            element.draw(picking = True, pickingColors = self.pickingColors)

        tr = self.transforms.get_transform("canvas", "framebuffer")
        p = tr.map(pos)[:2]
        if pos is None:
            img = self.render()
        else:
            img = self.render(region = (p[0],p[1], 1, 1))
        
        return img

    def getPointAtPosition(self, pos, refresh=True):
        img = self.getPickingRender(pos)
        # single pixel right in the middle
        color = img[0, 0]
        idx = self.colorToIndex(color)
        if refresh:
            self.widget.visualRefresh(force=True)
        return idx

    def on_mouse_press(self, event):
        if not self.mouseClickActive:
            return
        # https://vispy.org/api/vispy.scene.events.html

        # left click only
        if event.button != 1:
            return

        if self.widget.loupe.selectedDatasetKey is None:
            return

        point = self.getPointAtPosition(event.pos, refresh=False)
        self.widget.setSelectedPoint(point)

    def on_mouse_move(self, event):
        if not self.mouseoverActive:
            return

        # not refreshing because we know we will refresh after setting the hovered point
        point = self.getPointAtPosition(event.pos, refresh=False)
        self.widget.setHoveredPoint(point)

    def on_resize(self, *args):
        scene.SceneCanvas.on_resize(self, *args)
        # self.plotWidget.onResize()

    def refreshPickingColors(self, N):
        ids = np.arange(N)
        colors = np.ones((N, 4)) * 255
        colors[:, 0] = ids % 256
        colors[:, 1] = ids // 256

        self.pickingColors= colors/255

    def colorToIndex(self, color):
        if color[2] == 0:
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

    def __init__(self, loupe, **kwargs):
        super().__init__(layout="horizontal", **kwargs)

        self.canvas = SceneCanvas(
            self, keys="interactive", bgcolor="black", create_native=False
        )

        self.elements = []
        self.props = {}

        self.canvas.create_native()
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = Camera(self)
        self.camera = self.view.camera

        self.scene = self.view.scene
        self.loupe = loupe
        self.canvas.native.setParent(loupe)
        self.layout.addWidget(self.canvas.native)

        self.freeze()

    ## VISUAL ELEMENTS & PROPERTIES

    def addVisualElement(self, Element):
        el = Element(parent=self.scene)
        el.canvas = self
        self.elements.append(el)

    def visualRefresh(self, force = False):
        for element in self.elements:
            if force or element.visualRefreshQueued:
                element.draw(picking = False, pickingColors = None)
                element.visualRefreshQueued = False

    def addProperty(self, Prop):
        prop = Prop()
        prop.canvas = self
        self.props[prop.key] = prop

    ## INIT
    
    def setDataset(self, dataset):
        self.dataset = dataset

        for prop in self.props.values():
            prop.onDatasetInit()

        for element in self.elements:
            element.onDatasetInit()

        self.visualRefresh()
        self.canvas.refreshPickingColors(self.dataset.getNAtoms())

    ## GEOMETRY

    def getR(self, index=None):
        return self.dataset.getCoordinates(indices=index)
        # return R - np.mean(R, axis=0)

    def getCurrentR(self):
        return self.getR(self.index)

    def setIndex(self, index):
        self.index = index
        self.onNewGeometry()

    def onNewGeometry(self):
        self.canvas.measure_fps()  # TODO remove

        for prop in self.props.values():
            prop.onNewGeometry()

        for element in self.elements:
            element.onNewGeometry()

        self.visualRefresh()

    ## CAMERA
    def onCameraChange(self):
        for prop in self.props.values():
            prop.onCameraChange()

        for element in self.elements:
            element.onCameraChange()

        self.visualRefresh()

    ## PICKING
    def setHoveredPoint(self, index):
        self.visualRefresh(force=True)

    def setSelectedPoint(self, index):
        self.visualRefresh(force=True)

    def isActiveAtomSelectTool(self, tool):
        if tool is None:
            return self.activeAtomSelectTool is None
        return isinstance(self.activeAtomSelectTool, tool)

    def setActiveAtomSelectTool(self, tool=None):
        if self.isActiveAtomSelectTool(tool):
            return

        if tool is None:
            self.activeAtomSelectTool = None
            # self.currentAtomSelectionLabel.setText("")
            # self.cancelAtomSelectionButton.hide()
        else:
            self.activeAtomSelectTool = tool(self)
            # label = self.activeAtomSelectTool.label
            # self.currentAtomSelectionLabel.setText(
            #     f"Current selection tool: {label}"
            # )
            # self.cancelAtomSelectionButton.show()

        self.selectedPoints = []
        self.refresh()


class CanvasProperty:

    canvas = None
    index = None
    cleared = False

    def __init__(self, **kwargs):
        self.content = {}

    def onDatasetInit(self):
        pass

    def onNewGeometry(self):
        pass

    def onCameraChange(self):
        pass

    def set(self, **kwargs):
        self.content.update(kwargs)

    def _generate(self):
        self.generate()
        self.cleared = False

    def generate(self):
        pass

    def get(self, key):
        if self.cleared:
            self._generate()
        return self.content.get(key, None)

    def clear(self):
        self.cleared = True


class VisualElement(CanvasProperty):

    singleElement = None
    visualRefreshQueued = False

    def __init__(self, singleElement=None):
        self.setSingleElement(singleElement)

    def setSingleElement(self, element):
        self.singleElement = element

    def queueVisualRefresh(self):
        self.visualRefreshQueued = True

    def draw(self):
        pass

    def hide(self):
        if self.singleElement is not None:
            self.singleElement.hide()


class Loupe(Widget, EventChildClass):

    selectedDatasetKey = None
    index = 0
    videoPaused = True

    def __init__(self, handler, N, **kwargs):
        self.handler = handler
        self.env = handler.env
        super().__init__(color="green", layout="horizontal")
        EventChildClass.__init__(self)

        self.initialiseSettings()

        self.resize(1100, 800)
        self.setWindowTitle(f"Loupe {N}")

        # SIDEBAR HERE
        self.sideBarContainer = Widget(layout="vertical", parent=self)
        self.sideBarContainer.setFixedWidth(300)
        self.layout.addWidget(self.sideBarContainer)

        self.datasetComboBox = ObjectComboBox(handler, hasModels=False)
        self.datasetComboBox.setOnIndexChanged(self.onDatasetSelected)
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

    # SETTINGS
    def initialiseSettings(self):
        self.settings = Settings()
        self.settings.addAction("updateIndex", self.updateCurrentIndex)
        self.settings.addAction("updateGeometry", self.updateCurrentIndex)
        self.settings.addAction("pause", self.onPause)
        self.settings.addAction("datasetSelected", self.onDatasetSelected)

        self.settings.addParameters(
            **{"videoFPS": [30], "videoSkipFrames": [0],}
        )

    def initialiseVideoPane(self):
        pane = Widget(parent=self, layout="vertical")

        # PLAYBACK
        playbackWindow = Widget(parent=pane, layout="vertical")
        self.indexSlider = Slider()
        self.indexSlider.setCallbackFunc(self.setIndex)
        playbackWindow.layout.addWidget(self.indexSlider)

        arrowBar = Widget(parent=pane, layout="horizontal")
        self.indexLeftArrow = ToolButton(self.onPrevious, "left")
        self.playButton = ToolButton(self.toggleVideo, "start")
        self.indexRightArrow = ToolButton(self.onNext, "right")

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

    def onDatasetSelected(self, key):
        if key == self.selectedDatasetKey:
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
    def addVisualElement(self, Element):
        self.canvas.addVisualElement(Element)

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

    # SETTINGS PANE
    def addSidebarPane(self, name, pane):
        if name in self.panes:
            logger.error(f'Tried to add settings pane with name {name} but already exists')
            return
        self.panes[name] = pane
        self.sideBar.addContent(name, pane)

    def getSettingsPane(self, name):
        return self.panes.get(name, None)

    # PICKING
    def setActiveAtomSelectTool(self, *args):
        return self.canvas.setActiveAtomSelectTool(*args)
    
    def isActiveAtomSelectTool(self, *args):
        return self.canvas.isActiveAtomSelectTool(*args)