from events import EventChildClass
from UI.Templates import Widget, ContentBar, ObjectComboBox
from PySide6 import QtCore, QtGui, QtWidgets
import logging 
from vispy import scene
import numpy as np 

logger = logging.getLogger("FFAST")

class SideBar(ContentBar):
    def __init__(self, handler, **kwargs):
        super().__init__(handler, **kwargs)
        self.handler = handler
        self.setupContent()

    def setupContent(self):
        pass

class InteractiveCanvas(scene.SceneCanvas):
    
    mouseoverActive = False

    def __init__(self):
        super().__init__(keys="interactive", bgcolor="black", create_native=False)
        # self.plotWidget = plotWidget
        self.create_native()
        # super().__init__(self)


        pos = np.random.normal(size=(100000, 3), scale=0.2)
        # one could stop here for the data generation, the rest is just to make the
        # data look more interesting. Copied over from magnify.py
        centers = np.random.normal(size=(50, 3))
        indexes = np.random.normal(size=100000, loc=centers.shape[0] / 2,
                                scale=centers.shape[0] / 3)
        indexes = np.clip(indexes, 0, centers.shape[0] - 1).astype(int)

        scales = 10**(np.linspace(-2, 0.5, centers.shape[0]))[indexes][:, np.newaxis]
        pos *= scales
        pos += centers[indexes]
        colors = np.random.random((len(pos),4))

        scatter = scene.visuals.Markers(scaling=True, spherical=True)
        colors = np.random.random((len(pos),4))
        scatter.set_data(pos, edge_width=0.002, face_color=colors, size=0.02) 

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

    # def addObject(self, )

    # def on_resize(self, *args):
    #     scene.SceneCanvas.on_resize(self, *args)
    #     self.plotWidget.onResize()


class Loupe(Widget, EventChildClass):

    selectedDatasetKey = None

    def __init__(self, handler, N, **kwargs):
        self.handler = handler
        super().__init__(color="green", layout = 'horizontal')
        EventChildClass.__init__(self)

        self.resize(1100, 800)
        self.setWindowTitle(f"Loupe {N}")

        # SIDEBAR HERE
        self.sideBarContainer = Widget(layout='vertical')
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
        self.canvas = InteractiveCanvas()
        self.contentLayout.addWidget(self.canvas.native)

    def onDatasetSelected(self, key):
        if key == self.selectedDatasetKey:
            return
        
        self.selectedDatasetKey = key

    


