from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QEvent
from UI.Templates import Widget, ContentBar
from config.uiConfig import configStyleSheet

class SideBar(ContentBar):
    def __init__(self, handler):
        super().__init__(handler)
        self.handler = handler
        self.setupContent()

    def setupContent(self):
        # dataset
        self.addContent("DATASETS")
        self.addContent("MODELS")

        
