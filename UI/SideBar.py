from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QEvent
from UI.Templates import Widget, ContentBar, ObjectListItem, ObjectList, CollapseButton
from config.uiConfig import configStyleSheet
from Utils.misc import rgbToHex

class InfoWidget(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

        self.setInfo(*[
            ("heloo", "i am testing stuff"),
            ('name', "buabras oadisja sd"),
            ("element the third", "third element"),
            ('name', "buabras oadisja sd"),
            ('name', "buabras oadisja sd"),
            ("element the third", "third element")
        ])


        self.setStyleSheet(configStyleSheet("""
            QLabel#LeftLabel{
                font-weight: bold;
            }
            QLabel{
                qproperty-alignment: AlignLeft;
            }
        """))

    nRows = 0
    def setInfo(self, *args):
        # ADD LABELS
        nRows = len(args)
        for i in range(self.nRows, nRows):
            labelLeft = QtWidgets.QLabel("")
            labelLeft.setObjectName("LeftLabel")
            self.layout.addWidget(labelLeft, i, 0)

            labelRight = QtWidgets.QLabel("")
            labelRight.setObjectName("RightLabel")
            self.layout.addWidget(labelRight, i, 1)

        # REMOVE LABELS
        for i in range(nRows, self.nRows):
            labelLeft = self.layout.itemAtPosition(i, 0)
            self.layout.removeWidget(labelLeft.widget())

            labelRight = self.layout.itemAtPosition(i, 1)
            self.layout.removeWidget(labelRight.widget())


        for i in range(nRows):
            sLeft, sRight = args[i]

            labelLeft = self.layout.itemAtPosition(i, 0).widget()
            labelRight = self.layout.itemAtPosition(i, 1).widget()

            labelLeft.setText(sLeft)
            labelRight.setText(sRight)

        self.nRows = nRows

class DatasetModelItem(ObjectListItem):

    buttonStyleSheet = '''
        background-color: @COLOR;
        border-radius: 20;
    '''
    color = (150, 150, 150)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, layout = 'vertical', **kwargs)
        
        self.setStyleSheet(configStyleSheet('''
            QPushButton#collapseButton{
                background-color: transparent;
            }
        '''))

        ## TOP PART
        self.layout.setContentsMargins(8,8,8,8)
        self.topLayout = QtWidgets.QHBoxLayout()
        self.topLayout.setSpacing(8)
        self.layout.addLayout(self.topLayout)
        self.topRightLayout = QtWidgets.QVBoxLayout()

        # COLOR BUTTON
        self.colorButton = QtWidgets.QPushButton("", parent = self)
        b = self.colorButton
        b.setFixedHeight(40)
        b.setFixedWidth(40)
        self.topLayout.addWidget(b)

        b.clicked.connect(self.chooseColor)

        # TEXT INFO
        self.topLayout.addLayout(self.topRightLayout)
        self.titleLabel = QtWidgets.QLabel("?", parent = self)
        self.infoButton = CollapseButton(parent = self)
        self.topRightLayout.addWidget(self.titleLabel)
        self.topRightLayout.addWidget(self.infoButton)

        ## INFO WIDGET
        self.infoWidget = InfoWidget(parent = self)
        self.layout.addWidget(self.infoWidget)
        self.infoButton.setCollapsingWidget(self.infoWidget)

        self.applyStyle()

    def applyStyle(self):
        # button color
        ss = self.buttonStyleSheet.replace("@COLOR", rgbToHex(*self.color))
        self.colorButton.setStyleSheet(configStyleSheet(ss))

    def chooseColor(self):
        initialColor = QtGui.QColor.fromRgb(*self.color)
        newColor = QtWidgets.QColorDialog.getColor(initialColor)
        self.color = newColor.getRgb()[:3]
        self.applyStyle()

class DatasetObjectList(ObjectList):
    def __init__(self, handler, **kwargs):
        super().__init__(handler, DatasetModelItem, **kwargs)
        self.layout.setSpacing(2)
        self.newObject("test")
        self.newObject("test2")
        self.newObject("test3")

class SideBar(ContentBar):
    def __init__(self, handler, **kwargs):
        super().__init__(handler, **kwargs)
        self.handler = handler
        self.setupContent()

    def setupContent(self):
        # dataset
        self.datasetsList = DatasetObjectList(self.handler, parent = self)
        self.addContent("DATASETS", widget = self.datasetsList)
        self.addContent("MODELS")


