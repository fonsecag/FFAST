from UI.Templates import (
    Widget,
    ListCheckButton,
    FlexibleListSelector,
    ExpandingScrollArea,
)
from PySide6 import QtCore, QtGui, QtWidgets
from config.uiConfig import configStyleSheet
from Utils.misc import rgbToHex
import logging
from events import EventChildClass

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

        self.widget = Widget(layout="vertical", color=color, parent=self)
        self.setContent(self.widget)

        self.widget.layout.setSpacing(0)

        self.topLayout = QtWidgets.QVBoxLayout()
        self.bottomLayout = QtWidgets.QGridLayout()

        self.widget.layout.addLayout(self.topLayout)
        self.widget.layout.addLayout(self.bottomLayout)

        self.hasDataSelector = hasDataSelector
        if hasDataSelector:
            self.widget.layout.setContentsMargins(40, 10, 40, 40)
            self.widget.layout.setSpacing(40)
            self.addDataSelector()

        else:
            self.widget.layout.setContentsMargins(40, 40, 40, 40)

    def addWidget(self, *args, **kwargs):
        self.bottomLayout.addWidget(*args, **kwargs)

    def addDataSelectionCallback(self, func):
        return self.dataSelector.addUpdateCallback(func)

    def addDataSelector(self):
        self.dataSelector = DatasetModelSelector(self.handler, parent=self)
        self.topLayout.addWidget(self.dataSelector)


class DatasetModelSelector(Widget, EventChildClass):
    def __init__(self, handler, **kwargs):
        self.handler = handler
        self.env = handler.env
        super().__init__(layout="vertical", **kwargs)
        EventChildClass.__init__(self)
        self.updateCallbacks = []

        self.env = handler.env
        self.layout.setSpacing(5)

        # CREATE LISTS AND ADD THEM TO THE LAYOUTS
        self.modelsList = FlexibleListSelector(label = 'Selected models')
        self.datasetsList = FlexibleListSelector(label = 'Selected datasets')
        self.datasetsList.singleSelection = True
        self.modelsList.setOnUpdate(self.update)
        self.datasetsList.setOnUpdate(self.update)
        self.layout.addWidget(self.modelsList)
        self.layout.addWidget(self.datasetsList)

        self.eventSubscribe("DATASET_LOADED", self.updateDatasetsList)
        self.eventSubscribe("DATASET_DELETED", self.updateDatasetsList)

        self.eventSubscribe("MODEL_LOADED", self.updateModelsList)
        self.eventSubscribe("MODEL_DELETED", self.updateModelsList)

    def updateModelsList(self, key):
        self.modelsList.removeWidgets(clear=True)
        keys = self.env.getAllModelKeys()

        for key in keys:
            w = DatasetModelLabel(self.handler, key, parent=self.modelsList)
            self.modelsList.addWidget(w)

    def updateDatasetsList(self, key):
        self.datasetsList.removeWidgets(clear=True)
        keys = self.env.getAllDatasetKeys()

        for key in keys:
            w = DatasetModelLabel(self.handler, key, parent = self.datasetsList)
            self.datasetsList.addWidget(w)

    def addUpdateCallback(self, func):
        self.updateCallbacks.append(func)

    def getSelectedKeys(self):
        modelKeys = []
        for w in self.modelsList.getWidgets():
            if w.checked:
                modelKeys.append(w.key)

        datasetKeys = []
        for w in self.datasetsList.getWidgets():
            if w.checked:
                datasetKeys.append(w.key)

        return modelKeys, datasetKeys

    def update(self):
        modelKeys, datasetKeys = self.getSelectedKeys()

        for func in self.updateCallbacks:
            func(modelKeys, datasetKeys)
