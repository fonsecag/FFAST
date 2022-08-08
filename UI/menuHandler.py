from events import EventClass
from PySide6.QtWidgets import QFileDialog
import os


class MenuHandler(EventClass):
    def __init__(self, handler):

        self.handler = handler
        self.window = handler.window
        self.connectActions()

    def connectActions(self):
        handler, window = self.handler, self.window

        window.actionSave.triggered.connect(self.onSave)
        window.actionLoad.triggered.connect(self.onLoad)
        window.actionCustomPreferences.triggered.connect(self.onPreferences)
        window.actionCustomExit.triggered.connect(self.onExit)
        window.actionDatasetLoad.triggered.connect(self.onDatasetLoad)
        window.actionModelLoad.triggered.connect(self.onModelLoad)
        window.actionNewLoupe.triggered.connect(self.newLoupe)
        window.actionNewLoupe.setShortcut("Ctrl+n")
        window.actionLoadPrepredictedModel.triggered.connect(self.loadPrepredictedModel)

    def onSave(self):
        path, _ = QFileDialog.getSaveFileName(self.handler.window)
        if path is None or path.strip() == "":
            return

        self.handler.env.newTask(
            self.handler.env.save,
            args=(path,),
            visual=True,
            name=f"Saving at {os.path.basename(path)}",
            threaded=True,
        )

    def onLoad(self):
        path = QFileDialog.getExistingDirectory(self.handler.window)
        if path is None or path.strip() == "":
            return

        self.handler.env.newTask(
            self.handler.env.load,
            args=(path,),
            visual=True,
            name=f"Loading {os.path.basename(path)}",
            threaded=True,
        )

    def onPreferences(self):
        pass

    def onExit(self):
        self.eventPush("QUIT_EVENT")

    def onDatasetLoad(self):
        path, _ = QFileDialog.getOpenFileName(self.handler.window)
        if path is None or path.strip() == "":
            return

        env = self.handler.env
        env.newTask(
            env.loadDataset,
            args=(path,),
            visual=True,
            name=f"Loading dataset {os.path.basename(path)}",
            threaded=True,
        )

    def onModelLoad(self):
        path, _ = QFileDialog.getOpenFileName(self.handler.window)
        if path is None or path.strip() == "":
            return

        env = self.handler.env
        env.newTask(
            env.loadModel,
            args=(path,),
            visual=True,
            name=f"Loading model {os.path.basename(path)}",
            threaded=True,
        )

    def newLoupe(self):
        self.handler.newLoupe()

    def loadPrepredictedModel(self):
        self.handler.loadPrepredictPopup()
