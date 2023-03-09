from PySide6 import QtCore, QtGui, QtWidgets
from config.uiConfig import config, configStyleSheet

class MenuButton(QtWidgets.QPushButton):

    def __init__(self, name):
        super().__init__(name, flat = True)

        self.menu = QtWidgets.QMenu()
        self.setMenu(self.menu)

        self.setStyleSheet("::menu-indicator{ image: none; }")

    def addAction(self, *args):
        self.menu.addAction(*args)


class ToolButton(QtWidgets.QToolButton):

    def __init__(self, handler, func, icon = 'default'):
        self.handler = handler
        super().__init__()
        self.clicked.connect(func)
        icon = config['icons'][icon]
        self.setIcon(QtGui.QIcon(f'icon:{icon}'))
