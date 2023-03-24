from UI.Templates import (
    Widget,
    WidgetButton,
    FlexibleHList,
    ExpandingScrollArea,
)
from PySide6 import QtCore, QtGui, QtWidgets
from config.uiConfig import configStyleSheet
from Utils.misc import rgbToHex
import logging
from events import EventChildClass

logger = logging.getLogger("FFAST")


class DatasetModelLabel(WidgetButton, EventChildClass):
    colorCircleStyleSheet = """
        background-color: @COLOR;
        border-radius: 10;
    """
    styleSheet = """
        @OBJECT{border-radius:9px;}
        @OBJECT:hover{background-color:@BGColor4}
        @OBJECT[checked=true]{background-color:@BGColor4}
        @OBJECT[checked=true]:hover{background-color:@BGColor5}
    """

    def __init__(self, handler, key, type="label", onClick=None, **kwargs):
        self.handler = handler
        super().__init__(
            layout="horizontal",
            color="transparent",
            styleSheet=self.styleSheet,
            **kwargs
        )
        EventChildClass.__init__(self)

        self.env = handler.env
        self.key = key

        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(5)

        # setting color to transparent forces the widget to have a background at all for changing later
        self.colorCircle = Widget(parent=self, color="transparent")
        self.colorCircle.setFixedHeight(20)
        self.colorCircle.setFixedWidth(20)

        self.label = QtWidgets.QLabel("?", parent=self)
        self.label.setFixedHeight(20)

        self.layout.addWidget(self.colorCircle)
        self.layout.addWidget(self.label)

        self.eventSubscribe("OBJECT_COLOR_CHANGED", self.onDatasetModelChanged)

        self.applyStyle()

    def getColor(self):
        return self.env.getModelOrDataset(self.key).color

    def getName(self):
        return self.env.getModelOrDataset(self.key).getDisplayName()

    def applyStyle(self):
        ss = self.colorCircleStyleSheet.replace(
            "@COLOR", rgbToHex(*self.getColor())
        )
        self.colorCircle.setStyleSheet(configStyleSheet(ss))

        self.label.setText(self.getName())

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

        # CREATE LAYOUTS AND ADD LIST LABELS
        self.modelsLayout = QtWidgets.QHBoxLayout()
        self.datasetsLayout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.modelsLayout)
        self.layout.addLayout(self.datasetsLayout)

        self.modelsLabel = QtWidgets.QLabel("Selected models")
        self.datasetsLabel = QtWidgets.QLabel("Selected datasets")
        self.modelsLayout.addWidget(self.modelsLabel)
        self.datasetsLayout.addWidget(self.datasetsLabel)

        self.modelsLabel.setFixedWidth(110)
        self.modelsLabel.setObjectName("titleLabel")
        self.datasetsLabel.setFixedWidth(110)
        self.datasetsLabel.setObjectName("titleLabel")

        # CREATE LISTS AND ADD THEM TO THE LAYOUTS
        self.modelsList = FlexibleHList()
        self.datasetsList = FlexibleHList()
        self.modelsLayout.addWidget(self.modelsList)
        self.datasetsLayout.addWidget(self.datasetsList)

        self.eventSubscribe("DATASET_LOADED", self.updateDatasetsList)
        self.eventSubscribe("DATASET_DELETED", self.updateDatasetsList)

        self.eventSubscribe("MODEL_LOADED", self.updateModelsList)
        self.eventSubscribe("MODEL_DELETED", self.updateModelsList)

    def updateModelsList(self, key):
        self.modelsList.removeWidgets(clear=True)
        keys = self.env.getAllModelKeys()

        for key in keys:
            w = DatasetModelLabel(self.handler, key, type="button")
            w.setOnClick(self.update)
            self.modelsList.addWidget(w)

    def updateDatasetsList(self, key):
        self.datasetsList.removeWidgets(clear=True)
        keys = self.env.getAllDatasetKeys()

        for key in keys:
            w = DatasetModelLabel(self.handler, key, type="button")
            w.setOnClick(self.update)
            self.datasetsList.addWidget(w)

    def addUpdateCallback(self, func):
        self.updateCallbacks.append(func)

    def getSelectedKeys(self):
        modelKeys = []
        for w in self.modelsList.widgets:
            if w.checked:
                modelKeys.append(w.key)

        datasetKeys = []
        for w in self.datasetsList.widgets:
            if w.checked:
                datasetKeys.append(w.key)

        return modelKeys, datasetKeys

    def update(self):
        modelKeys, datasetKeys = self.getSelectedKeys()

        for func in self.updateCallbacks:
            func(modelKeys, datasetKeys)
