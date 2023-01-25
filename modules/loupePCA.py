import numpy as np
from client.dataType import DataType, DataEntity
import logging
from scipy.stats import gaussian_kde
from sklearn.decomposition import KernelPCA

logger = logging.getLogger("FFAST")


def loadData(env):
    class DatasetKernelPCA3(DataType):

        modelDependent = False
        datasetDependent = True
        key = "kpca3"
        # no dependencies

        def __init__(self, *args):
            super().__init__(*args)

        def data(self, dataset=None, model=None, taskID=None):
            env = self.env

            d = dataset.getPDist()
            kpca = KernelPCA(n_components=3, kernel="rbf")
            if len(d) > 1000:
                trainIdxs = np.random.choice(
                    np.arange(len(d)), 1000, replace=False
                )
                dTrain = d[trainIdxs]
                kpca.fit(dTrain)
                y = kpca.transform(d)
            else:
                y = kpca.fit_transform(d)

            de = self.newDataEntity(y=y)
            env.setData(de, self.key, model=model, dataset=dataset)

            return True

    env.registerDataType(DatasetKernelPCA3)


def loadUI(UIHandler, env):

    from UI.plots import LoupePlot

    class LoupeKPCA3Plot(LoupePlot):
        def __init__(self, handler, loupe):
            super().__init__(
                handler, loupe, title="Kernel PCA", name="LoupeKPCA"
            )
            self.setDataDependencies("kpca3")
            self.setXLabel("Component 1")
            self.setYLabel("Component 2")

        def addPlots(self):
            for x in self.getWatchedData():
                de = x["dataEntry"]
                y = de.get()
                self.plot(y[:, 0], y[:, 1], pen=None, symbol="o")

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange
            y0, y1 = yRange

            kpca = self.env.getData("kpca3", dataset=dataset).get()

            xTruth = (kpca[:, 0] > x0) & (kpca[:, 0] < x1)
            yTruth = (kpca[:, 1] > y0) & (kpca[:, 1] < y1)
            return np.argwhere(xTruth & yTruth).flatten()

    def loupeAddon(UIHandler, loupe):
        tabWidget = loupe.newTab("PCA")
        kpcaPlot = LoupeKPCA3Plot(UIHandler, loupe)
        loupe.registerLoupePlot(kpcaPlot)
        tabWidget.layout.insertWidget(-1, kpcaPlot)

    UIHandler.addLoupeAddon(loupeAddon)
