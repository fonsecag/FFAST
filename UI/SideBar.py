from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QEvent
from UI.Templates import Widget, ContentBar, ObjectListItem, ObjectList
from config.uiConfig import configStyleSheet

class DatasetModelItem(ObjectListItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, layout = 'horizontal', **kwargs)
        self.setFixedHeight(40)

class DatasetObjectList(ObjectList):
    def __init__(self, handler):
        super().__init__(handler, DatasetModelItem)
        self.layout.setSpacing(2)
        from Utils.misc import rgbToHex, mixColors
        c1, c2 = (255,0,0), (100, 100, 100)
        c3 = mixColors(c1, c2)
        self.newObject("test", color = rgbToHex(*c1))
        self.newObject("test2", color = rgbToHex(*c2))
        self.newObject("test3", color = rgbToHex(*c3))

class SideBar(ContentBar):
    def __init__(self, handler):
        super().__init__(handler)
        self.handler = handler
        self.setupContent()

    def setupContent(self):
        # dataset
        self.datasetsList = DatasetObjectList(self.handler)
        self.addContent("DATASETS", widget = self.datasetsList)
        self.addContent("MODELS")


