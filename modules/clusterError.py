import numpy as np
from PySide6.QtWidgets import QCheckBox
from client.dataType import DataType, DataEntity
from sklearn.cluster import AgglomerativeClustering
from sklearn.cluster import KMeans
from UI.plots import BasicPlotContainer
from UI.tab import Tab
import logging
import pyqtgraph as pg
import math

logger = logging.getLogger("FFAST")


def smallestMaxDistanceEuclidean(sample, clData):
    g = np.zeros(len(clData))

    for i in range(len(clData)):
        g[i] = np.max(
            np.sum(np.square(clData[i] - sample), 1)
        )  # numpy difference=>clusters[c]-sample elementwise for each c

    return np.argmin(g)


def agglomerative(desc, n, nInitPoints):
    indAll = np.arange(len(desc))
    indInit = np.random.permutation(indAll)[:nInitPoints]

    descInit = desc[indInit]

    indRest = np.delete(indAll, indInit)
    descRest = desc[indRest]
    lDescRest = len(descRest)

    cinitLabels = AgglomerativeClustering(
        affinity="euclidean", n_clusters=n, linkage="complete"
    ).fit_predict(descInit)

    # gather cluster data from labels and return to original indices
    clind, cldesc = [], []
    for i in range(n):
        ind = np.concatenate(np.argwhere(cinitLabels == i))

        # convert back to initial set of indices
        ind = indInit[ind]

        clind.append(ind.tolist())
        cldesc.append(np.array(desc[clind[i]]))

    for i in range(lDescRest):
        c = smallestMaxDistanceEuclidean(descRest[i], cldesc)
        clind[c].append(indRest[i])

    return [np.array(x) for x in clind]


def kMeans(desc, n):
    clLabels = KMeans(n_clusters=n, init="k-means++").fit_predict(desc)

    clind = []

    for i in range(n):
        argwhere = np.argwhere(clLabels == i)
        if len(argwhere) < 1:
            continue
        ind = np.concatenate(argwhere)

        # convert back to initial set of indices
        # no need here
        clind.append(ind)

    return clind


class DatasetCluster(DataType):

    modelDependent = False
    datasetDependent = True
    key = "datasetCluster"
    dependencies = []

    def __init__(self, *args):
        super().__init__(*args)

    def cluster(self, dataset, scheme, indices=None, taskID=None):
        env = self.env
        if scheme["desc"] == "Coulomb":
            d = dataset.getPDist(indices=indices)
        elif scheme["desc"] == "Energy":
            d = dataset.getEnergies(indices=indices).reshape(-1, 1)
        else:
            logger.error(
                f"Unrecognised cluster scheme descriptor {scheme['desc']}"
            )

        nClusters = scheme["nClusters"]

        if scheme["type"] == "Agglo":
            localClind = agglomerative(
                d, nClusters, env.getConfig("aggloNInitPoints")
            )
        elif scheme["type"] == "KMeans":
            localClind = kMeans(d, nClusters)
        else:
            logger.error(f"Unrecognised cluster scheme type {scheme['type']}")

        # fix indices
        if indices is not None:
            clind = []
            for idx in localClind:
                clind.append(indices[idx])

        return clind

    def clindToLabels(self, dataset, clinds):
        N = dataset.getN()
        labels = np.zeros(N)

        for i in range(len(clinds)):
            clind = clinds[i]
            labels[clind] = i

        return labels

    def data(self, dataset=None, model=None, taskID=None):
        env = self.env

        schemes = env.getConfig("clusterScheme")
        clinds = [np.arange(dataset.getN())]
        for s in schemes:
            newClinds = []
            for idxs in clinds:
                clind = self.cluster(dataset, s, idxs)
                newClinds += clind

            clinds = newClinds

        labels = self.clindToLabels(dataset, clinds)

        de = self.newDataEntity(clind=clinds, labels=labels)
        env.setData(de, self.key, model=model, dataset=dataset)
        return True


class ClusterForceError(DataType):

    modelDependent = True
    datasetDependent = True
    key = "clusterForceError"
    dependencies = ["datasetCluster", "forcesError"]

    def __init__(self, *args):
        super().__init__(*args)

    def data(self, dataset=None, model=None, taskID=None):
        env = self.env

        err = env.getData("forcesError", model=model, dataset=dataset)
        diff = np.abs(err.get("diff"))
        diff = diff.reshape(diff.shape[0], -1)
        mae = np.abs(diff)

        clind = env.getData("datasetCluster", dataset=dataset)
        clind = clind.get("clind")

        clerr = []
        for x in clind:
            clerr.append(np.mean(mae[x]))

        de = self.newDataEntity(clerr=np.array(clerr))
        env.setData(de, self.key, model=model, dataset=dataset)
        return True


class ClusterEnergyError(DataType):

    modelDependent = True
    datasetDependent = True
    key = "clusterEnergyError"
    dependencies = ["datasetCluster", "energyError"]

    def __init__(self, *args):
        super().__init__(*args)

    def data(self, dataset=None, model=None, taskID=None):
        env = self.env

        err = env.getData("energyError", model=model, dataset=dataset)
        diff = np.abs(err.get("diff"))
        diff = diff.reshape(diff.shape[0], -1)
        mae = np.abs(diff)

        clind = env.getData("datasetCluster", dataset=dataset)
        clind = clind.get("clind")

        clerr = []
        for x in clind:
            clerr.append(np.mean(mae[x]))

        de = self.newDataEntity(clerr=np.array(clerr))
        env.setData(de, self.key, model=model, dataset=dataset)
        return True


class OrderingCheckBox(QCheckBox):
    def __init__(self, plotWidget):
        super().__init__()
        self.plotWidget = plotWidget

        self.setText("Ordered")
        self.stateChanged.connect(self.onStateChanged)

    def onStateChanged(self, state):
        checked = self.isChecked()
        if self.isChecked():
            self.plotWidget.setXLabel("Ordered cluster index")
            # self.plotWidget.subCheckBox.setEnabled(False)
        else:
            self.plotWidget.setXLabel("Cluster index")
            # self.plotWidget.subCheckBox.setEnabled(True)

        self.plotWidget.refresh()
        if self.plotWidget.isSubbing():
            self.plotWidget.updateSub()


class ClusterErrorPlot(BasicPlotContainer):
    def __init__(self, handler, tab, title="N/A", name="N/A"):
        super().__init__(
            handler,
            parentSelector=True,
            title=title,
            isSubbable=True,
            name=name,
        )
        self.setXLabel("Cluster index")

        # add a ordering checkbox to toolbar
        cb = OrderingCheckBox(self)
        self.addWidgetToToolbar(cb)
        self.orderingCheckBox = cb
        self.plotItem.setMouseEnabled(x=None, y=None)

        self.plotWidget.eventFilter = self.eventFilter

        # https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/ViewBox/ViewBox.html#ViewBox
        self.plotItem.getViewBox().state["mouseEnabled"] = [False, False]
        # self.plotItem.getViewBox().state['wheelScaleFactor'] = 0

        self.regions = []
        self.selectedRegions = []

        self.plotWidget.scene().sigMouseClicked.connect(self.mouseClicked)
        self.plotWidget.scene().sigMouseMoved.connect(self.mouseMoved)

        self.noneBrush = pg.mkBrush(None)
        self.hoverBrush = pg.mkBrush(0, 0, 255, 80)
        self.selectedBrush = pg.mkBrush(0, 0, 255, 50)

    orderedModelKey = None
    currentN = -1
    modelOrder = {}

    def addPlots(self):
        i = 0
        orderedModelKey = None
        N = 0
        self.currentN = 0

        for x in self.getWatchedData():
            de = x["dataEntry"]
            model = x["model"]
            clerr = de.get("clerr")
            N = len(clerr)
            self.currentN = max(self.currentN, N)

            order = np.argsort(clerr)
            self.modelOrder[model.fingerprint] = order

            if self.isOrdered():
                clerr = clerr[order]
            else:
                if orderedModelKey is None:
                    orderedModelKey = model.fingerprint
                    self.orderedModelKey = model.fingerprint
                clerr = clerr[self.modelOrder[orderedModelKey]]

            self.stepPlot(np.arange(N), clerr)

        if orderedModelKey is not None:
            self.setXTicks(np.arange(N), self.modelOrder[orderedModelKey])
        else:
            x = np.arange(N)
            self.setXTicks(x, x)

        self.createRegions(N)
        self.orderRegions()

    def createRegions(self, N):
        for i in range(len(self.regions), N):
            reg = pg.LinearRegionItem(
                movable=False, pen=pg.mkPen(None), brush=self.noneBrush
            )
            self.regions.append(reg)
            self.plotWidget.addItem(reg)

    def orderRegions(self):
        if not self.isSubbing():
            for reg in self.regions:
                reg.hide()
            return

        for i in range(self.currentN):
            reg = self.regions[i]
            # idx = self.currentOrder[i]
            reg.setRegion((i - 0.5, i + 0.5))
            reg.show()

    def isOrdered(self):
        return self.orderingCheckBox.isChecked()

    def viewCoordsToIndex(self, x, y):
        coords = self.mapSceneToView(x, y)
        x, y = (coords.x(), coords.y())

        return math.floor(x + 0.5)

    def mouseClicked(self, event):
        (x, y) = event.scenePos()
        idx = self.viewCoordsToIndex(x, y)
        self.toggleSelectCluster(idx)

    hoveredIndex = -1

    def mouseMoved(self, point):
        idx = self.viewCoordsToIndex(point.x(), point.y())
        if idx == self.hoveredIndex:
            return

        self.hoveredIndex = idx
        self.updateRegionBrushes()

    def updateRegionBrushes(self):
        if self.currentN < 1:
            return

        for i in range(self.currentN):
            reg = self.regions[i]
            if i == self.hoveredIndex:
                reg.setBrush(self.hoverBrush)
            elif i in self.selectedRegions:
                reg.setBrush(self.selectedBrush)
            else:
                reg.setBrush(self.noneBrush)

        # force a refresh of the plot
        if reg.isVisible():
            reg.hide()
            reg.show()

        if self.isSubbing():
            self.updateSub()

    def toggleSelectCluster(self, idx):
        if idx in self.selectedRegions:
            self.selectedRegions.remove(idx)
        else:
            self.selectedRegions.append(idx)

        self.updateRegionBrushes()

    def getDatasetSubIndices(self, dataset, model):

        indices = self.modelOrder[model.fingerprint][self.selectedRegions]

        if (not self.isOrdered()) and (
            model.fingerprint != self.orderedModelKey
        ):
            return None

        clind = self.env.getData("datasetCluster", dataset=dataset)
        labels = clind.get("labels")

        idxs = np.argwhere(np.isin(labels, indices)).flatten()
        return idxs


class ForcesClusterErrorPlot(ClusterErrorPlot):
    def __init__(self, handler, tab):
        super().__init__(
            handler, tab, title="Forces Cluster Error", name="ClFoErr"
        )

        self.setDataDependencies("clusterForceError")
        self.setYLabel("Force MAE", "kcal/mol A")


class EnergyClusterErrorPlot(ClusterErrorPlot):
    def __init__(self, handler, tab):
        super().__init__(
            handler, tab, title="Energy Cluster Error", name="ClEnErr"
        )

        self.setDataDependencies("clusterEnergyError")
        self.setYLabel("Energy MAE", "kcal/mol")


def load(UIHandler, env):
    env.registerDataType(DatasetCluster)
    env.registerDataType(ClusterForceError)
    env.registerDataType(ClusterEnergyError)

    tab = Tab(
        UIHandler,
        hasDatasetSelector=True,
        hasModelSelector=True,
        singleDataset=True,
    )
    UIHandler.addTab(tab, "Cluster Error")

    plot = ForcesClusterErrorPlot(UIHandler, tab)
    tab.addWidget(plot, 0, 0)

    plot = EnergyClusterErrorPlot(UIHandler, tab)
    tab.addWidget(plot, 1, 0)

    tab.addBottomVerticalSpacer()
