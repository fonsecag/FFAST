from events import EventChildClass
import sys, os, time
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtUiTools import QUiLoader
from Utils.uiLoader import loadUi
import numpy as np
import logging
from Utils.qt import makeStretchingTable, stretchTableToContent

logger = logging.getLogger("FFAST")


class BasicTab(EventChildClass, QtWidgets.QWidget):
    def __init__(self, handler, *args, **kwargs):
        self.handler = handler
        super().__init__(*args, **kwargs)
        self.handler.addEventChild(self)
        loadUi(os.path.join(self.handler.uiFilesPath, "basicTab.ui"), self)
