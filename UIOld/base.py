from events import EventClass, EventChildClass
from PySide6 import QtCore, QtGui, QtWidgets
import logging
import numpy as np
import os
import sys
import asyncio
import time
from Utils.uiLoader import loadUi
from UI.sidebar import Sidebar
import pyqtgraph as pg
from UI.loupe.loupe import Loupe
from UI.menuHandler import MenuHandler
from PySide6.QtCore import QDir


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, handler):
        super().__init__()
        self.handler = handler
        loadUi(os.path.join(self.handler.uiFilesPath, "base.ui"), self)
        self.setWindowTitle("FFAST")
        # icon = QtGui.QIcon("tempIcon.png")
        # self.setWindowIcon(icon)
        self.setFocus()

    def closeEvent(self, event):
        self.handler.quitEvent()


class UIHandler(EventClass):
    """
    Main object responsible for handling UI elements.
    """

    uiFilesPath = os.path.join("UI", "uiFiles")
    env = None
    tabs = []
    loupes = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eventSubscribe("QUIT_READY", self.setQuitReady)

    def quitEvent(self):
        self.eventPush("QUIT_EVENT")

    quitReady = False

    def setQuitReady(self):
        self.quitReady = True

    def nLoupes(self):
        return len(self.loupes)

    def loadUiElements(self):
        self.sidebar = Sidebar(self)
        self.window.horizontalLayout.replaceWidget(
            self.window.leftWidget, self.sidebar
        )

        self.menuHandler = MenuHandler(self)

    def newLoupe(self):
        loupe = Loupe(self, len(self.loupes))

        for func in self.loupeAddonFunctions:
            func(self, loupe)

        self.loupes.append(loupe)
        loupe.show()
        loupe.setFocus()

        self.eventPush("LOUPES_UPDATE")

    def addPlotToTab(self, plw):
        tab = self.tabs[0]
        layout = tab.mainLayout

        layout.insertWidget(layout.count() - 1, plw)

    def setEnvironment(self, env):
        self.env = env

    def applyConfigToStyleSheet(self, sheet):
        for (key, value) in self.config["envs"].items():
            sheet = sheet.replace(f"@{key}", value)

        return sheet

    def launch(self):

        from config.uiConfig import config

        self.config = config

        # qasync creates its own QApplication instance, and as such you don't
        # need to create a new one, just access the created instance.
        # Also, we don't need app.exec() at the end, that's also handled
        app = QtWidgets.QApplication.instance()  # (sys.argv)
        app.setStyle("Fusion")
        app.setApplicationDisplayName("FFAST")
        app.setQuitOnLastWindowClosed(False)

        # Load icons
        QDir.addSearchPath("icon", "theme")

        window = MainWindow(self)
        window.show()
        window.resize(1800, 1200)

        # Load styles
        with open("style.qss", "r") as file:
            styleSheet = file.read()

        # set variables
        styleSheet = self.applyConfigToStyleSheet(styleSheet)

        app.setStyleSheet(styleSheet)

        self.window = window
        self.app = app
        self.mainWindow = window

        self.setTabsConfig()
        self.initialisePlotConfigs()

    def setTabsConfig(self):
        sheet = """
            QWidget#centralWidget{
                background-color:@BGColor2;
            }

            QTabBar::tab{
                background-color:@BGColor2;
            }
        """

        self.window.setStyleSheet(self.applyConfigToStyleSheet(sheet))

    def initialisePlotConfigs(self):

        pg.setConfigOptions(
            antialias=True,
            leftButtonPan=False,
            crashWarning=True,
            foreground=self.config["envs"].get("TextColor1"),
            useOpenGL=True,
            enableExperimental=True,
            exitCleanup=True,
        )

    def addTab(self, widget, name):
        self.tabs.append(widget)
        self.window.centerTabs.addTab(widget, name)

    loupeAddonFunctions = []

    def addLoupeAddon(self, func):
        self.loupeAddonFunctions.append(func)

    def loadPrepredictPopup(self):

        dlg = LoadPrepredictFileDialog(self)
        dlg.run()


class LoadPrepredictFileDialog(EventChildClass, QtWidgets.QFileDialog):
    def __init__(self, handler):
        self.handler = handler
        super().__init__()
        self.handler.addEventChild(self)

        self.eventSubscribe("CUSTOM_FILE_DIALOG_UPDATE", self.onDialogUpdate)

        env = handler.env

        self.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        self.setOption(QtWidgets.QFileDialog.HideNameFilterDetails, True)
        layout = self.layout()
        self.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        # self.setNameFilters([".npz"])

        cbLabel = QtWidgets.QLabel()
        cbLabel.setText("Dataset")
        layout.addWidget(cbLabel, 5, 0)

        cb = QtWidgets.QComboBox()
        layout.addWidget(cb, 5, 1)

        datasets = env.getAllDatasets(excludeSubs=True)
        self.selections = []
        for dataset in datasets:
            cb.addItem(dataset.getDisplayName())
            self.selections.append(dataset.fingerprint)

        self.datasetComboBox = cb
        self.currentChanged.connect(self.onCurrentChanged)
        btnBox = self.findChild(QtWidgets.QDialogButtonBox)
        self.confirmButton = btnBox.button(QtWidgets.QDialogButtonBox.Open)

    def run(self):
        if self.exec_():
            idx = self.datasetComboBox.currentIndex()
            datasetKey = self.selections[idx]
            path = self.selectedFiles()[0]
            self.handler.env.loadPrepredictedDataset(path, datasetKey)

    def onCurrentChanged(self, *args):
        # we delay it by 1 update because it gets enabled automatically by qt
        # we want the open button to not be active unless dataset selected
        self.eventPush("CUSTOM_FILE_DIALOG_UPDATE")

    def onDialogUpdate(self):
        if not self.confirmButton.isEnabled():
            return

        self.confirmButton.setEnabled(self.getOpenableStatus())

    def getOpenableStatus(self):
        # not needed yet
        return True
