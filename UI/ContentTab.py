from UI.Templates import (
    Widget,
    ListCheckButton,
    FlexibleListSelector,
    ExpandingScrollArea,
)
from PySide6 import QtCore, QtGui, QtWidgets
from config.uiConfig import configStyleSheet
from utils import rgbToHex
import logging
from events import EventChildClass
from PySide6.QtWidgets import QSizePolicy

logger = logging.getLogger("FFAST")


class DatasetModelLabel(ListCheckButton, EventChildClass):
    def __init__(self, handler, key, **kwargs):
        self.handler = handler
        self.env = handler.env
        self.key = key

        super().__init__(**kwargs)
        EventChildClass.__init__(self)

        self.eventSubscribe("OBJECT_COLOR_CHANGED", self.onDatasetModelChanged)
        self.eventSubscribe("OBJECT_NAME_CHANGED", self.onDatasetModelChanged)

    def getColor(self):
        return self.env.getModelOrDataset(self.key).color

    def getLabel(self):
        return self.env.getModelOrDataset(self.key).getDisplayName()

    def onDatasetModelChanged(self, key):
        if key != self.key:
            return
        self.applyStyle()


class ContentTab(ExpandingScrollArea):
    def __init__(
        self, handler, hasDataSelector=True, color="@BGColor2", **kwargs
    ):
        self.handler = handler
        super().__init__(**kwargs)
        # self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        self.widget = Widget(layout="vertical", color=color, parent=self)
        self.setContent(self.widget)

        self.widget.layout.setSpacing(0)

        self.topLayout = QtWidgets.QVBoxLayout()
        self.bottomLayout = QtWidgets.QGridLayout()

        self.widget.layout.addLayout(self.topLayout)
        self.widget.layout.addLayout(self.bottomLayout)

        self.hasDataSelector = hasDataSelector
        self.widget.layout.setContentsMargins(40, 40, 40, 40)
        self.widget.layout.setSpacing(40)
        if hasDataSelector:
            self.addDataSelector()

    def addWidget(self, *args, **kwargs):
        self.bottomLayout.addWidget(*args, **kwargs)

    def addDataSelectionCallback(self, func):
        return self.dataSelector.addUpdateCallback(func)

    def setDataSelector(self, dataselector):
        self.widget.layout.setContentsMargins(40, 10, 40, 40)
        self.dataSelector = dataselector
        self.topLayout.addWidget(self.dataSelector)

    def addDataSelector(self):
        ds = DatasetModelSelector(self.handler, parent=self)
        self.setDataSelector(ds)


class DatasetModelSelector(Widget, EventChildClass):

    quiet = False

    def __init__(self, handler, **kwargs):
        self.handler = handler
        self.env = handler.env
        super().__init__(layout="vertical", **kwargs)
        EventChildClass.__init__(self)
        self.updateCallbacks = []

        self.env = handler.env
        self.layout.setSpacing(5)

        # CREATE LISTS AND ADD THEM TO THE LAYOUTS
        self.modelsList = FlexibleListSelector(
            label="Selected models", parent=self
        )
        self.datasetsList = FlexibleListSelector(
            label="Selected datasets", parent=self
        )
        self.modelsList.setOnUpdate(self.update)
        self.datasetsList.setOnUpdate(self.update)
        self.layout.addWidget(self.modelsList)
        self.layout.addWidget(self.datasetsList)

        self.eventSubscribe("DATASET_LOADED", self.updateDatasetsList)
        self.eventSubscribe("DATASET_DELETED", self.updateDatasetsList)
        self.eventSubscribe("DATASET_STATE_CHANGED", self.updateDatasetsList)

        self.eventSubscribe("MODEL_LOADED", self.updateModelsList)
        self.eventSubscribe("MODEL_DELETED", self.updateModelsList)

    def updateModelsList(self, key):
        self.quiet = True
        modelKeys, _ = self.getSelectedKeys()

        self.modelsList.removeWidgets(clear=True)
        keys = self.env.getAllModelKeys()

        for key in keys:
            w = DatasetModelLabel(self.handler, key, parent=self.modelsList)
            self.modelsList.addWidget(w)

        # reselect all models
        for w in self.modelsList.getWidgets():
            if w.key in modelKeys:
                w.setChecked(True, quiet=True)

        self.quiet = False
        self.update()

    def updateDatasetsList(self, key):

        self.quiet = True
        _, datasetKeys = self.getSelectedKeys()

        self.datasetsList.removeWidgets(clear=True)
        keys = self.env.getAllDatasetKeys()

        for key in keys:
            w = DatasetModelLabel(self.handler, key, parent=self.datasetsList)
            self.datasetsList.addWidget(w)

        # reselect all datasets
        for w in self.datasetsList.getWidgets():
            if w.key in datasetKeys:
                w.setChecked(True, quiet=True)

        self.quiet = False
        self.update()

    def addUpdateCallback(self, func):
        self.updateCallbacks.append(func)

    def getSelectedKeys(self):
        modelKeys = []
        for w in self.modelsList.getSelectedWidgets():
            modelKeys.append(w.key)

        datasetKeys = []
        for w in self.datasetsList.getSelectedWidgets():
            datasetKeys.append(w.key)

        return modelKeys, datasetKeys

    def update(self):
        if self.quiet:
            return
        modelKeys, datasetKeys = self.getSelectedKeys()

        for func in self.updateCallbacks:
            func(modelKeys, datasetKeys)
