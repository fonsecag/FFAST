from events import EventClass
import os
from PySide6 import QtWidgets
from PySide6.QtCore import QDir
import pyqtgraph
from UI.MainWindow import MainWindow
import os
from UI.Loupe import Loupe


class UIHandler(EventClass):
    """
    Main object responsible for handling UI elements.
    """

    uiFilesPath = os.path.join("UI", "uiFiles")
    env = None
    tabs = []
    loupes = []
    loupeModules = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.eventSubscribe("QUIT_READY", self.setQuitReady)

    def quitEvent(self):
        self.eventPush("QUIT_EVENT")
        # self.app.quit()
        self.setQuitReady()

    def quit(self):
        self.app.quit()

    quitReady = False

    def setQuitReady(self):
        self.quitReady = True

    def nLoupes(self):
        return len(self.loupes)

    def newLoupe(self):
        loupe = Loupe(self, len(self.loupes))

        for func in self.loupeModules:
            func(self, loupe)

        loupe.forceUpdate()
        self.loupes.append(loupe)
        loupe.show()
        loupe.setFocus()

        self.eventPush("LOUPES_UPDATE")

    def registerLoupeModule(self, func):
        self.loupeModules.append(func)

    def setEnvironment(self, env):
        self.env = env

    def launch(self):
        from config.uiConfig import config, configStyleSheet

        self.config = config

        # qasync creates its own QApplication instance, and as such you don't
        # need to create a new one, just access the created instance.
        # Also, we don't need app.exec() at the end, that's also handled
        app = QtWidgets.QApplication.instance()  # (sys.argv)
        app.setApplicationDisplayName("FFAST")
        app.setQuitOnLastWindowClosed(False)

        # Load icons
        QDir.addSearchPath("icon", "theme")

        # pyqtgraph configs
        self.initialisePlotConfigs()

        # TODO
        if True:
            app.setStyle("Fusion")
            # Load styles
            with open("style.qss", "r") as file:
                styleSheet = file.read()

            # set variables
            styleSheet = configStyleSheet(styleSheet)
            app.setStyleSheet(styleSheet)

        window = MainWindow(self)
        window.show()

        self.window = window
        self.app = app
        self.mainWindow = window

    def initialisePlotConfigs(self):
        pyqtgraph.setConfigOptions(
            antialias=True,
            leftButtonPan=False,
            crashWarning=True,
            foreground=self.config["envs"].get("TextColor1"),
            # background=self.config["envs"].get("BGColor2"),
            background=None,
            useOpenGL=True,
            enableExperimental=True,
            exitCleanup=True,
        )

    def addContentTab(self, widget, name):
        self.mainWindow.mainContent.addTab(widget, name)
