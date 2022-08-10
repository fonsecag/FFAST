from PySide6.QtWidgets import (
    QComboBox,
    QStyledItemDelegate,
    QCheckBox,
    QTextEdit,
    QToolButton,
    QPushButton,
)
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QPalette, QStandardItem, QFontMetrics
from PySide6 import QtCore, QtGui
from events import EventWidgetClass
import os


# slightly altered from:
# https://gis.stackexchange.com/questions/350148/qcombobox-multiple-selection-pyqt5
class CheckableComboBox(QComboBox):

    # Subclass Delegate to increase item height
    class Delegate(QStyledItemDelegate):
        def sizeHint(self, option, index):
            size = super().sizeHint(option, index)
            size.setHeight(20)
            return size

    def __init__(self, *args, text=None, singleSelect=False, **kwargs):
        super().__init__(*args, **kwargs)

        self.singleSelect = singleSelect

        # Make the combo editable to set a custom text, but readonly
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        # Make the lineedit the same color as QPushButton
        palette = qApp.palette()
        palette.setBrush(QPalette.Base, palette.button())
        self.lineEdit().setPalette(palette)

        # Use custom delegate
        self.setItemDelegate(CheckableComboBox.Delegate())

        # Update the text when an item is toggled
        self.model().dataChanged.connect(self.updateText)

        # self.activated.connect(self.onActivated)
        if singleSelect:
            self.highlighted.connect(self.onHighlight)

        # Hide and show popup when clicking the line edit
        self.lineEdit().installEventFilter(self)
        self.closeOnLineEditClick = False

        # Prevent popup from closing when clicking on an item
        self.view().viewport().installEventFilter(self)

        self.text = text
        if text is not None:
            fontMetric = self.fontMetrics()
            w = fontMetric.horizontalAdvance(text)
            self.setWidth(w + 50)  # +X for space for the arrow thing
            self.setFixedWidth(self.fixedWidth)

    lastHighlightedIndex = -1

    def onHighlight(self, index):
        self.lastHighlightedIndex = index

    def resizeEvent(self, event):
        # Recompute text to elide as needed
        self.updateText()
        super().resizeEvent(event)
        if self.fixedWidth is not None:
            self.resize(self.fixedWidth, self.height())

    fixedWidth = None

    def setWidth(self, w):
        self.fixedWidth = w

    def eventFilter(self, object, event):

        if object == self.lineEdit():
            if event.type() == QEvent.MouseButtonRelease:
                if self.closeOnLineEditClick:
                    self.hidePopup()
                else:
                    self.showPopup()
                return True
            return False

        if object == self.view().viewport():
            if event.type() == QEvent.MouseButtonRelease:
                index = self.view().indexAt(event.pos())
                item = self.model().item(index.row())

                if item.checkState() == Qt.Checked:
                    item.setCheckState(Qt.Unchecked)
                else:
                    item.setCheckState(Qt.Checked)
                return True
        return False

    def showPopup(self):
        super().showPopup()
        # When the popup is displayed, a click on the lineedit should close it
        self.closeOnLineEditClick = True

    def hidePopup(self):
        super().hidePopup()
        # Used to prevent immediate reopening when clicking on the lineEdit
        self.startTimer(100)
        # Refresh the display text when closing
        self.updateText()

    def timerEvent(self, event):
        # After timeout, kill timer, and reenable click on line edit
        self.killTimer(event.timerId())
        self.closeOnLineEditClick = False

    def applySingleSelect(self):
        N = len(self.currentData())
        if N < 2:
            return

        self.uncheckData(exceptIndex=self.lastHighlightedIndex)

    def updateText(self):
        if self.singleSelect:
            self.applySingleSelect()

        if self.text is not None:
            self.lineEdit().setText(self.text)
            return

        texts = []
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == Qt.Checked:
                texts.append(self.model().item(i).text())
        text = ", ".join(texts)

        # Compute elided text (with "...")
        metrics = QFontMetrics(self.lineEdit().font())
        elidedText = metrics.elidedText(
            text, Qt.ElideRight, self.lineEdit().width()
        )
        self.lineEdit().setText(elidedText)

    def addItem(self, text, data=None):
        item = QStandardItem()
        item.setText(text)
        if data is None:
            item.setData(text)
        else:
            item.setData(data)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        item.setData(Qt.Unchecked, Qt.CheckStateRole)
        self.model().appendRow(item)

    def addItems(self, texts, datalist=None):
        for i, text in enumerate(texts):
            try:
                data = datalist[i]
            except (TypeError, IndexError):
                data = None
            self.addItem(text, data)

    def currentData(self):
        # Return the list of selected items data
        res = []
        for i in range(self.model().rowCount()):
            if self.model().item(i).checkState() == Qt.Checked:
                res.append(self.model().item(i).data())
        return res

    def uncheckData(self, exceptIndex=-1):
        for i in range(self.model().rowCount()):
            if i == exceptIndex:
                continue
            self.model().item(i).setCheckState(Qt.Unchecked)

    def checkData(self, selected):

        for i in range(self.model().rowCount()):
            if self.model().item(i).data() in selected:
                self.model().item(i).setCheckState(Qt.Checked)


class DatasetModelSelector(CheckableComboBox, EventWidgetClass):
    def __init__(self, handler, typ="dataset", *args, **kwargs):
        CheckableComboBox.__init__(self, *args, **kwargs)
        EventWidgetClass.__init__(self)

        self.handler = handler

        self.callbacks = []

        self.model().dataChanged.connect(self.updateSelection)
        self.eventSubscribe("DATASET_LOADED", self.refreshList)
        self.eventSubscribe("DATASET_STATE_CHANGED", self.refreshList)
        self.eventSubscribe("MODEL_LOADED", self.refreshList)

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

        sel = self.currentData()
        self.updateCallback(sel)

    def updateCallback(self, sel):
        for func in self.callbacks:
            func(sel)

    def addUpdateCallback(self, func):
        self.callbacks.append(func)

    def refreshList(self, *args):
        sel = self.currentData()
        self.clear()

        if self.type == "dataset":
            datasets = self.handler.env.getAllDatasets()
            names = [x.getDisplayName() for x in datasets]
            keys = [x.fingerprint for x in datasets]
            self.addItems(names, keys)

        if self.type == "model":
            models = self.handler.env.getAllModels()
            names = [x.getDisplayName() for x in models]
            keys = [x.fingerprint for x in models]
            self.addItems(names, keys)

        self.checkData(sel)
        self.updateText()

    # deprecated


class DatasetModelComboBox(QComboBox, EventWidgetClass):
    def __init__(self, handler, typ="dataset"):
        self.handler = handler
        super().__init__()

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


class DataLoaderButton(QPushButton, EventWidgetClass):
    def __init__(self, handler, watcher):
        super().__init__()
        self.handler = handler
        self.dataWatcher = watcher

        self.setText("Load")
        self.clicked.connect(self.dataWatcher.loadContent)

        self.dataWatcher.addRefreshWidget(self)
        self.eventSubscribe("WIDGET_REFRESH", self.onWidgetRefresh)

        self.onWidgetRefresh(self)

    def onWidgetRefresh(self, widget):
        print("REFRESH", widget)
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
