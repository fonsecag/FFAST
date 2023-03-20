from events import EventChildClass
import sys, os
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtUiTools import QUiLoader
from Utils.uiLoader import loadUi
from UI.utils import CollapseButton, getIcon
import logging

logger = logging.getLogger("FFAST")


class TaskWidget(QtWidgets.QWidget):
    def __init__(self, handler, taskID):
        super().__init__()
        loadUi(os.path.join(handler.uiFilesPath, "task.ui"), self)

        task = handler.env.getTask(taskID)

        self.taskNameLabel.setText(task["name"])
        self.task = task
        self.taskID = taskID
        self.setProgress()
        self.abortButton.clicked.connect(self.abort)
        self.handler = handler

    deleted = False

    def delete(self):
        self.deleteLater()
        self.deleted = True

    def abort(self):
        self.handler.eventPush("TASK_CANCEL", self.taskID)

    def setProgress(
        self, progMax=None, prog=None, percent=False, message="Working..."
    ):
        if self.deleted:
            return
        bar = self.progressBar
        self.messageLabel.setText(message)

        if (prog is None) or (progMax is None):
            bar.setValue(1)
            bar.setTextVisible(False)
            return
        else:
            bar.setTextVisible(True)

        if percent:
            bar.setFormat("%p%")
        else:
            bar.setFormat("%v/%m")

        bar.setMaximum(progMax)
        bar.setValue(prog)


class LoaderWidget(EventChildClass, QtWidgets.QWidget):
    def __init__(self, handler, loadee, *args, **kwargs):
        self.loadee = loadee
        self.handler = handler
        self.loadeeType = loadee.loadeeType
        super().__init__(*args, **kwargs)
        self.handler.addEventChild(self)
        loadUi(os.path.join(self.handler.uiFilesPath, "loaderWidget.ui"), self)

        # self.pathValueLabel.setText(loadee.path)

        regExp = QtCore.QRegularExpression("^[^.\\\/]*$")
        validator = QtGui.QRegularExpressionValidator(regExp)
        self.nameValueEdit.setValidator(validator)

        self.nameValueEdit.setText(loadee.getName())
        self.nameValueEdit.editingFinished.connect(self.onNameEdited)

        self.deleteButton.clicked.connect(self.onDelete)

        # ADD UI ELEMENTS
        cb = CollapseButton(
            handler, self.contentFrame, "down", defaultCollapsed=True
        )
        self.headerLayout.insertWidget(0, cb)

        self.applyConfig()

    def applyConfig(self):
        sheet = """
            QFrame#contentFrame{
                background-color: transparent;
            }

            QToolButton{
                border: None;
            }

            QFrame#footerFrame{
                border-bottom: 2px solid @BGColor1;
            }

        """

        self.setStyleSheet(self.handler.applyConfigToStyleSheet(sheet))
        self.deleteButton.setIcon(getIcon("close"))

    def checkState(self, key):
        if key != self.loadee.fingerprint:
            return

        if self.loadee.active:
            self.show()
            # self.setFixedHeight(79)
        else:
            self.hide()
            # self.setFixedHeight(0)

    def onColorChanged(self, btn):
        pass

    def onNameEdited(self):
        txt = self.nameValueEdit.text()
        self.loadee.setName(txt)

    def onDelete(self):
        env = self.handler.env

        if self.loadeeType == "dataset":
            env.deleteDataset(self.loadee.fingerprint)
        elif self.loadeeType == "model":
            env.deleteModel(self.loadee.fingerprint)


class DatasetLoaderWidget(LoaderWidget):
    def __init__(self, handler, loadee):
        super().__init__(handler, loadee)
        self.eventSubscribe("DATASET_STATE_CHANGED", self.checkState)

        if loadee.isSubDataset:
            self.eventSubscribe("SUBDATASET_INDICES_CHANGED", self.updateInfo)
            self.deleteButton.hide()

        # add stuff to content
        if not loadee.isSubDataset:
            self.contentLayout.addRow(
                QtWidgets.QLabel("Path"), QtWidgets.QLabel(loadee.path)
            )
        else:
            self.contentLayout.addRow(
                QtWidgets.QLabel("Type"), QtWidgets.QLabel("Subdataset")
            )
            self.contentLayout.addRow(
                QtWidgets.QLabel("Parent Plot"),
                QtWidgets.QLabel(loadee.subName),
            )

        self.amountLabel = QtWidgets.QLabel(str(loadee.getN()))
        self.contentLayout.addRow(QtWidgets.QLabel("Amount"), self.amountLabel)

    def updateInfo(self, key):
        if key != self.loadee.fingerprint:
            return
        self.amountLabel.setText(str(self.loadee.getN()))


class ModelLoaderWidget(LoaderWidget):
    def __init__(self, handler, loadee):
        super().__init__(handler, loadee)
        self.eventSubscribe("DATASET_STATE_CHANGED", self.checkState)

        # add stuff to content
        if not loadee.isGhost:
            self.contentLayout.addRow(
                QtWidgets.QLabel("Path"), QtWidgets.QLabel(loadee.path)
            )
        else:
            self.contentLayout.addRow(
                QtWidgets.QLabel("Type"), QtWidgets.QLabel("Ghost")
            )


class Sidebar(EventChildClass, QtWidgets.QWidget):
    def __init__(self, handler, *args, **kwargs):
        self.handler = handler
        super().__init__(*args, **kwargs)
        self.handler.addEventChild(self)
        loadUi(os.path.join(self.handler.uiFilesPath, "sidebar.ui"), self)

        self.eventSubscribe("DATASET_LOADED", self.onDatasetLoaded)
        self.eventSubscribe("MODEL_LOADED", self.onModelLoaded)
        self.eventSubscribe("DATASET_DELETED", self.onDatasetDeleted)
        self.eventSubscribe("MODEL_DELETED", self.onModelDeleted)

        # TASKS
        self.eventSubscribe("TASK_CREATED", self.onTaskCreated)
        self.eventSubscribe("TASK_DONE", self.onTaskDone)
        self.eventSubscribe("TASK_PROGRESS", self.onTaskProgress)

        styleSheet = """
            QFrame#contentFrame{
                background-color: @BGColor1;
                border: None;
                border-radius:0px;
            }

            QLabel#datasetLabel,
            QLabel#modelLabel,
            QLabel#tasksLabel{
                font-weight: bold;
                text-decoration: underline; 
            }
        """

        self.setStyleSheet(handler.applyConfigToStyleSheet(styleSheet))

    modelKeys = []
    datasetKeys = []

    def forceContextUpdate(self):
        self.eventPush("CONTEXT_UPDATED")
        self.eventPush("CONTEXT_UPDATED_FORCE")

    def chooseDataset(self):
        (fileName, _) = QtWidgets.QFileDialog.getOpenFileName(self)
        if fileName is None or fileName == "":
            return
        self.eventPush("DATASET_CHOSEN", fileName)

    def onDatasetLoaded(self, key, *args):
        existingWidget = self.getDatasetWidget(key)
        if existingWidget is not None:
            return
        dataset = self.handler.env.getDataset(key)
        loader = DatasetLoaderWidget(self.handler, dataset)
        n = self.datasetsLayout.count()
        self.datasetsLayout.insertWidget(n - 1, loader)

    def getDatasetWidget(self, key):
        layout = self.datasetsLayout
        widgets = (layout.itemAt(i) for i in range(layout.count()))
        for widget in widgets:
            if not isinstance(widget, QtWidgets.QWidgetItem):
                continue
            loaderWidget = widget.widget()
            dataset = loaderWidget.loadee
            if dataset.fingerprint == key:
                return loaderWidget

        return None

    def getModelWidget(self, key):
        layout = self.modelsLayout
        widgets = (layout.itemAt(i) for i in range(layout.count()))
        for widget in widgets:
            if not isinstance(widget, QtWidgets.QWidgetItem):
                continue
            loaderWidget = widget.widget()
            model = loaderWidget.loadee
            if model.fingerprint == key:
                return loaderWidget

        return None

    def onModelLoaded(self, key):
        existingWidget = self.getModelWidget(key)
        if existingWidget is not None:
            return
        model = self.handler.env.getModel(key)
        loader = ModelLoaderWidget(self.handler, model)
        n = self.modelsLayout.count()
        self.modelsLayout.insertWidget(n - 1, loader)

    def onDatasetDeleted(self, key):
        widget = self.getDatasetWidget(key)
        if widget is None:
            return

        self.datasetsLayout.removeWidget(widget)
        widget.deleteLater()

    def onModelDeleted(self, key):
        widget = self.getModelWidget(key)
        if widget is None:
            return

        self.modelsLayout.removeWidget(widget)
        widget.deleteLater()

    tasks = {}

    def onTaskCreated(self, taskID):
        task = self.handler.env.getTask(taskID)

        if not task["visual"]:
            return

        taskWidget = TaskWidget(self.handler, taskID)
        n = self.tasksLayout.count()
        self.tasksLayout.insertWidget(n - 1, taskWidget)
        self.tasks[taskID] = taskWidget

    def onTaskDone(self, taskID):
        if taskID not in self.tasks:
            return

        taskWidget = self.tasks[taskID]
        self.tasksLayout.removeWidget(taskWidget)
        taskWidget.delete()
        del taskWidget

    def onTaskProgress(self, taskId, **kwargs):
        if taskId not in self.tasks:
            return

        taskWidget = self.tasks[taskId]
        taskWidget.setProgress(**kwargs)

    # def onDatasetNameChanged(self, key):
    #     dataset = self.handler.env.getDataset(key)
    #     name = dataset.name
    #     self.getDatasetWidget(key)
