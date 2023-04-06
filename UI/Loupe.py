from events import EventChildClass
from UI.Templates import (
    Widget,
    ContentBar,
    ObjectComboBox,
    SettingsPane,
    Widget,
    Slider,
    ToolButton
)
from PySide6 import QtCore, QtGui, QtWidgets
import logging
from vispy import scene
import numpy as np
from vispy.geometry.generation import create_sphere
import asyncio
from config.userConfig import Settings

logger = logging.getLogger("FFAST")


class SideBar(ContentBar):
    def __init__(self, handler, **kwargs):
        super().__init__(handler, **kwargs)
        self.handler = handler
        self.setupContent()

    def setupContent(self):
        pass


class InteractiveCanvas(Widget):

    mouseoverActive = False

    def __init__(self, loupe, **kwargs):
        super().__init__(layout="horizontal", **kwargs)

        self.canvas = scene.SceneCanvas(
            keys="interactive", bgcolor="black", create_native=False
        )
        self.canvas.create_native()
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = "turntable"
        self.scene = self.view.scene
        self.loupe = loupe
        self.canvas.native.setParent(loupe)
        self.layout.addWidget(self.canvas.native)

        self.elements = []

        self.freeze()

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
        if not self.mouseoverActive:
            return
        # https://vispy.org/api/vispy.scene.events.html

        # left click only
        if event.button != 1:
            return

        if self.plotWidget.selectedDatasetKey is None:
            return

        point = self.getPointAtPosition(event.pos, refresh=False)
        self.plotWidget.setSelectedPoint(point)

    def on_mouse_move(self, event):
        if not self.mouseoverActive:
            return

        # not refreshing because we know we will refresh after setting the hovered point
        point = self.getPointAtPosition(event.pos, refresh=False)
        self.plotWidget.setHoveredPoint(point)

    def on_resize(self, *args):
        scene.SceneCanvas.on_resize(self, *args)
        # self.plotWidget.onResize()

    ## VISUAL ELEMENTS

    def addVisualElement(self, Element):
        el = Element(parent=self.scene)
        el.canvas = self
        self.elements.append(el)

    def visualRefresh(self):

        for element in self.elements:
            if element.visualRefreshQueued:
                element.draw()
                element.visualRefreshQueued = False

    ## INIT

    def setDataset(self, dataset):
        self.dataset = dataset

        for element in self.elements:
            element.onDatasetInit()

        self.visualRefresh()

    ## GEOMETRY
    def getCurrentR(self):
        return self.dataset.getCoordinates(indices=self.index)

    def setIndex(self, index):
        self.index = index
        self.onNewGeometry()

    def onNewGeometry(self):
        self.canvas.measure_fps()  # TODO remove

        for element in self.elements:
            element.onNewGeometry()

        self.visualRefresh()


class VisualElement:

    hasElement = False
    visualRefreshQueued = False
    canvas = None
    index = None

    def __init__(self, element=None):
        if element is None:
            self.hasElement = False
        else:
            self.hasElement = True
            self.element = element

    def onDatasetInit(self):
        pass

    def onNewGeometry(self):
        pass

    def queueVisualRefresh(self):
        self.visualRefreshQueued = True

    def draw(self):
        pass


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

        # MAIN WINDOW HERE
        self.contentWindow = Widget(
            color="@BGColor2", layout="horizontal", parent=self
        )
        self.contentLayout = self.contentWindow.layout
        self.layout.addWidget(self.contentWindow)

        # CANVAS
        self.canvas = InteractiveCanvas(self, parent=self)
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
        playbackWindow = Widget(parent = pane, layout = 'vertical')
        self.indexSlider = Slider()
        self.indexSlider.setCallbackFunc(self.setIndex)
        playbackWindow.layout.addWidget(self.indexSlider)

        arrowBar = Widget(parent = pane, layout = 'horizontal')
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
        self.indexSlider.setMinMax(0, dataset.getN()-1)
        self.updateCurrentIndex()

    def getSelectedDataset(self):
        if self.selectedDatasetKey is None:
            return None
        return self.env.getDataset(self.selectedDatasetKey)

    # INDEX
    def updateCurrentIndex(self):
        # self.indexSlider.setValue(self.index)
        self.canvas.setIndex(self.index)

    # ELEMENTS
    def addVisualElement(self, Element):
        self.canvas.addVisualElement(Element)

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
            self.onNext(skip = self.settings.get("videoSkipFrames"))
            await asyncio.sleep(1/self.settings.get("videoFPS"))

    def onPrevious(self):
        index = max(0, self.index - 1)
        self.setIndex(index)

    def getNMax(self):
        return self.getSelectedDataset().getN() - 1

    def onNext(self, skip = 0):
        index = min(self.getNMax(), self.index + 1 + skip) 

        self.setIndex(index)

    def setIndex(self, index):

        self.index = index
        if index == self.getNMax():
            self.onPause()

        self.updateCurrentIndex()

    # SETTINGS PANE
    def addSidebarPane(self, name, pane):
        self.sideBar.addContent(name, pane)
