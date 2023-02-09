import numpy as np
import logging

logger = logging.getLogger("FFAST")


def loadData(env):
    pass


def loadUI(UIHandler, env):

    from UI.plots import BasicPlotContainer
    from UI.tab import Tab
    import pyqtgraph as pg

    class ForcesErrorScatterPlot(BasicPlotContainer):
        def __init__(self, handler, tab):
            super().__init__(
                handler,
                parentSelector=True,
                title="Forces Scatter",
                isSubbable=True,
                name="FoErrScatter",
            )
            self.setDataDependencies("forces")
            self.setXLabel("True MA Force", "kcal/mol A")
            self.setYLabel("Predicted MA Force", "kcal/mol A")

        def addPlots(self):
            for x in self.getWatchedData():
                de = x["dataEntry"]
                fPred = de.get()
                dataset = x["dataset"]
                fTrue = dataset.getForces()

                self.plot(
                    fTrue.flatten(), fPred.flatten(), scatter=True, symbol="o"
                )


        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange
            y0, y1 = yRange

            fTrue = dataset.getForces()
            fPred = self.env.getData(
                "forces", dataset=dataset, model=model
            ).get()

            fPred = fPred.flatten()
            fTrue = fTrue.flatten()

            xTruth = (fTrue > x0) & (fTrue < x1)
            yTruth = (fPred > y0) & (fPred < y1)
            args = np.argwhere(xTruth & yTruth).flatten()

            nEntriesPerConf = dataset.getNAtoms() * 3
            args = np.unique(np.floor(args / nEntriesPerConf)).astype(int)
            return args

    class EnergyErrorScatterPlot(BasicPlotContainer):
        def __init__(self, handler, tab):
            super().__init__(
                handler,
                parentSelector=True,
                title="Energy Scatter",
                isSubbable=True,
                name="EnErrScatter",
            )
            self.setDataDependencies("energy")
            self.setXLabel("True Energy", "kcal/mol")
            self.setYLabel("Predicted Energy", "kcal/mol")

        def addPlots(self):
            for x in self.getWatchedData():
                de = x["dataEntry"]
                ePred = de.get()
                dataset = x["dataset"]
                eTrue = dataset.getEnergies()

                self.plot(eTrue, ePred, scatter=True, symbol="o")
                # self.plot(eTrue, ePred, symbol = "o", pen=None)

        def getDatasetSubIndices(self, dataset, model):
            (xRange, yRange) = self.getRanges()
            N = dataset.getN()
            x0, x1 = xRange
            y0, y1 = yRange

            eTrue = dataset.getEnergies()
            ePred = self.env.getData(
                "energy", dataset=dataset, model=model
            ).get()

            xTruth = (eTrue > x0) & (eTrue < x1)
            yTruth = (ePred > y0) & (ePred < y1)
            return np.argwhere(xTruth & yTruth).flatten()

    tab = Tab(
        UIHandler,
        hasDatasetSelector=True,
        hasModelSelector=True,
        singleDataset=True,
        singleModel=True,
    )
    UIHandler.addTab(tab, "Error Scatter")

    plot = ForcesErrorScatterPlot(UIHandler, tab)
    tab.addWidget(plot, 0, 0)

    plot = EnergyErrorScatterPlot(UIHandler, tab)
    tab.addWidget(plot, 0, 1)

    tab.addBottomVerticalSpacer()
