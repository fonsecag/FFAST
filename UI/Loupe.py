from events import EventChildClass
from UI.Templates import Widget, ContentBar, ObjectComboBox
from PySide6 import QtCore, QtGui, QtWidgets
import logging 
from vispy import scene
import numpy as np 
from vispy.geometry.generation import create_sphere
import asyncio

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

    def __init__(self, loupe):
        super().__init__(layout='horizontal')


        self.canvas = scene.SceneCanvas(keys="interactive", bgcolor="black", create_native=False)
        self.canvas.create_native()
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = 'turntable'
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
        print("RESIZING")
        # self.plotWidget.onResize()

    ## VISUAL ELEMENTS

    def addVisualElement(self, Element):
        el = Element(parent = self.scene)
        self.elements.append(el)

    ## INIT

    def onDatasetInit(self):
        for element in self.elements:
            element.onDatasetInit()

    ## GEOMETRY

    def onNewGeometry(self):
        self.canvas.measure_fps()

        for element in self.elements:
            element.onNewGeometry()

    def setGeometry(self, R):
        self.R = R
        self.onNewGeometry()

class VisualElement:

    hasElement = False
    canvas = None

    def __init__(self, parent = None, element = None):
        if element is None:
            self.hasElement = False
        else:
            self.hasElement = True
            self.element = element

    def onDatasetInit(self):
        pass

    def onNewGeometry(self):
        pass

class Loupe(Widget, EventChildClass):

    selectedDatasetKey = None
    index = 0
    videoPaused = True
    videoInterval = 1./60 # s

    def __init__(self, handler, N, **kwargs):
        self.handler = handler
        self.env = handler.env
        super().__init__(color="green", layout = 'horizontal')
        EventChildClass.__init__(self)

        self.resize(1100, 800)
        self.setWindowTitle(f"Loupe {N}")

        # SIDEBAR HERE
        self.sideBarContainer = Widget(layout='vertical')
        self.sideBarContainer.setFixedWidth(300)
        self.layout.addWidget(self.sideBarContainer)

        self.datasetComboBox = ObjectComboBox(handler, hasModels=False)
        self.datasetComboBox.setOnIndexChanged(self.onDatasetSelected)
        self.sideBarContainer.layout.addWidget(self.datasetComboBox)

        self.sideBar = SideBar(handler)
        self.sideBarContainer.layout.addWidget(self.sideBar)

        # MAIN WINDOW HERE
        self.contentWindow = Widget(color ="@BGColor2", layout = 'horizontal')
        self.contentLayout = self.contentWindow.layout
        self.layout.addWidget(self.contentWindow)

        # CANVAS
        self.canvas = InteractiveCanvas(self)
        self.contentLayout.addWidget(self.canvas)

        # UPDATES
        self.datasetComboBox.forceUpdate() # activate the selection

    def onDatasetSelected(self, key):
        if key == self.selectedDatasetKey:
            return
        
        self.selectedDatasetKey = key
        self.canvas.onDatasetInit()

        self.index = 0
        self.updateCurrentR()


        # TODO REMOVE
        if self.videoPaused:
            self.onStart()

    def getSelectedDataset(self):
        if self.selectedDatasetKey is None:
            return None
        return self.env.getDataset(self.selectedDatasetKey)

    # GEOMETRY
    def getCurrentR(self):
        return self.getSelectedDataset().getCoordinates(indices = self.index)

    def updateCurrentR(self):
        self.canvas.setGeometry(self.getCurrentR())

    # ELEMENTS
    def addVisualElement(self, Element):
        self.canvas.addVisualElement(Element)

    # VIDEO/MOVING GEOMETRIES
    def onStart(self):
        self.videoPaused = False
        self.videoTask = self.env.tm.simpleTask(self.runOnNext)

    async def runOnNext(self):
        while not self.videoPaused:
            self.onNext()
            await asyncio.sleep(self.videoInterval)

    def onPause(self):
        self.videoPaused = True

    def onPrevious(self):
        self.n = max(0, self.n - 1)
        self.updateCurrentR()

    def getNMax(self):
        return self.getSelectedDataset().getN()

    def onNext(self):
        nMax = self.getNMax() - 1
        # self.index = min(nMax, self.index + 1) # TODO: back to max
        self.index = (self.index + 1) % nMax
        if self.index == nMax:
            self.onPause()

        self.updateCurrentR()

