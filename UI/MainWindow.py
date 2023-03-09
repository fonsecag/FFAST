from PySide6 import QtCore, QtGui, QtWidgets
from UI.Templates import MenuButton, ToolButton
from config.uiConfig import configStyleSheet

class Color(QtWidgets.QWidget):

    def __init__(self, color):
        super(Color, self).__init__()
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(color))
        self.setPalette(palette)

class MenuBar(QtWidgets.QWidget):
    def __init__(self, handler):
        super().__init__()

        self.handler = handler
        self.setObjectName("menuBar")

        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)        
        self.layout.setContentsMargins(0,0,0,0)

        self.setMaximumHeight(30)

        # MENU BUTTON 1
        mb1 = MenuButton("File")
        self.layout.addWidget(mb1)

        mb1.addAction("test")
        mb1.addAction("test2", self.testMethod, "Ctrl+n")

        self.layout.addStretch()

        closeButton = ToolButton(self.handler, self.handler.quitEvent, icon = 'close')
        self.layout.addWidget(closeButton)

        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        styleSheet = '''
            QWidget#menuBar{
               background-color:@BGColor1;
            }
        '''
        self.setStyleSheet(configStyleSheet(styleSheet))

    def testMethod(self):
        print("TEST MEYHOD WWASd")

    def sizeHint(self):
        return QtCore.QSize(super().sizeHint().width(),self.maximumHeight())
    
    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QtCore.QPoint(event.globalPos() - self.oldPos)
        window = self.handler.window
        window.move(window.x() + delta.x(), window.y() + delta.y())
        self.oldPos = event.globalPos()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, handler):
        super().__init__()
        self.handler = handler
        self.setWindowTitle("FFAST")
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        
        # icon = QtGui.QIcon("tempIcon.png")
        # self.setWindowIcon(icon)
        self.setFocus()
        self.setGeometry(200, 200, 800, 600)
        self.window = QtWidgets.QWidget()

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0,0,0,0)
        self.window.setLayout(self.layout)

        self.setCentralWidget(self.window)

        self.menuBar = MenuBar(handler)
        self.layout.addWidget(self.menuBar)
        self.layout.addWidget(QtWidgets.QDial())
        self.layout.addWidget(Color("blue"))

    def closeEvent(self, event):
        self.handler.quitEvent()
