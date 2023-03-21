from events import EventChildClass
from PySide6 import QtCore, QtGui, QtWidgets
from config.uiConfig import configStyleSheet
from UI.Templates import TabWidget, Widget


class MainContentTabWidget(TabWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
