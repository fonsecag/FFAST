from PySide6 import QtCore, QtGui, QtWidgets
from UI.Templates import (
    ContentBar,
    ObjectListItem,
    ObjectList,
    CollapseButton,
    InfoWidget,
)
from config.uiConfig import configStyleSheet
from Utils.misc import rgbToHex
from events import EventChildClass


class DatasetModelItem(ObjectListItem):
    buttonStyleSheet = """
        background-color: @COLOR;
        border-radius: 20;
    """
    color = (150, 150, 150)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, layout="vertical", **kwargs)

        self.setStyleSheet(
            configStyleSheet(
                """
            QPushButton#collapseButton{
                background-color: transparent;
                font-weight: normal;
                font-style: italic;
            }
            QLabel#titleLabel{
                font-weight: bold;
            }
        """
            )
        )

        ## TOP PART
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.topLayout = QtWidgets.QHBoxLayout()
        self.topLayout.setSpacing(8)
        self.layout.addLayout(self.topLayout)
        self.topRightLayout = QtWidgets.QVBoxLayout()

        # COLOR BUTTON
        self.colorButton = QtWidgets.QPushButton("", parent=self)
        b = self.colorButton
        b.setFixedHeight(40)
        b.setFixedWidth(40)
        self.topLayout.addWidget(b)

        b.clicked.connect(self.chooseColor)

        # TEXT INFO
        self.topLayout.addLayout(self.topRightLayout)
        self.titleLabel = QtWidgets.QLabel("?", parent=self)
        self.titleLabel.setObjectName("titleLabel")
        self.infoButton = CollapseButton(parent=self)
        self.topRightLayout.addWidget(self.titleLabel)
        self.topRightLayout.addWidget(self.infoButton)

        ## INFO WIDGET
        self.infoWidget = InfoWidget(parent=self)
        self.layout.addWidget(self.infoWidget)
        self.infoButton.setCollapsingWidget(self.infoWidget)
        self.infoButton.setCollapsed()

        self.applyStyle()
        self.applyInfo()

    def applyStyle(self):
        # button color
        ss = self.buttonStyleSheet.replace("@COLOR", rgbToHex(*self.color))
        self.colorButton.setStyleSheet(configStyleSheet(ss))

    def chooseColor(self):
        initialColor = QtGui.QColor.fromRgb(*self.color)
        newColor = QtWidgets.QColorDialog.getColor(initialColor)
        self.color = newColor.getRgb()[:3]
        self.applyStyle()

    def setName(self, name):
        self.titleLabel.setText(name)

    def setInfoLabel(self, label):
        self.infoButton.setText(label)

    def applyInfo(self):
        dataset = self.handler.env.getDataset(self.id)

        self.setName(dataset.getDisplayName())
        self.setInfoLabel(dataset.datasetType)

        info = dataset.getBaseInfo() + dataset.getInfo()
        self.infoWidget.setInfo(*info)


class DatasetObjectList(ObjectList, EventChildClass):
    def __init__(self, handler, **kwargs):
        self.handler = handler
        super().__init__(handler, DatasetModelItem, **kwargs)
        EventChildClass.__init__(self)
        self.eventSubscribe("DATASET_LOADED", self.onDatasetLoaded)

    def onDatasetLoaded(self, id):
        if self.getWidget(id) is not None:
            return

        self.newObject(id)


class SideBar(ContentBar):
    def __init__(self, handler, **kwargs):
        super().__init__(handler, **kwargs)
        self.handler = handler
        self.setupContent()

    def setupContent(self):
        # dataset
        self.datasetsList = DatasetObjectList(self.handler, parent=self)
        self.addContent("DATASETS", widget=self.datasetsList)
        self.addContent("MODELS")
