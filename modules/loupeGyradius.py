import numpy as np
from config.userConfig import getConfig
from client.dataType import DataType
from scipy.stats import gaussian_kde
import logging

logger = logging.getLogger("FFAST")
DEPENDENCIES = ["basicErrors"]


class GyrationRadius(DataType):
    modelDependent = False
    datasetDependent = True
    key = "gyradius"
    dependencies = []
    iterable = True

    def __init__(self, *args):
        super().__init__(*args)

    def data(self, dataset=None, model=None, taskID=None):
        env = self.env

        R = dataset.getCoordinates()  # (N, nA, 3)
        com = np.mean(R, axis=1)  # (N, 3)

        diff = R - com.reshape(-1, 1, 3)  # (N, nA, 3)

        s = np.sqrt(np.sum(diff ** 2, axis=2))  # (N, nA)

        z = dataset.getElements()

        gyradius = np.sqrt(np.sum(z * s ** 2, axis=1) / np.sum(z))

        de = self.newDataEntity(gyradius=gyradius)  # , mae=mae)
        env.setData(de, self.key, model=model, dataset=dataset)
        return True


class GyrationDistribution(DataType):
    modelDependent = False
    datasetDependent = True
    key = "gyradiusDist"
    dependencies = ["gyradius"]
    iterable = False

    def __init__(self, *args):
        super().__init__(*args)

    def data(self, dataset=None, model=None, taskID=None):
        env = self.env

        data = env.getData("gyradius", dataset=dataset)

        gyr = data.get("gyradius")

        kde = gaussian_kde(gyr)

        delta = np.max(gyr) - np.min(gyr)

        distX = np.linspace(
            np.min(gyr) - delta * 0.05,
            np.max(gyr) + delta * 0.05,
            getConfig("plotDistNum"),
        )
        distY = kde(distX)

        de = self.newDataEntity(distY=distY, distX=distX)
        env.setData(de, self.key, model=model, dataset=dataset)
        return True


def loadData(env):
    env.registerDataType(GyrationRadius)
    env.registerDataType(GyrationDistribution)


def loadUI(UIHandler, env):
    from UI.ContentTab import ContentTab
    from UI.Plots import BasicPlotWidget
    from UI.Templates import Slider

    ct = ContentTab(UIHandler)
    UIHandler.addContentTab(ct, "Gyration")

    class GyradiusPlot(BasicPlotWidget):
        smoothing = 1

        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Total gyration radius",
                name="Total Gyradius",
                isSubbable=True,
                **kwargs,
            )
            self.setDataDependencies("gyradius")
            self.setXLabel("Configuration index")
            self.setYLabel("Gyration radius")

            self.slider = Slider(
                hasEditBox=True, label="Smoothing", nMin=1, nMax=10000
            )
            self.slider.setToolTip("Number of points in sliding average")
            self.addOption(self.slider)
            self.slider.setCallbackFunc(self.updateSmoothing)

        def updateSmoothing(self, value):
            self.smoothing = value
            self.visualRefresh(force=True, noAutoRange=True)

        def addPlots(self):
            smoothing = self.smoothing
            for data in self.getWatchedData():
                err = data["dataEntry"].get("gyradius")
                err = np.convolve(
                    err, np.ones(smoothing) / smoothing, mode="valid"
                )
                self.plot(
                    np.arange(err.shape[0]),
                    np.abs(err),
                    autoColor=data,
                    autoLabel=data,
                )

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange
            return np.arange(
                max(0, int(x0 + self.smoothing)),
                min(N, int(x1 + self.smoothing)),
            )

    class GyradiusEnergyPlot(BasicPlotWidget):
        smoothing = 1

        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Gyradius & Energy Timeline",
                name="Gyradius & Energy Timeline",
                isSubbable=True,
                **kwargs,
            )
            self.setDataDependencies("gyradius")
            self.setXLabel("Configuration index")
            self.setYLabel("Gyradius/Energy (Normalised)")

            self.slider = Slider(
                hasEditBox=True, label="Smoothing", nMin=1, nMax=10000
            )
            self.slider.setToolTip("Number of points in sliding average")
            self.addOption(self.slider)
            self.slider.setCallbackFunc(self.updateSmoothing)

        def updateSmoothing(self, value):
            self.smoothing = value
            self.visualRefresh(force=True, noAutoRange=True)

        def addPlots(self):
            for data in self.getWatchedData():
                de = data["dataEntry"]

                self._addPlot(
                    de.get("gyradius"),
                    autoLabel=data,
                    autoColor=data,
                    label="Gyradius __NAME__",
                )
                self._addPlot(
                    data["dataset"].getEnergies(),
                    autoLabel=data,
                    label="Energy __NAME__",
                )

        def _addPlot(self, y, **kwargs):
            smoothing = self.smoothing

            y = np.convolve(y, np.ones(smoothing) / smoothing, mode="valid")
            y -= np.min(y)
            y /= np.max(y)
            self.plot(np.arange(y.shape[0]), np.abs(y), **kwargs)

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange
            return np.arange(
                max(0, int(x0 + self.smoothing)),
                min(N, int(x1 + self.smoothing)),
            )

    class GyradiusEnergyErrorPlot(BasicPlotWidget):
        smoothing = 1

        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Gyradius & Forces MAE Timeline",
                name="Gyradius & Forces MAE Timeline",
                isSubbable=True,
                **kwargs,
            )
            self.setDataDependencies("gyradius", "forcesError")
            self.setXLabel("Configuration index")
            self.setYLabel("Gyradius/Forces MAE (Normalised)")

            self.slider = Slider(
                hasEditBox=True, label="Smoothing", nMin=1, nMax=10000
            )
            self.slider.setToolTip("Number of points in sliding average")
            self.addOption(self.slider)
            self.slider.setCallbackFunc(self.updateSmoothing)

        def updateSmoothing(self, value):
            self.smoothing = value
            self.visualRefresh(force=True, noAutoRange=True)

        def addPlots(self):
            smoothing = self.smoothing
            for data in self.getWatchedData():
                de = data["dataEntry"]

                label = "Gyradius __NAME__"
                if data["dataTypeKey"] == "gyradius":
                    y = de.get("gyradius")
                else:
                    label = "Energy MAE __NAME__"
                    y = np.abs(de.get("diff"))

                y = np.convolve(
                    y, np.ones(smoothing) / smoothing, mode="valid"
                )
                y -= np.min(y)
                y /= np.max(y)
                self.plot(
                    np.arange(y.shape[0]),
                    np.abs(y),
                    autoColor=data,
                    autoLabel=data,
                    label=label,
                )

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange
            return np.arange(
                max(0, int(x0 + self.smoothing)),
                min(N, int(x1 + self.smoothing)),
            )

    # PLOTS
    class GyradiusDistPlot(BasicPlotWidget):
        def __init__(self, handler, **kwargs):
            super().__init__(
                handler,
                title="Gyradius distribution",
                isSubbable=True,
                name="Gyradius Distribution",
                **kwargs,
            )
            self.setDataDependencies("gyradiusDist")
            self.setXLabel("Gyradius")
            self.setYLabel("Density")

        def addPlots(self):
            for data in self.getWatchedData():
                de = data["dataEntry"]
                x, y = de.get("distX"), de.get("distY")
                self.plot(x, y, autoColor=data, autoLabel=data)

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange

            data = env.getData("gyradius", dataset=dataset)
            gyr = data.get("gyradius")

            idxs = np.argwhere((gyr >= x0) & (gyr <= x1))
            idxs = np.unique(idxs)

            return idxs

    plt = GyradiusPlot(UIHandler, parent=ct)
    ct.addWidget(plt, 0, 0)
    ct.addDataSelectionCallback(plt.setModelDatasetDependencies)

    plt = GyradiusEnergyPlot(UIHandler, parent=ct)
    ct.addWidget(plt, 0, 1)
    ct.addDataSelectionCallback(plt.setModelDatasetDependencies)

    plt = GyradiusDistPlot(UIHandler, parent=ct)
    ct.addWidget(plt, 1, 0)
    ct.addDataSelectionCallback(plt.setModelDatasetDependencies)

    plt = GyradiusEnergyErrorPlot(UIHandler, parent=ct)
    ct.addWidget(plt, 1, 1)
    ct.addDataSelectionCallback(plt.setModelDatasetDependencies)
