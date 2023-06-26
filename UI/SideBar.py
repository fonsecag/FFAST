from PySide6 import QtCore, QtGui, QtWidgets
from UI.Templates import (
    ContentBar,
    ObjectListItem,
    ObjectList,
    CollapseButton,
    InfoWidget,
    ToolButton,
    LineEdit,
    ProgressBar,
    customFileDialog,
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
        self.eventSubscribe("OBJECT_NAME_CHANGED", self.applyInfo)
        self.eventSubscribe(
            "DATASET_STATE_CHANGED", self.onDatasetStateChanged
        )

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
        self.renameButton.setToolTip("Rename")
        self.renameButton.setFixedSize(25, 25)

        # SET LINE EDIT PARAMETERS
        regExp = QtCore.QRegularExpression("^[^.\\\/]*$")
        validator = QtGui.QRegularExpressionValidator(regExp)
        self.titleLabel.setValidator(validator)
        self.titleLabel.editingFinished.connect(self.onNameEdited)

        layout.addWidget(self.renameButton)

        if (self.getObject().isSubDataset) and not (self.getObject().frozen):
            self.freezeButton = ToolButton(self.freezeObject, icon="freeze")
            self.freezeButton.setFixedSize(25, 25)
            self.freezeButton.setToolTip(
                "Freeze current indices to keep subdataset as is"
            )
            layout.addWidget(self.freezeButton)
        else:
            self.deleteButton = ToolButton(self.deleteObject, icon="delete")
            self.deleteButton.setFixedSize(25, 25)
            self.deleteButton.setToolTip("Remove")
            layout.addWidget(self.deleteButton)

        # save button
        if self.getObject().loadeeType == "dataset":
            self.saveButton = ToolButton(self.saveDataset)
            self.saveButton.setFixedSize(25, 25)
            self.saveButton.setToolTip("Save dataset")
            layout.addWidget(self.saveButton)

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
                # if subdataset, could care about name changes of parents
                dataset = self.handler.env.getDataset(self.id)
                if dataset is None:
                    return
                obj = self.handler.env.getObject(key)
                if not dataset.isDependentOn(obj):
                    return

        dataset = self.handler.env.getDataset(self.id)
        if dataset is not None:
            self.setName(dataset.getDisplayName())
            self.setInfoLabel(dataset.datasetName)

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

    def freezeObject(self):
        self.handler.env.freezeSubDataset(self.id)

    def renameObject(self):
        self.titleLabel.setText(
            self.getObject().getName()
        )  # remove display name things
        self.titleLabel.setDisabled(False)
        self.titleLabel.setFocus()

    def saveDataset(self):
        env = self.handler.env
        dataset = self.getObject()

        # get the path from the user and the type of dataset
        datasetTypes = [env.datasetTypes[x] for x in env.datasetTypes.keys()]
        formats = {}
        for dType in datasetTypes:
            if not hasattr(dType, "saveDataset"):
                continue
            for form in dType.saveFormats:
                if form is None:
                    name = dType.datasetName
                else:
                    name = f"{dType.datasetName} [{form}]"
                formats[name] = (dType.datasetName, form)

        path, formatName = customFileDialog(
            self.handler.window, fileTypes=list(formats.keys()), save=True
        )
        if path is None:
            return
        typ, form = formats[formatName]
        env.taskSaveDataset(dataset, typ, form, path)

    def onNameEdited(self):
        self.titleLabel.setDisabled(True)
        self.getObject().setName(
            self.titleLabel.text()
        )  # also calls the event
        self.applyInfo()

    def onDatasetStateChanged(self, fingerprint):
        if fingerprint != self.id:
            return

        dataset = self.getObject()
        if dataset.active:
            self.show()
        else:
            self.hide()

        self.forceUpdateParent()


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


class TaskItem(ObjectListItem, EventChildClass):
    def __init__(self, *args, **kwargs):
        # self.handler is set automatically
        super().__init__(*args, layout="vertical", **kwargs)
        EventChildClass.__init__(self)

        taskID = self.id
        self.task = self.handler.env.getTask(taskID)

        self.eventSubscribe("TASK_PROGRESS", self.setProgress)

        self.layout.setContentsMargins(16, 8, 16, 8)
        self.layout.setSpacing(8)

        self.topLayout = QtWidgets.QHBoxLayout()
        self.topLayout.setSpacing(4)
        self.layout.addLayout(self.topLayout)

        self.bottomLayout = QtWidgets.QHBoxLayout()
        self.bottomLayout.setSpacing(4)
        self.layout.addLayout(self.bottomLayout)

        ## TOP
        self.titleLabel = QtWidgets.QLabel(self.task["name"])
        self.titleLabel.setObjectName("titleLabel")
        self.topLayout.addWidget(self.titleLabel)

        self.topLayout.addStretch()

        ## TOP TOOLBAR
        self.cancelButton = ToolButton(self.cancel, icon="delete")
        self.cancelButton.setFixedSize(25, 25)
        self.setToolTip("Cancel task")
        self.topLayout.addWidget(self.cancelButton)

        ## BOTTOM
        self.messageLabel = QtWidgets.QLabel("Working...")
        self.bottomLayout.addWidget(self.messageLabel)

        self.bottomLayout.addStretch()

        self.progressLabel = QtWidgets.QLabel("/")
        self.bottomLayout.addWidget(self.progressLabel)

        ## BAR
        self.progressBar = ProgressBar()
        self.progressBar.setFixedHeight(10)
        self.layout.addWidget(self.progressBar)

    def setProgress(
        self,
        taskID,
        progMax=None,
        prog=None,
        percent=False,
        message="Working...",
    ):
        if taskID is not self.id:
            return

        hasProg = (prog is not None) and (progMax is not None)

        # prog text
        progText = ""
        if hasProg:
            if percent:
                progText = f"{prog / progMax * 100:.0f}%"
            else:
                progText = f"{prog}/{progMax}"
        self.progressLabel.setText(progText)

        # prog bar
        if hasProg:
            self.progressBar.setValue(prog)
            self.progressBar.setMaximum(progMax)
        else:
            pass

        # message
        self.messageLabel.setText(message)
        self.messageLabel.setToolTip(message)

    def cancel(self):
        taskID = self.id
        self.eventPush("TASK_CANCEL", taskID)


class TasksList(ObjectList, EventChildClass):
    def __init__(self, handler, **kwargs):
        self.handler = handler
        super().__init__(handler, TaskItem, **kwargs)
        EventChildClass.__init__(self)

        self.eventSubscribe("TASK_CREATED", self.onTaskCreated)
        self.eventSubscribe("TASK_DONE", self.onTaskDone)

    def onTaskCreated(self, taskID):
        task = self.handler.env.getTask(taskID)
        if (task is None) or (not task["visual"]):
            return

        self.newObject(taskID)

    def onTaskDone(self, taskID):
        self.removeObject(taskID)


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

        self.tasksList = TasksList(self.handler, parent=self)
        self.addContent("TASKS", widget=self.tasksList)
        self.setExpanded("TASKS")
