from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QEvent
from UI.Templates import MenuButton, FramelessResizableWindow, MenuBar, Widget
from config.uiConfig import configStyleSheet
from UI.SideBar import SideBar

class Color(QtWidgets.QWidget):

    def __init__(self, color):
        super(Color, self).__init__()
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(color))
        self.setPalette(palette)

        self.setMouseTracking(True)

class MainWindow(FramelessResizableWindow):
    def __init__(self, handler):
        super().__init__()
        self.handler = handler
        self.setWindowTitle("FFAST")

        self.setFocus()
        self.setGeometry(200, 200, 800, 600)

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0,0,0,0)
        self.setLayout(self.layout)

        self.menuBar = MenuBar(handler, self)
        self.menuBar.onClose = self.handler.quitEvent
        self.layout.addWidget(self.menuBar)

        self.mainContainer = Widget()
        self.containerLayout = QtWidgets.QHBoxLayout()
        self.mainContainer.setLayout(self.containerLayout)
        self.containerLayout.setContentsMargins(0,0,0,0)
        self.containerLayout.setSpacing(0)
        self.layout.addWidget(self.mainContainer)

        self.sideBar = SideBar(self.handler)
        self.containerLayout.addWidget(self.sideBar)

        self.mainWidget = Widget(layout='vertical', color = '@BGColor2')
        self.mainLayout = self.mainWidget.layout
        self.containerLayout.addWidget(self.mainWidget)

        self.setupMenuBar()

    def setupMenuBar(self):
        layout = self.menuBar.layout

        # MENU BUTTON 1
        mb1 = MenuButton("File")
        layout.insertWidget(0, mb1)

        mb1.addAction("test")
        mb1.addAction("test2", lambda:print("test"), "Ctrl+n")

    def closeEvent(self, event):
        self.handler.quitEvent()
