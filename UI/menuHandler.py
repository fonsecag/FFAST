from events import EventClass
from PySide6.QtWidgets import QFileDialog
from UI.Templates import customFileDialog
import os


class MenuHandler(EventClass):
    def __init__(self, window):
        self.handler = window.handler
        self.window = window
        self.connectActions()

    def connectActions(self):
        handler, window = (self.handler, self.window)
        mb = window.menuBar()

        # FILE
        File = mb.addMenu("&File")
        File.addAction("Save", self.onSave, "Ctrl+s")
        File.addAction("Load", self.onLoad, "Ctrl+l")

        File.addAction("Load Dataset", self.onDatasetLoad, "Ctrl+d")
        File.addAction("Load Model", self.onModelLoad, "Ctrl+e")

        File.addAction("Load Zero Model", self.loadZeroModel)
        # File.addAction("Load Prediction", self.loadPrepredictedModel)

        # File.addAction("Preferences", self.onPreferences)
        # File.addAction("Exit", self.onExit)

        # LOUPE
        Loupe = mb.addMenu("&Loupe")
        Loupe.addAction("New", self.newLoupe, "Ctrl+n")

    def onSave(self):
        (path, _) = QFileDialog.getSaveFileName(self.handler.window)
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
        env = self.handler.env
        fileTypes = list(env.datasetTypes.keys())
        extensions = [
            env.datasetTypes[x].datasetFileExtension for x in fileTypes
        ]
        path, typ = customFileDialog(
            self.handler.window, fileTypes=fileTypes, extensions=extensions
        )

        env.taskLoadDataset(path, typ)

    def onModelLoad(self):
        env = self.handler.env
        fileTypes = list(env.modelTypes.keys())
        extensions = [env.modelTypes[x].modelFileExtension for x in fileTypes]
        path, typ = customFileDialog(
            self.handler.window, fileTypes=fileTypes, extensions=extensions
        )

        env.taskLoadModel(path, typ)

    def newLoupe(self):
        self.handler.newLoupe()

    def loadZeroModel(self):
        env = self.handler.env
        env.loadZeroModel()
