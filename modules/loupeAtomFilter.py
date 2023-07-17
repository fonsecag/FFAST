import logging
from UI.loupeProperties import AtomSelectionBase, CanvasProperty
from functools import partial
import numpy as np

logger = logging.getLogger("FFAST")


class AtomFilterSelect(AtomSelectionBase):
    multiselect = 10000
    rectangleSelect = True
    label = "Atom Filter Selection"

    def __init__(self, canvas, **kwargs):
        super().__init__(canvas, **kwargs)

        indices = canvas.settings.get("atomFilterIndices")
        if indices is not None:
            self.selectedPoints = list.copy(indices)
            canvas.visualRefresh(force=True)

    def selectCallback(self):
        loupe = self.canvas.loupe
        # sending a copy is important, otherwise the code block never
        # updates, since it thinks it hasnt changed
        loupe.settings.setParameter(
            "atomFilterIndices", list.copy(self.selectedPoints), refresh=True
        )


class AtomFilterPaneHiding(CanvasProperty):

    key = "atomFilterPaneHiding"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def onDatasetInit(self):
        loupe = self.canvas.loupe
        dataset = loupe.getSelectedDataset()

        loupe.setSettingsPaneVisibility(
            "ATOM FILTER", not dataset.isSubDataset
        )


def addSetting(UIHandler, loupe):
    def updateSelection(loupe):
        canvas = loupe.canvas
        if not canvas.isActiveAtomSelectTool(AtomFilterSelect):
            return

        tool = canvas.activeAtomSelectTool
        atoms = canvas.settings.get("atomFilterIndices")
        if atoms != tool.selectedPoints:
            tool.selectedPoints = list.copy(atoms)
            canvas.visualRefresh(force=True)

    # add dummy setting where the indices are saved
    settings = loupe.settings
    settings.addParameters(
        **{
            "atomFilterIndices": [
                [],
                partial(updateSelection, loupe),
                "visualRefresh",
            ]
        }
    )


def addSettingsPane(UIHandler, loupe):
    from UI.Templates import SettingsPane, PushButton, Label

    pane = SettingsPane(UIHandler, loupe.settings, parent=loupe)
    loupe.addSidebarPane("ATOM FILTER", pane)

    def cleanIndices(arr):
        dataset = loupe.getSelectedDataset()
        if dataset is None:
            return True, []
        try:
            nA = dataset.getNAtoms()
            zStr = dataset.getElementsName()
            lst = []
            removes = []

            for x in arr:
                if isinstance(x, str):
                    isNeg = x.startswith("-")
                    if isNeg:
                        x = x.replace("-", "")
                    x = x.strip()
                    idxs = [i for i in range(len(zStr)) if zStr[i] == x]
                    if isNeg:
                        removes += idxs
                    else:
                        lst += idxs

                else:
                    lst.append(int(x))

            # check if it contains any strings
            s = set(lst) - set(removes)

        except Exception as e:
            logger.exception(
                f"Tried to clean indices arr, but failed for: {e}. Array/List needs contain dinstinct integers"
            )
            return False, None

        return True, list(s)

    pane.addSetting(
        "CodeBox",
        "Indices",
        settingsKey="atomFilterIndices",
        validationFunc=cleanIndices,
        labelDirection="horizontal",
        singleLine=False,
        toolTip='Python list of indices. "Z" to include all elements Z. "-Z" to remove them',
    )

    ## ADD BONDS BUTTONS
    container = pane.addSetting(
        "Container", "Atom Filter Indices Container", layout="horizontal"
    )

    # SELECT ATOMS BTN
    def selectAtoms():
        loupe.setActiveAtomSelectTool(AtomFilterSelect)

    selectButton = PushButton("Select")
    selectButton.setToolTip(
        "Click to manually add/remove indices in the atom filter. Hold CMD/CTRL to create selection rectangle."
    )
    selectButton.clicked.connect(selectAtoms)
    container.layout.addWidget(selectButton)

    # CREATE ATOM FILTERED DATASET BTB
    def createAtomFilteredDataset():
        idxs = loupe.settings.get("atomFilterIndices")
        dataset = loupe.getSelectedDataset()

        if dataset is None:
            return

        if (idxs is None) or len(idxs) == 0:
            return

        UIHandler.env.createAtomFilteredDataset(dataset, idxs)

    createButton = PushButton("Create")
    createButton.setToolTip(
        "Create an atom-filtered dataset with only the current atom indices"
    )
    createButton.clicked.connect(createAtomFilteredDataset)
    container.layout.addWidget(createButton)

    # ADD A PROPERTY TO CONTROL THE SHOWING/HIDING OF THE PANE
    # Pane should not be visible if the selected dataset is a subdataset/atomfitlered
    loupe.addCanvasProperty(AtomFilterPaneHiding)


def loadLoupe(UIHandler, loupe):
    addSetting(UIHandler, loupe)
    addSettingsPane(UIHandler, loupe)
