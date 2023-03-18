from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QEvent
from UI.Templates import Widget
from config.uiConfig import configStyleSheet
from UI.SideBar import SideBar

# from qframelesswindow import FramelessWindow

class Color(QtWidgets.QWidget):

    def __init__(self, color):
        super(Color, self).__init__()
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(color))
        self.setPalette(palette)

        self.setMouseTracking(True)

class MainWindow(QtWidgets.QMainWindow):
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

        self.mainContainer = Widget(layout='horizontal', parent = None)
        # self.layout.addWidget(self.mainContainer)
        self.setCentralWidget(self.mainContainer)
        self.containerLayout = self.mainContainer.layout
        # self.containerLayout.setContentsMargins(0,0,0,0)
        # self.containerLayout.setSpacing(0)

        self.sideBar = SideBar(self.handler, parent = self)
        self.containerLayout.addWidget(self.sideBar)

        self.mainWidget = Widget(layout='vertical', color = '@BGColor2', parent = self)
        self.mainLayout = self.mainWidget.layout
        self.containerLayout.addWidget(self.mainWidget)

        # self.setupMenuBar()

    def setTitleBar(self, titleBar):
        """ set custom title bar
        Parameters
        ----------
        titleBar: TitleBar
            title bar
        """
        self.titleBar.deleteLater()
        self.titleBar = titleBar
        self.titleBar.setParent(self)
        self.titleBar.raise_()

    def setupMenuBar(self):
        mb = self.menuBar()
        file =  mb.addMenu("&File")
        file.addAction("hello", self.exit)

    def exit(self):
        self.close()

    def closeEvent(self, event):
        self.handler.quitEvent()
