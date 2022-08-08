from events import EventWidgetClass
import sys, os, time
from PySide6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import numpy as np
from Utils.uiLoader import loadUi
import logging
from client.dataWatcher import DataWatcher
from UI.utils import DatasetModelSelector, DataLoaderButton
from datasetLoaders.loader import SubDataset

logger = logging.getLogger("FFAST")

PLOT_WIDGETS = []
GIVEN_NAMES = []


class BasicPlotContainer(EventWidgetClass, QtWidgets.QWidget):
    def __init__(
        self,
        handler,
        title="",
        name=None,
        hasDatasetSelector=False,
        singleDataset=False,
        hasModelSelector=False,
        singleModel=False,
        hasLegend=True,
        isSubbable=True,
        parentSelector=False,
        bypassMinimumSize=False,
    ):
        self.handler = handler
        self.env = self.handler.env
        super().__init__()

        loadUi(os.path.join(self.handler.uiFilesPath, "plotWidget.ui"), self)

        if name is None:
            raise ValueError(f"BasicPlotContainer needs a name, none given")
        elif name in GIVEN_NAMES:
            raise ValueError(
                f"BasicPlotContainer needs a unique name, but `{name}` already given"
            )

        self.setObjectName(name)
        self.name = name
        GIVEN_NAMES.append(name)

        PLOT_WIDGETS.append(self)

        self.plotWidget = pg.PlotWidget(name=name + "PlotWidget", title=title)
        self.plotItem = self.plotWidget.getPlotItem()
        self.mainLayout.addWidget(self.plotWidget)
        self.plotWidget.setBackground(None)

        self.plotItem.setTitle(title=title)

        self.data = []
        self.plotItems = []

        self.eventSubscribe("WIDGET_REFRESH", self.onWidgetRefresh)
        self.eventSubscribe("WIDGET_VISUAL_REFRESH", self.visualRefresh)
        self.eventSubscribe("QUIT_READY", self.onQuit)
        self.initialiseWatcher()

        self.loadButton = DataLoaderButton(self.handler, self.dataWatcher)
        self.toolbarLayout.insertWidget(0, self.loadButton)

        # when added to a tab, will link the dataset and model selection to tab toolbar
        self.parentSelector = parentSelector

        self.hasLegend = hasLegend
        if hasLegend:
            self.legend = pg.LegendItem(
                offset=(30, 10),
                labelTextSize="12pt",
                labelTextColor=self.handler.config["envs"].get("TextColor1"),
            )
            self.legend.setParentItem(self.plotWidget.graphicsItem())

        n = 1
        if hasDatasetSelector:
            cb = DatasetModelSelector(
                self.handler,
                "dataset",
                text="Choose datasets",
                singleSelect=singleDataset,
            )
            self.addWidgetToToolbar(cb)
            cb.addUpdateCallback(self.setDatasetDependencies)
            n += 1

        if hasModelSelector:
            cb = DatasetModelSelector(
                self.handler,
                "model",
                text="Choose models",
                singleSelect=singleModel,
            )
            self.addWidgetToToolbar(cb)
            cb.addUpdateCallback(self.setModelDependencies)
            n += 1

        self.isSubbable = isSubbable
        if isSubbable:
            cb = QtWidgets.QCheckBox("Sub", self)
            self.addWidgetToToolbar(cb)
            self.subCheckBox = cb
            cb.stateChanged.connect(self.onSubStateChanged)

            self.plotWidget.sigRangeChanged.connect(self.updateSub)

        if bypassMinimumSize:
            self.setMinimumSize(0, 0)

    active3DIndex = -1

    def isSubbing(self):
        return self.subCheckBox.isChecked()

    def addWidgetToToolbar(self, widget):
        n = self.toolbarLayout.count()
        self.toolbarLayout.insertWidget(n - 1, widget)

    def setXLabel(self, label, unit=None):
        if unit is not None:
            label = f"{label} [{unit}]"
        self.plotWidget.setLabel("bottom", label)

    def setYLabel(self, label, unit=None):
        if unit is not None:
            label = f"{label} [{unit}]"
        self.plotWidget.setLabel("left", label)

    def setXTicks(self, x, labels):
        ax = self.plotWidget.getAxis("bottom")
        n = len(x)
        ax.setTicks([[(x[i], str(labels[i])) for i in range(n)]])

    def setYTicks(self, y, labels):
        ay = self.plotWidget.getAxis("left")
        n = len(y)
        ay.setTicks([[(y[i], str(labels[i])) for i in range(n)]])

    def getRanges(self):
        x1, y1, x2, y2 = self.plotWidget.visibleRange().getCoords()
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

    def updateSub(self, **kwargs):  # kwargs deprecated
        if not self.isSubbing():
            return

        subDatasets = self.getValidSubDatasets()
        for (dataset, model, idx) in subDatasets:
            self.declareSubDataset(dataset, model, idx)

    def declareSubDataset(self, dataset, model, idx):
        self.env.declareSubDataset(dataset, model, idx, self.name)

    def getDatasetSubIndices(self, dataset, model):
        raise NotImplementedError

    def onWidgetRefresh(self, widget):
        if self is not widget:
            return

        # updateKey = self.dataWatcher.getUpdateKey()

        # if updateKey == self.lastUpdateKey:
        #     return

        # self.lastUpdateKey = updateKey
        self.refresh()

    def setDataDependencies(self, *args, **kwargs):
        self.dataWatcher.setDataDependencies(*args, **kwargs)

    def setDatasetDependencies(self, *args, **kwargs):
        self.dataWatcher.setDatasetDependencies(*args, **kwargs)

    def setModelDependencies(self, *args, **kwargs):
        self.dataWatcher.setModelDependencies(*args, **kwargs)

    def onQuit(self):
        self.plotWidget.close()

    dataWatcher = None

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

    def plot(self, x, y, **kwargs):
        colors = self.handler.env.getConfig("plotColors")
        N = len(self.plotItems) % len(colors)

        if "pen" in kwargs:
            pen = kwargs["pen"]
            del kwargs["pen"]
        else:
            color = colors[N]
            pen = pg.mkPen(color, width=2.5)

        # plotItem = self.plotWidget.plot(x, y, pen=pg.mkPen(color, width=2.5))
        plotItem = pg.PlotDataItem(x, y, pen=pen, **kwargs)
        self.plotItem.addItem(plotItem)
        self.plotItems.append(plotItem)

    def stepPlot(self, x, y, width=1, **kwargs):
        xLeft, xRight = x - width / 2, x + width / 2
        newX = np.zeros(xLeft.shape[0] * 2)
        newX[::2] = xLeft
        newX[1::2] = xRight

        newY = np.repeat(y, 2)

        self.plot(newX, newY, **kwargs)

    def mapSceneToView(self, arg1, arg2=None):
        if arg2 is not None:
            arg1 = QtCore.QPointF(arg1, arg2)
        return self.plotItem.getViewBox().mapSceneToView(arg1)


class LoupePlot(BasicPlotContainer):
    def __init__(self, handler, loupe, title="N/A", name="N/A"):

        super().__init__(
            handler,
            title=title,
            name=f"{name}_{loupe.nPlotWidget}",
            bypassMinimumSize=True,
            isSubbable=False,
        )
        self.plotWidget.sigRangeChanged.connect(self.updateSub)
        self.loupe = loupe

    def isSubbing(self):
        return True

    def updateSub(self, **kwargs):
        dataset = self.handler.env.getDataset(self.loupe.selectedDatasetKey)
        if dataset is None:
            return
        idx = self.getDatasetSubIndices(dataset, None)
        self.loupe.setActiveIndices(idx)
