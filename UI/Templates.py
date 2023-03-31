from PySide6 import QtCore, QtGui, QtWidgets
from config.uiConfig import config, configStyleSheet
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QWidget, QTabWidget
from config.uiConfig import config, getIcon
from PySide6.QtWidgets import QSizePolicy
import pyqtgraph
import logging
from Utils.misc import rgbToHex

WIDGET_ID = 0
logger = logging.getLogger("FFAST")


class Widget(QWidget):

    frozen = False  # sometimes used to prevent callbacks while frozen
    deleted = False

    def __init__(
        self, layout=None, color=None, parent=None, frozen=False, styleSheet=""
    ):
        super().__init__(parent=parent)
        self.frozen = frozen
        if parent is None:
            logger.warn(f"Parent not being set for widget {self}")

        self.applyDefaultName()
        self.applyDefaultLayout(layout=layout)
        self.applyDefaultStyleSheet(color=color, styleSheet=styleSheet)

    def applyDefaultName(self):
        global WIDGET_ID
        self.id = WIDGET_ID
        self.objectName = f"WIDGET_{self.id}"
        WIDGET_ID += 1
        self.setObjectName(self.objectName)

    def applyDefaultLayout(self, layout=None):
        if layout is None:
            return

        if layout == "vertical":
            self.layout = QtWidgets.QVBoxLayout()
        elif layout == "horizontal":
            self.layout = QtWidgets.QHBoxLayout()
        elif layout == "grid":
            self.layout = QtWidgets.QGridLayout()
        elif layout is not None:
            logger.error(
                f"Layout given to {self} but type {layout} not recognised"
            )

        self.setLayout(self.layout)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

    def applyDefaultStyleSheet(self, color=None, styleSheet=""):
        ss = styleSheet
        if color is not None:
            self.setAttribute(Qt.WA_StyledBackground, True)
            ss = ss + f"@OBJECT{{background-color:{color};}}"

        ss = ss.replace("@OBJECT", f"QWidget#{self.objectName}")

        self.setStyleSheet(configStyleSheet(ss))

    def freeze(self):
        self.frozen = True

    def unfreeze(self):
        self.frozen = False

    def setDeleted(self):
        self.deleted = True
        self.deleteLater()
        if hasattr(self, "isEventChild") and self.isEventChild:
            self.deleteEvents()


class TabWidget(QTabWidget):
    def __init__(self, parent=None, color=None, styleSheet=""):
        super().__init__(parent=parent)

        Widget.applyDefaultName(self)
        Widget.applyDefaultStyleSheet(self, color=color, styleSheet=styleSheet)


class PushButton(QtWidgets.QPushButton):
    def __init__(self, text, parent=None, color=None, styleSheet=""):
        super().__init__(text, parent=parent)

        Widget.applyDefaultName(self)
        Widget.applyDefaultStyleSheet(self, color=color, styleSheet=styleSheet)


class WidgetButton(Widget):

    checked = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setProperty("checked", False)

    def setOnClick(self, func):
        self.updateFunc = func

    def mousePressEvent(self, event):
        self.setChecked(not self.checked)

    def setChecked(self, checked, quiet=False):
        self.checked = checked

        if not quiet:
            self.updateFunc()

        # https://wiki.qt.io/Dynamic_Properties_and_Stylesheets
        self.setProperty("checked", checked)
        self.style().unpolish(self)
        self.style().polish(self)

    def updateFunc(*args, **kwargs):
        pass


class ToolCheckButton(QtWidgets.QToolButton):
    checked = False

    def __init__(self, handler, func, icon="default", **kwargs):
        super().__init__(**kwargs)
        self.handler = handler
        self.func = func
        icon = getIcon(icon)
        self.setIcon(QtGui.QIcon(icon))

        self.clicked.connect(self.onClicked)
        self.setCheckable(True)

    def onClicked(self):
        self.setChecked(not self.isChecked())

    def setChecked(self, checked):
        if self.checked == checked:
            return

        self.checked = checked
        self.onStateChanged()

        self.setChecked(checked)

    def isChecked(self):
        return self.checked

    def onStateChanged(self):
        self.func()


class ToolButton(QtWidgets.QToolButton):
    def __init__(self, handler, func, icon="default", **kwargs):
        super().__init__(**kwargs)
        self.handler = handler
        self.clicked.connect(func)
        icon = getIcon(icon)
        self.setIcon(QtGui.QIcon(icon))


class ExpandingScrollArea(QtWidgets.QScrollArea):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setWidgetResizable(True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.setMaximumHeight(0)
        self.setMinimumHeight(0)

    contentWidget = None

    def setContent(self, widget):
        self.setWidget(widget)
        widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.contentWidget = widget
        self.setMaximumHeight(16777215)

    def sizeHint(self):
        h = 0
        if self.contentWidget is not None:
            h = self.contentWidget.height()
        return QtCore.QSize(super().sizeHint().width(), h)


class CollapseButton(QtWidgets.QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("collapseButton")
        self.setIcon(QtGui.QIcon(getIcon("expanded")))
        self.clicked.connect(self.onClick)

    collapsingWidget = None

    def setCollapsingWidget(self, widget):
        self.collapsingWidget = widget
        self.updateIcon()

    def updateIcon(self):
        if self.collapsingWidget.isVisible():
            self.setIcon(QtGui.QIcon(getIcon("expanded")))
        else:
            self.setIcon(QtGui.QIcon(getIcon("collapsed")))

    def onClick(self):
        if self.isExpanded():
            self.setCollapsed()
        else:
            self.setExpanded()

    def setCollapsed(self):
        self.collapsingWidget.hide()
        self.updateIcon()
        self.updateSize()

    def setExpanded(self):
        self.collapsingWidget.show()
        self.updateIcon()
        self.updateSize()

    def isExpanded(self):
        return self.collapsingWidget.isVisible()

    def updateSize(self):
        w = self
        while w.parentWidget() is not None:
            w = w.parentWidget()
            if isinstance(w, CollapsibleWidget):
                # idk why this is needed, but it is
                # otherwise things just dont update properly
                # also, only .adjustSize is also not good enough for some reason
                w.forceUpdateLayout()


class CollapsibleWidget(Widget):
    def __init__(
        self, handler, name="N/A", titleHeight=25, widget=None, **kwargs
    ):
        super().__init__(layout="vertical", **kwargs)
        self.handler = handler
        self.titleHeight = titleHeight

        # make title button
        self.titleButton = CollapseButton(name)
        self.titleButton.setFixedHeight(self.titleHeight)

        self.layout.addWidget(self.titleButton)

        if widget is None:
            self.scrollWidget = Widget(layout="vertical")
            self.scrollLayout = self.scrollWidget.layout
        else:
            self.scrollWidget = widget

        self.scrollArea = ExpandingScrollArea()
        self.scrollArea.setContent(self.scrollWidget)

        self.layout.addWidget(self.scrollArea)

        self.titleButton.setCollapsingWidget(self.scrollArea)

    def sizeHint(self):
        return QtCore.QSize(
            super().sizeHint().width(), super().sizeHint().height()
        )

    def isExpanded(self):
        return self.titleButton.isExpanded()

    def setCollapsed(self):
        self.titleButton.setCollapsed()

    def setExpanded(self):
        self.titleButton.setExpanded()

    def forceUpdateLayout(self):
        QtCore.QTimer.singleShot(0, self._forceUpdateLayout)

    def _forceUpdateLayout(self):
        self.scrollArea.setMaximumHeight(10)
        self.scrollArea.setMaximumHeight(100000)
        self.scrollWidget.setMaximumHeight(10)
        self.scrollWidget.setMaximumHeight(100000)

        self.scrollArea.adjustSize()
        self.scrollWidget.adjustSize()


class ContentBar(Widget):
    def __init__(self, handler, **kwargs):
        super().__init__(color="@BGColor1", **kwargs)
        self.handler = handler

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        self.setFixedWidth(300)
        self.layout.addStretch()

    def addContent(self, name, widget=None):
        content = CollapsibleWidget(
            self.handler, name=name, widget=widget, parent=self
        )
        self.layout.insertWidget(self.layout.count() - 1, content)


class ObjectListItem(Widget):
    def __init__(self, handler, id, color=None, layout="vertical", **kwargs):
        super().__init__(color=color, layout=layout, **kwargs)
        self.handler = handler
        self.id = id


class ObjectList(Widget):
    def __init__(self, handler, widgetType, color=None, **kwargs):
        super().__init__(color=color, layout="vertical", **kwargs)
        self.handler = handler
        self.widgetType = widgetType
        self.widgets = {}
        self.layout.setSpacing(2)

    def newObject(self, id, **kwargs):
        if id in self.widgets:
            logger.error(
                f"ID {id} already exists for ObjectList {self} and widgetType {self.widgetType}."
            )
            return
        w = self.widgetType(self.handler, id, parent=self, **kwargs)
        self.widgets[id] = w
        self.layout.addWidget(w)

    def getWidget(self, id):
        return self.widgets.get(id, None)

    def removeObject(self, id):
        w = self.getWidget(id)
        if w is None:
            return

        self.layout.removeWidget(w)
        w.deleteLater()

        # force udpate parents if they're collapsible scrollareas
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, CollapsibleWidget):
                parent.forceUpdateLayout()
                break
            parent = parent.parent()


class InfoWidget(Widget):
    nRows = 0
    styleSheet = '''
        QLabel#LeftLabel{
            font-weight: bold;
        }
        QLabel{
            qproperty-alignment: AlignLeft;
        }
        """
    '''

    def __init__(self, **kwargs):
        super().__init__(**kwargs, styleSheet=self.styleSheet)
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

    def setInfo(self, *args):
        # ADD LABELS
        nRows = len(args)
        for i in range(self.nRows, nRows):
            labelLeft = QtWidgets.QLabel("")
            labelLeft.setObjectName("LeftLabel")
            self.layout.addWidget(labelLeft, i, 0)

            labelRight = QtWidgets.QLabel("")
            labelRight.setObjectName("RightLabel")
            self.layout.addWidget(labelRight, i, 1)

        # REMOVE LABELS
        for i in range(nRows, self.nRows):
            labelLeft = self.layout.itemAtPosition(i, 0)
            self.layout.removeWidget(labelLeft.widget())

            labelRight = self.layout.itemAtPosition(i, 1)
            self.layout.removeWidget(labelRight.widget())

        for i in range(nRows):
            sLeft, sRight = args[i]

            labelLeft = self.layout.itemAtPosition(i, 0).widget()
            labelRight = self.layout.itemAtPosition(i, 1).widget()

            labelLeft.setText(sLeft)
            labelRight.setText(sRight)

        self.nRows = nRows


class FlexibleHList(Widget):

    currentNElementsPerRow = 0
    needsReadjusting = False

    def __init__(self, elementSize=150, **kwargs):
        super().__init__(layout="horizontal", **kwargs)
        self.gridWidget = Widget(layout="grid")
        self.gridWidget.layout.setSpacing(5)
        self.spacerWidget = Widget()
        self.gridLayout = self.gridWidget.layout

        self.gridWidget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )

        self.spacerWidget.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Ignored
        )

        self.layout.addWidget(self.gridWidget)
        self.layout.addWidget(self.spacerWidget)
        self.elementSize = elementSize
        self.widgets = []

        # self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def resizeEvent(self, event):
        if self.frozen:
            return

        if self.needsReadjusting:
            self.updateMaximumWidth()
            self.adjustLayout()

        elif self.nElementsPerRow() != self.currentNElementsPerRow:
            self.adjustLayout()

        QWidget.resizeEvent(self, event)

    def adjustLayout(self):
        self.removeWidgets()
        self.readdWidgets()
        self.currentNElementsPerRow = self.nElementsPerRow()
        self.needsReadjusting = False

    def removeWidgets(self, clear=False):
        for w in self.widgets:
            self.gridLayout.removeWidget(w)

        if clear:
            for w in self.widgets:
                w.setDeleted()
            self.widgets = []

    def nElementsPerRow(self):
        return self.width() // self.elementSize

    def indexToGridIndices(self, index):
        nelpr = self.nElementsPerRow()
        if nelpr == 0:
            return None, None
        return divmod(index, self.nElementsPerRow())

    def readdWidgets(self):
        for iw in range(len(self.widgets)):
            w = self.widgets[iw]
            i, j = self.indexToGridIndices(iw)
            if i is None:
                continue
            self.gridLayout.addWidget(w, i, j)

    def addWidget(self, w):
        index = len(self.widgets)
        i, j = self.indexToGridIndices(index)

        self.widgets.append(w)
        w.setMaximumWidth(self.elementSize)

        if i is None:
            self.needsReadjusting = True
            return

        self.gridLayout.addWidget(w, i, j)
        self.updateMaximumWidth()

    def updateMaximumWidth(self):
        self.gridWidget.setMaximumWidth(len(self.widgets) * self.elementSize)


class ListCheckButton(WidgetButton):
    colorCircleStyleSheet = """
        background-color: @COLOR;
        border-radius: 10;
    """
    styleSheet = """
        @OBJECT{border-radius:9px;}
        @OBJECT:hover{background-color:@BGColor4}
        @OBJECT[checked=true]{background-color:@BGColor4}
        @OBJECT[checked=true]:hover{background-color:@BGColor5}
    """

    def __init__(self, *args, label="N/A", color=(255, 255, 255), **kwargs):
        super().__init__(
            *args,
            layout="horizontal",
            color="transparent",
            styleSheet=self.styleSheet,
            **kwargs,
        )

        self.name = label
        self.color = color

        self.colorCircle = Widget(parent=self, color="transparent")
        self.colorCircle.setFixedHeight(20)
        self.colorCircle.setFixedWidth(20)

        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(5)

        self.label = QtWidgets.QLabel("?", parent=self)
        self.label.setFixedHeight(20)

        self.layout.addWidget(self.colorCircle)
        self.layout.addWidget(self.label)

        self.applyStyle()
        self.setOnClick(self.updateParent)

    def applyStyle(self):
        ss = self.colorCircleStyleSheet.replace(
            "@COLOR", rgbToHex(*self.getColor())
        )
        self.colorCircle.setStyleSheet(configStyleSheet(ss))

        self.label.setText(self.getLabel())

    def getColor(self):
        return self.color

    def getLabel(self):
        return self.name

    def updateParent(self):
        self.parent.update(self)


class FlexibleListSelector(Widget):
    def __init__(
        self,
        *args,
        elementSize=150,
        label=None,
        singleSelection=False,
        **kwargs,
    ):
        super().__init__(*args, layout="horizontal", **kwargs)

        self.singleSelection = singleSelection

        if label is not None:
            self.label = QtWidgets.QLabel(parent=self)
            self.label.setText(label)
            self.layout.addWidget(self.label)
            self.label.setFixedWidth(120)
            self.label.setObjectName("titleLabel")

        self.list = FlexibleHList(elementSize=elementSize, parent=self)
        self.layout.addWidget(self.list)

    def removeWidgets(self, **kwargs):
        return self.list.removeWidgets(**kwargs)

    def addWidget(self, w, *args, **kwargs):
        w.parent = self
        return self.list.addWidget(w, *args, **kwargs)

    def getWidgets(self):
        return self.list.widgets

    def getSelectedWidgets(self):
        return [w for w in self.getWidgets() if w.checked]

    def setOnUpdate(self, func):
        self.updateFunc = func

    def update(self, widget):

        if self.singleSelection and len(self.getSelectedWidgets()) > 1:
            for w in self.getWidgets():
                if w is widget:
                    continue
                if w.checked:
                    w.setChecked(False, quiet=True)

        self.updateFunc()

    def removeWidgets(self, *args, **kwargs):
        return self.list.removeWidgets(*args, **kwargs)
