from PySide6.QtWidgets import (
    QComboBox,
    QStyledItemDelegate,
    QCheckBox,
    QTextEdit,
    QToolButton,
    QPushButton,
)
from PySide6.QtCore import QEvent, Qt, QEvent
from PySide6.QtGui import QPalette, QStandardItem, QFontMetrics
from PySide6 import QtCore, QtGui
from events import EventChildClass
import os


# https://www.geeksforgeeks.org/pyqt5-adding-action-to-combobox-with-checkable-items/
# new check-able combo box
class CheckableComboBox(QComboBox):

    # constructor
    def __init__(self, parent=None):
        super(CheckableComboBox, self).__init__(parent)
        self.view().pressed.connect(self.handleItemPressed)
        self.setModel(QtGui.QStandardItemModel(self))
        self.setMinimumWidth(150)
        self.selectedKeys = set()

        self.setEditable(True)  # creates a linedit, allows us to change text
        self.lineEdit().setReadOnly(True)
        # linedit is later made readonly

        self.view().viewport().installEventFilter(self)

    count = 0
    cbKeys = []

    def eventFilter(self, widget, event):
        # prevents closing of the window
        if event.type() == QEvent.MouseButtonRelease:
            return True
        return super().eventFilter(widget, event)

    # when any item get pressed
    def handleItemPressed(self, index):

        index = index.row()
        key = self.cbKeys[index]

        if key in self.selectedKeys:
            self.selectedKeys.remove(key)
        else:
            self.selectedKeys.add(key)

        self.checkData()

    def addItemsAndKeys(self, items, keys):
        self.addItems(items)
        self.cbKeys = keys
        self.updateText()

    def checkData(self):
        model = self.model()

        for i in range(model.rowCount()):
            item = model.itemFromIndex(model.index(i, 0))
            key = self.cbKeys[i]
            if item is None:
                return
            if key in self.selectedKeys:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

        self.updateText()

    def updateText(self):
        self.lineEdit().setText(self.getDisplayText())

    def getDisplayText(self):
        return "?"

    def getSelection(self):
        sel = list(self.selectedKeys)
        return [x for x in sel if x in self.cbKeys] # account for deleted elements


class DatasetModelSelector(CheckableComboBox, EventChildClass):
    def __init__(self, handler, typ="dataset", *args, **kwargs):
        CheckableComboBox.__init__(self)
        EventChildClass.__init__(self)

        self.handler = handler
        self.handler.addEventChild(self)

        self.callbacks = []

        self.model().dataChanged.connect(self.updateSelection)
        self.eventSubscribe("DATASET_LOADED", self.refreshList)
        self.eventSubscribe("DATASET_STATE_CHANGED", self.refreshList)
        self.eventSubscribe("MODEL_LOADED", self.refreshList)
        self.eventSubscribe("DATASET_DELETED", self.refreshList)
        self.eventSubscribe("MODEL_DELETED", self.refreshList)


        if typ == "dataset":
            self.eventSubscribe("DATASET_NAME_CHANGED", self.refreshList)

        elif typ == "model":
            self.eventSubscribe("MODEL_NAME_CHANGED", self.refreshList)

        else:
            logger.exception(
                f"Initialised DatasetModelSelector but type {typ} is not recognised. Needs to be dataset or model."
            )

        self.type = typ

    updateCallback = None

    def updateSelection(self):
        sel = self.getSelection()
        self.updateCallback(sel)

    def updateCallback(self, sel):
        for func in self.callbacks:
            func(sel)

    def addUpdateCallback(self, func):
        self.callbacks.append(func)

    def refreshList(self, *args):
        self.clear()

        if self.type == "dataset":
            datasets = self.handler.env.getAllDatasets()
            names = [x.getDisplayName() for x in datasets]
            keys = [x.fingerprint for x in datasets]
            self.addItemsAndKeys(names, keys)

        if self.type == "model":
            models = self.handler.env.getAllModels()
            names = [x.getDisplayName() for x in models]
            keys = [x.fingerprint for x in models]
            self.addItemsAndKeys(names, keys)

        self.checkData()
        self.updateText()

    def getDisplayText(self):
        sel = self.getSelection()
        N = len(sel)

        if N == 0:
            return f"Select {self.type}s"
        elif N < 2:
            return f"1 {self.type}"
        else:
            return f"{N} {self.type}s"


class DatasetModelComboBox(EventChildClass, QComboBox):
    def __init__(self, handler, typ="dataset"):
        self.handler = handler
        super().__init__()
        self.handler.addEventChild(self)

        self.eventSubscribe("DATASET_LOADED", self.refreshList)
        self.eventSubscribe("DATASET_STATE_CHANGED", self.refreshList)
        self.eventSubscribe("MODEL_LOADED", self.refreshList)
        self.callbacks = []
        self.currentIndexChanged.connect(self.updateSelection)

        if typ == "dataset":
            self.eventSubscribe("DATASET_NAME_CHANGED", self.refreshList)

        elif typ == "model":
            self.eventSubscribe("MODEL_NAME_CHANGED", self.refreshList)

        else:
            logger.exception(
                f"Initialised DatasetModelSelector but type {typ} is not recognised. Needs to be dataset or model."
            )

        self.type = typ
        self.refreshList()

    keys = None

    def currentKey(self):
        if self.keys is None:
            return []
        idx = self.currentIndex()
        if (idx == -1) or (idx is None) or (idx >= len(self.keys)):
            return []
        return [self.keys[idx]]

    def refreshList(self, *args):
        sel = self.currentKey()
        self.clear()

        if self.type == "dataset":
            datasets = self.handler.env.getAllDatasets()
            names = [x.getDisplayName() for x in datasets]
            self.keys = [x.fingerprint for x in datasets]
            self.addItems(names)

        if self.type == "model":
            models = self.handler.env.getAllModels()
            names = [x.getDisplayName() for x in models]
            self.keys = [x.fingerprint for x in models]
            self.addItems(names)

        if sel in self.keys:
            idx = self.keys.index(sel)
        else:
            idx = 0
        self.setCurrentIndex(idx)

    def updateCallback(self, sel):
        for func in self.callbacks:
            func(sel)

    def addUpdateCallback(self, func):
        self.callbacks.append(func)

    def updateSelection(self):
        sel = self.currentKey()
        self.updateCallback(sel)


class CodeTextEdit(QTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.installEventFilter(self)

    returnCallback = None

    def setReturnCallback(self, func):
        self.returnCallback = func

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            if event.modifiers() == Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.clearFocus()
                if self.returnCallback is not None:
                    self.returnCallback()
        else:
            super().keyPressEvent(event)


class DataLoaderButton(EventChildClass, QPushButton):
    def __init__(self, handler, watcher):
        super().__init__()
        self.handler = handler
        self.handler.addEventChild(self)
        self.dataWatcher = watcher

        self.setText("Load")
        self.clicked.connect(self.dataWatcher.loadContent)

        self.dataWatcher.addRefreshWidget(self)
        self.eventSubscribe("WIDGET_REFRESH", self.onWidgetRefresh)

        self.onWidgetRefresh(self)

    def onWidgetRefresh(self, widget):
        if self is not widget:
            return
        missing = self.dataWatcher.currentlyMissingKeys
        if len(missing) == 0:
            self.setEnabled(False)
        else:
            self.setEnabled(True)


def getIcon(name):
    if not name.endswith(".sgv"):
        name = name + ".svg"

    path = os.path.join("theme", "primary", name)
    return QtGui.QIcon(path)


class CollapseButton(QToolButton):
    def __init__(self, handler, frame, direction, defaultCollapsed=True):
        super().__init__()
        self.dir = direction
        self.frame = frame
        self.handler = handler

        if direction not in ["left", "right", "up", "down"]:
            raise ValueError(f"Collapse button direction {direction} invalid")

        self.clicked.connect(self.click)

        if direction == "left":
            self.collapsedIcon = getIcon("downarrow")
            self.expandedIcon = getIcon("leftarrow")
        elif direction == "right":
            self.collapsedIcon = getIcon("downarrow")
            self.expandedIcon = getIcon("rightarrow")
        elif direction == "up":
            self.collapsedIcon = getIcon("rightarrow")
            self.expandedIcon = getIcon("uparrow")
        elif direction == "down":
            self.collapsedIcon = getIcon("rightarrow")
            self.expandedIcon = getIcon("downarrow")

        if defaultCollapsed:
            self.setCollapsed()
        else:
            self.setExpanded()

        self.setConfig()

    collapsed = False

    def setConfig(self):
        sheet = """
            QToolButton,
            QToolButton:pressed,
            QToolButton:checked{
                border: 0px solid @HLColor1;
            }
        """

        self.setStyleSheet(self.handler.applyConfigToStyleSheet(sheet))

    def click(self, _):
        if self.collapsed:
            self.setExpanded()
        else:
            self.setCollapsed()

    def setExpanded(self):
        if (self.dir == "left") or (self.dir == "right"):
            self.frame.show()
        else:
            self.frame.show()

        self.setIcon(self.expandedIcon)
        self.collapsed = False

    def setCollapsed(self):
        if (self.dir == "left") or (self.dir == "right"):
            self.frame.hide()
            # self.frame.setMaximumWidth(0)
        else:
            self.frame.hide()
            # self.frame.setMaximumHeight(0)

        self.setIcon(self.collapsedIcon)
        self.collapsed = True
