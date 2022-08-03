import numpy as np
from UI.plots import BasicPlotContainer
from UI.tab import Tab
import logging
import pyqtgraph as pg
import math

logger = logging.getLogger("FFAST")

# TODO refactor some of this, there should be no need to rewrite this much
# especially since getDatasetSubIndices is (almost) completely generic here

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

            fPred = np.mean(
                np.absolute(fPred.reshape(fPred.shape[0], -1)), axis=1
            )
            fTrue = np.mean(
                np.absolute(fTrue.reshape(fTrue.shape[0], -1)), axis=1
            )
            self.plot(fTrue, fPred, pen=None, symbol="o")

    def getDatasetSubIndices(self, dataset, model):
        xRange, yRange = self.getRanges()
        N = dataset.getN()
        x0, x1 = xRange
        y0, y1 = yRange

        fTrue = dataset.getForces()
        fPred = self.env.getData("forces", dataset=dataset,model=model).get()

        fPred = np.mean(
            np.absolute(fPred.reshape(fPred.shape[0], -1)), axis=1
        )
        fTrue = np.mean(
            np.absolute(fTrue.reshape(fTrue.shape[0], -1)), axis=1
        )


        xTruth = (fTrue > x0) & (fTrue < x1)
        yTruth = (fPred > y0) & (fPred < y1)
        return np.argwhere(xTruth & yTruth).flatten()

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

            self.plot(eTrue, ePred, pen=None, symbol="o")

    def getDatasetSubIndices(self, dataset, model):
        xRange, yRange = self.getRanges()
        N = dataset.getN()
        x0, x1 = xRange
        y0, y1 = yRange

        eTrue = dataset.getEnergies()
        ePred = self.env.getData("energy", dataset=dataset,model=model).get()

        xTruth = (eTrue > x0) & (eTrue < x1)
        yTruth = (ePred > y0) & (ePred < y1)
        return np.argwhere(xTruth & yTruth).flatten()

def load(UIHandler, env):
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
