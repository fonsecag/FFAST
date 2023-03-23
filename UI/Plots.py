from UI.Templates import Widget, ToolCheckButton, PushButton
from PySide6 import QtCore, QtGui, QtWidgets
from config.uiConfig import config, configStyleSheet
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QWidget, QTabWidget
from config.uiConfig import config, getIcon
from PySide6.QtWidgets import QSizePolicy
from events import EventChildClass
import pyqtgraph
import logging
from client.dataWatcher import DataWatcher
import numpy as np


class DataloaderButton(PushButton, EventChildClass):

    styleSheet = """
        border: 1px solid @HLColor2;
        color: @HLColor2;
    """

    def __init__(self, handler, watcher, **kwargs):
        super().__init__("Load", styleSheet=self.styleSheet, **kwargs)
        self.handler = handler
        EventChildClass.__init__(self)
        self.dataWatcher = watcher

        self.setIcon(QtGui.QIcon(getIcon("load")))


class BasicPlotWidget(Widget, EventChildClass):

    dataWatcher = None
    lastUpdatedTimestamp = -1

    styleSheet = """
        border-radius:10px;
    """

    def __init__(
        self,
        handler,
        env,
        name="N/A",
        title="N/A",
        hasLegend=True,
        isSubbable=True,
        color="@BGColor3",
        **kwargs,
    ):
        self.handler = handler
        self.env = env
        super().__init__(
            layout="vertical",
            color="@BGColor3",
            styleSheet=self.styleSheet,
            **kwargs,
        )
        EventChildClass.__init__(self)
        self.colorString = color
        self.layout.setContentsMargins(13, 13, 13, 13)
        self.layout.setSpacing(8)
        self.name = name
        self.initialiseWatcher()

        # TOOLBAR
        self.toolbar = Widget(layout="horizontal", color="green")
        self.toolbar.setFixedHeight(30)
        self.toolbar.setObjectName("plotToolbar")
        self.layout.addWidget(self.toolbar)
        self.applyToolbar(title=title)

        # DIVIDER
        divider = Widget(color="@TextColor3")
        divider.setFixedHeight(1)
        self.layout.addWidget(divider)

        # PLOTWIDGET
        self.plotWidget = pyqtgraph.PlotWidget(name=f"{name}PlotWidget")
        self.plotItem = self.plotWidget.getPlotItem()
        self.layout.addWidget(self.plotWidget)
        self.applyPlotWidget()

        # LEGEND
        self.applyLegend(hasLegend)
        self.applyStyle()

    def applyToolbar(self, title="N/A"):
        tb = self.toolbar
        layout = self.toolbar.layout
        layout.setContentsMargins(20, 0, 0, 0)
        layout.setSpacing(8)

        self.titleLabel = QtWidgets.QLabel(title)
        self.titleLabel.setObjectName("plotTitleLabel")
        layout.addWidget(self.titleLabel)

        layout.addStretch()

        self.subCheckBox = ToolCheckButton(self.handler, lambda: None)
        layout.addWidget(self.subCheckBox)

        self.loadButton = DataloaderButton(self.handler, self.dataWatcher)
        layout.addWidget(self.loadButton)

    def applyPlotWidget(self):
        pi = self.plotItem
        pw = self.plotWidget

        pi.setContentsMargins(7, 7, 7, 7)  # fixes axis cutting

    def applyStyle(self):
        self.setMinimumSize(400, 400)
        self.setSizePolicy(
            QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding
        )

        color = config["envs"].get(self.colorString.replace("@", ""))
        self.plotWidget.setBackground(color)

    def applyLegend(self, hasLegend):
        self.hasLegend = hasLegend
        if not hasLegend:
            return

        self.legend = pyqtgraph.LegendItem(
            offset=(30, 10),
            labelTextSize="12pt",
            labelTextColor=self.handler.config["envs"].get("TextColor1"),
        )
        self.legend.setParentItem(self.plotWidget.graphicsItem())

    def isSubbing(self):
        return self.subCheckBox.isChecked()

    def addWidgetToToolbar(self, widget):
        n = self.toolbarLayout.count()
        self.toolbarLayout.insertWidget(n - 1, widget)

    def setXLabel(self, label, unit=None):
        fontOptions = {"font-size": "20px", "color": "lightgray"}
        if unit is not None:
            label = f"{label} [{unit}]"
        self.plotWidget.setLabel("bottom", label, **fontOptions)

    def setYLabel(self, label, unit=None):
        fontOptions = {"font-size": "20px", "color": "lightgray"}
        if unit is not None:
            label = f"{label} [{unit}]"
        self.plotWidget.setLabel("left", label, **fontOptions)

    def setXTicks(self, x, labels):
        ax = self.plotWidget.getAxis("bottom")
        n = len(x)
        ax.setTicks([[(x[i], str(labels[i])) for i in range(n)]])

    def setYTicks(self, y, labels):
        ay = self.plotWidget.getAxis("left")
        n = len(y)
        ay.setTicks([[(y[i], str(labels[i])) for i in range(n)]])

    def getRanges(self):
        (x1, y1, x2, y2) = self.plotWidget.visibleRange().getCoords()
        return (x1, x2), (y1, y2)

    def onSubStateChanged(self):
        existingSubs = self.getExistingSubDatasets()

        subbing = self.isSubbing()
        for sub in existingSubs:
            sub.setActive(subbing)

        if subbing:
            self.updateSub()

        self.refresh()

    def getValidSubDatasets(self, asFingerprint=False):
        subs = []
        env = self.env

        datasetKeys = self.dataWatcher.getDatasetDependencies()
        modelKeys = self.dataWatcher.getModelDependencies()

        for datasetKey in datasetKeys:
            dataset = env.getDataset(datasetKey)

            # dont do subdatasets of subdatasets
            if dataset.isSubDataset:
                continue

            for modelKey in modelKeys:
                model = env.getModel(modelKey)

                idx = self.getDatasetSubIndices(dataset, model)
                if (idx is None) or (len(idx) == 0):
                    idx = None

                if asFingerprint:
                    fp = SubDataset.getFingerprint(
                        SubDataset, dataset, model, self.name
                    )
                    subs.append(fp)
                else:
                    subs.append((dataset, model, idx))

        return subs

    def getExistingSubDatasets(self):
        fps = self.getValidSubDatasets(asFingerprint=True)
        ds = []
        for fp in fps:
            sub = self.env.getDataset(fp)
            if sub is not None:
                ds.append(sub)

        return ds

    def updateSub(self):
        if not self.isSubbing():
            return

        subDatasets = self.getValidSubDatasets()
        for dataset, model, idx in subDatasets:
            self.declareSubDataset(dataset, model, idx)

    def declareSubDataset(self, dataset, model, idx):
        self.env.declareSubDataset(dataset, model, idx, self.name)

    def getDatasetSubIndices(self, dataset, model):
        raise NotImplementedError

    def onWidgetRefresh(self, widget):
        if self is not widget:
            return
        self.refresh()

    def setDataDependencies(self, *args, **kwargs):
        self.dataWatcher.setDataDependencies(*args, **kwargs)

    def setDatasetDependencies(self, *args, **kwargs):
        self.dataWatcher.setDatasetDependencies(*args, **kwargs)

    def setModelDependencies(self, *args, **kwargs):
        self.dataWatcher.setModelDependencies(*args, **kwargs)

    def onQuit(self):
        self.plotWidget.close()

    def initialiseWatcher(self):
        dw = DataWatcher(self.handler.env)
        dw.addRefreshWidget(self)

        self.dataWatcher = dw
        self.dataWatcher.parentName = self.name

    def getWatchedData(self):
        return self.dataWatcher.getWatchedData()

    def refresh(self):
        self.visualRefresh()

    def addPlots(self):
        # placeholder, should be implemented by user
        return NotImplementedError

    def visualRefresh(self):
        # when many refresh events happen in a single loop, no need to
        # refresh every time since information won't change
        if self.eventClockTimestamp <= self.lastUpdatedTimestamp:
            return

        self.lastUpdatedTimestamp = self.eventClockTimestamp

        self.clear()

        self.addPlots()
        if self.hasLegend:
            self.refreshLegend()

    def refreshLegend(self):
        dw = self.dataWatcher
        hasDataset = len(dw.getDatasetDependencies()) > 1
        hasModel = len(dw.getModelDependencies()) > 1

        self.legend.clear()

        if hasDataset or hasModel:
            names = []

            for x in self.getWatchedData():
                s = ""
                if hasDataset and (x["dataset"] is not None):
                    s = x["dataset"].getDisplayName()

                if hasModel and (x["model"] is not None):
                    if hasDataset:
                        s += " & "
                    s += x["model"].getName()

                names.append(s)

        else:
            return

        for i in range(len(self.plotItems)):
            item = self.plotItems[i]
            self.legend.addItem(item, names[i])

    def clear(self):
        for item in self.plotItems:
            self.plotWidget.removeItem(item)
            del item

        self.plotItems = []

    def plot(self, x, y, scatter=False, **kwargs):
        self.plotItem.disableAutoRange()
        colors = self.handler.env.getConfig("plotColors")
        N = len(self.plotItems) % len(colors)
        color = colors[N]

        if "pen" in kwargs:
            pen = kwargs["pen"]
            del kwargs["pen"]
        else:
            pen = pg.mkPen(color, width=2.5)

        # plotItem = self.plotWidget.plot(x, y, pen=pg.mkPen(color, width=2.5))
        if scatter:
            brush = pg.mkBrush(color)
            plotItem = pg.ScatterPlotItem(x, y, symbolBrush=brush)
        else:
            plotItem = pg.PlotDataItem(x, y, pen=pen, **kwargs)

        self.plotItem.addItem(plotItem)
        self.plotItems.append(plotItem)
        self.plotItem.autoRange()

    def stepPlot(self, x, y, width=1, **kwargs):
        xLeft, xRight = (x - width / 2, x + width / 2)
        newX = np.zeros(xLeft.shape[0] * 2)
        newX[::2] = xLeft
        newX[1::2] = xRight

        newY = np.repeat(y, 2)

        self.plot(newX, newY, **kwargs)

    def mapSceneToView(self, arg1, arg2=None):
        if arg2 is not None:
            arg1 = QtCore.QPointF(arg1, arg2)
        return self.plotItem.getViewBox().mapSceneToView(arg1)
