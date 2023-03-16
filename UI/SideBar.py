from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QEvent
from UI.Templates import Widget, CollapsibleWidget
from config.uiConfig import configStyleSheet

class SideBar(Widget):
    def __init__(self, handler):
        super().__init__()
        self.handler = handler

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0,0,0,0)
        self.setLayout(self.layout)

        self.setObjectName("sideBar")

        self.setFixedWidth(300)

        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        styleSheet = '''
            QWidget#sideBar{
               background-color:@BGColor1;
            }
        '''
        self.setStyleSheet(configStyleSheet(styleSheet))
        self.setupContent()

    def setupContent(self):
        # dataset
        self.datasetsWidget = CollapsibleWidget(self.handler, name = 'DATASETS')
        self.layout.addWidget(self.datasetsWidget)

        self.modelsWidget = CollapsibleWidget(self.handler, name = 'MODELS')
        self.layout.addWidget(self.modelsWidget)

        self.layout.addStretch()
