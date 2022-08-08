from events import EventWidgetClass
import sys, os, time
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtUiTools import QUiLoader
from Utils.uiLoader import loadUi
import numpy as np
import logging
from Utils.qt import makeStretchingTable, stretchTableToContent
from UI.utils import DatasetModelSelector

logger = logging.getLogger("FFAST")


class Tab(EventWidgetClass, QtWidgets.QWidget):
    def __init__(
        self,
        handler,
        *args,
        layoutType="grid",
        hasDatasetSelector=False,
        hasModelSelector=False,
        singleDataset=False,
        singleModel=False,
        **kwargs,
    ):

        self.handler = handler
        super().__init__(*args, **kwargs)
        loadUi(os.path.join(self.handler.uiFilesPath, "tab.ui"), self)

        self.layoutType = layoutType

        self.widgets = []

        if layoutType == "grid":
            self.setGridLayout()

        self.loadAllButton.clicked.connect(self.loadAllContent)

        n = 1
        if hasDatasetSelector:
            cb = DatasetModelSelector(
                self.handler,
                "dataset",
                text="Choose datasets",
                singleSelect=singleDataset,
            )
            self.datasetSelector = cb
            self.toolbarLayout.insertWidget(1, cb)
            n += 1

        if hasModelSelector:
            cb = DatasetModelSelector(
                self.handler,
                "model",
                text="Choose models",
                singleSelect=singleModel,
            )
            self.modelSelector = cb
            self.toolbarLayout.insertWidget(n, cb)

        self.applyConfig()

    def applyConfig(self):
        sheet = """
            QWidget#scrollAreaWidgetContents{
                background-color:@BGColor2;
            }

        """

        self.setStyleSheet(self.handler.applyConfigToStyleSheet(sheet))

    def setGridLayout(self):
        pass  # should be a grid layout by default when importing

    def addBottomVerticalSpacer(self):
        # widget = QtWidgets.QWidget()
        # layout = QtWidgets.QVBoxLayout()

        # widget.setLayout(layout)

        verticalSpacer = QtWidgets.QSpacerItem(
            20,
            40,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding,
        )
        # layout.addWidget(verticalSpacer)

        self.gridLayout.addItem(verticalSpacer)

    nRows = 0

    def addWidget(self, widget, i=None, j=None):
        if self.layoutType == "grid":
            if (i is None) or (j is None):
                logger.error(
                    f"Tried adding widget to Tab {Tab}, but grid layout needs i and j"
                )
                return

            self.gridLayout.addWidget(widget, i, j)
            self.nRows = max(self.nRows, 1 + i)

        else:
            logger.error(
                f"Tried adding widget to Tab {Tab}, but layoutType {self.layoutType} not recognised"
            )
            return

        if widget.parentSelector and (widget.dataWatcher is not None):
            self.datasetSelector.addUpdateCallback(widget.setDatasetDependencies)
            self.modelSelector.addUpdateCallback(widget.setModelDependencies)

        self.widgets.append(widget)

    def loadAllContent(self):
        for w in self.widgets:
            if hasattr(w, "dataWatcher"):
                w.dataWatcher.loadContent()
