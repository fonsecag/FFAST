from events import EventClass
import os
from PySide6 import QtWidgets
from PySide6.QtCore import QDir
import pyqtgraph 
from UI.MainWindow import MainWindow

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
        self.app.quit()

    quitReady = False

    def setQuitReady(self):
        self.quitReady = True

    def nLoupes(self):
        return len(self.loupes)

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
        
        #TODO
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

        self.initialisePlotConfigs()

    def initialisePlotConfigs(self):

        pyqtgraph.setConfigOptions(
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

