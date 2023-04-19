from PySide6 import QtCore, QtGui, QtWidgets
from UI.Templates import (
    ContentBar,
    ObjectListItem,
    ObjectList,
    CollapseButton,
    InfoWidget,
    ToolButton,
    LineEdit,
)
from config.uiConfig import configStyleSheet
from utils import rgbToHex
from events import EventChildClass


class DatasetModelItem(ObjectListItem, EventChildClass):
    buttonStyleSheet = """
        background-color: @COLOR;
        border-radius: 20;
    """

    def __init__(self, *args, **kwargs):
        # self.handler is set automatically
        super().__init__(*args, layout="vertical", **kwargs)
        EventChildClass.__init__(self)

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

        self.eventSubscribe("DATASET_UPDATED", self.applyInfo)

        ## TOP PART
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.topLayout = QtWidgets.QHBoxLayout()
        self.topLayout.setSpacing(4)
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
        self.labelLayout = QtWidgets.QHBoxLayout()
        self.labelLayout.setContentsMargins(0, 5, 0, 0)
        self.labelLayout.setSpacing(4)
        self.titleLabel = LineEdit("?", parent=self)
        self.titleLabel.setDisabled(True)
        # self.titleLabel = QtWidgets.QLabel("?", parent=self)

        self.titleLabel.setObjectName("titleLabel")
        self.infoButton = CollapseButton(parent=self)
        self.topRightLayout.addLayout(self.labelLayout)
        self.labelLayout.addWidget(self.titleLabel)
        self.topRightLayout.addWidget(self.infoButton)
        self.applyToolbar()

        ## INFO WIDGET
        self.infoWidget = InfoWidget(parent=self)
        self.layout.addWidget(self.infoWidget)
        self.infoButton.setCollapsingWidget(self.infoWidget)
        self.infoButton.setCollapsed()

        self.applyStyle()
        self.applyInfo()

    def applyToolbar(self):
        layout = self.labelLayout

        self.renameButton = ToolButton(self.renameObject, icon="rename")
        self.renameButton.setFixedSize(25, 25)

        # SET LINE EDIT PARAMETERS
        regExp = QtCore.QRegularExpression("^[^.\\\/]*$")
        validator = QtGui.QRegularExpressionValidator(regExp)
        self.titleLabel.setValidator(validator)
        self.titleLabel.editingFinished.connect(self.onNameEdited)

        layout.addWidget(self.renameButton)

        if not self.getObject().isSubDataset:
            self.deleteButton = ToolButton(self.deleteObject, icon="delete")
            self.deleteButton.setFixedSize(25, 25)
            layout.addWidget(self.deleteButton)

    def applyStyle(self):
        obj = self.getObject()
        # button color
        if obj is not None:
            ss = self.buttonStyleSheet.replace("@COLOR", rgbToHex(*obj.color))
            self.colorButton.setStyleSheet(configStyleSheet(ss))

    def getColor(self):
        obj = self.getObject()
        if obj is not None:
            return obj.color
        return None

    def chooseColor(self):
        obj = self.getObject()
        if obj is None:
            return

        initialColor = QtGui.QColor.fromRgb(*obj.color)
        newColor = QtWidgets.QColorDialog.getColor(initialColor)
        obj.setColor(*newColor.getRgb()[:3])
        self.applyStyle()

    def setName(self, name):
        self.titleLabel.setText(name)

    def setInfoLabel(self, label):
        self.infoButton.setText(label)

    def getObject(self):
        dataset = self.handler.env.getDataset(self.id)
        if dataset is None:
            return self.handler.env.getModel(self.id)
        else:
            return dataset

    def applyInfo(self, key=None):
        if key is not None:
            if key != self.id:
                return

        dataset = self.handler.env.getDataset(self.id)
        if dataset is not None:
            self.setName(dataset.getDisplayName())
            self.setInfoLabel(dataset.datasetType)

            info = dataset.getBaseInfo() + dataset.getInfo()
            self.infoWidget.setInfo(*info)

        else:
            model = self.handler.env.getModel(self.id)
            if model is None:
                return
            self.setName(model.getDisplayName())
            self.setInfoLabel(model.modelName)

            info = model.getInfo()
            self.infoWidget.setInfo(*info)

    def deleteObject(self):
        self.handler.env.deleteObject(self.id)

    def renameObject(self):
        self.titleLabel.setText(
            self.getObject().getName()
        )  # remove display name things
        self.titleLabel.setDisabled(False)
        self.titleLabel.setFocus()

    def onNameEdited(self):
        self.titleLabel.setDisabled(True)
        self.getObject().setName(
            self.titleLabel.text()
        )  # also calls the event
        self.applyInfo()


class DatasetObjectList(ObjectList, EventChildClass):
    def __init__(self, handler, **kwargs):
        self.handler = handler
        super().__init__(handler, DatasetModelItem, **kwargs)
        EventChildClass.__init__(self)
        self.eventSubscribe("DATASET_LOADED", self.onDatasetLoaded)
        self.eventSubscribe("DATASET_DELETED", self.onDatasetDeleted)

    def onDatasetLoaded(self, id):
        if self.getWidget(id) is not None:
            return

        self.newObject(id)

    def onDatasetDeleted(self, id):
        self.removeObject(id)


class ModelsObjectList(ObjectList, EventChildClass):
    def __init__(self, handler, **kwargs):
        self.handler = handler
        super().__init__(handler, DatasetModelItem, **kwargs)
        EventChildClass.__init__(self)
        self.eventSubscribe("MODEL_LOADED", self.onModelLoaded)
        self.eventSubscribe("MODEL_DELETED", self.onModelDeleted)

    def onModelLoaded(self, id):
        if self.getWidget(id) is not None:
            return
        self.newObject(id)

    def onModelDeleted(self, id):
        self.removeObject(id)


class SideBar(ContentBar):
    def __init__(self, handler, **kwargs):
        super().__init__(handler, **kwargs)
        self.handler = handler
        self.setupContent()

    def setupContent(self):

        self.modelsList = ModelsObjectList(self.handler, parent=self)
        self.addContent("MODELS", widget=self.modelsList)
        self.setExpanded("MODELS")

        self.datasetsList = DatasetObjectList(self.handler, parent=self)
        self.addContent("DATASETS", widget=self.datasetsList)
        self.setExpanded("DATASETS")
