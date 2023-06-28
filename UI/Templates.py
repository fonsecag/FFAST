from PySide6 import QtCore, QtGui, QtWidgets
from config.uiConfig import config, configStyleSheet
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QWidget, QTabWidget, QFileDialog
from config.uiConfig import config, getIcon
from PySide6.QtWidgets import QSizePolicy
import pyqtgraph
import logging
from utils import rgbToHex
from events import EventChildClass
import ast
from functools import partial
import pprint

CURRENT_WIDGET_ID = 0
logger = logging.getLogger("FFAST")


class Widget(QWidget):

    frozen = False  # sometimes used to prevent callbacks while frozen
    deleted = False

    def __init__(
        self,
        layout=None,
        color=None,
        parent=None,
        frozen=False,
        styleSheet="",
        widgetName=None,
    ):
        super().__init__(parent=parent)
        self.frozen = frozen
        if parent is None:
            logger.warn(f"Parent not being set for widget {self}")

        if widgetName is None:
            self.applyDefaultName()
        else:
            self.objectName = widgetName
            self.setObjectName(widgetName)

        self.applyDefaultLayout(layout=layout)
        self.applyDefaultStyleSheet(color=color, styleSheet=styleSheet)

    def applyDefaultName(self):
        global CURRENT_WIDGET_ID
        self.id = CURRENT_WIDGET_ID
        self.objectName = f"WIDGET_{self.id}"
        CURRENT_WIDGET_ID += 1
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
        ss = configStyleSheet(ss)

        self.setStyleSheet(ss)

    def freeze(self):
        self.frozen = True

    def unfreeze(self):
        self.frozen = False

    def prepareDeletion(self):
        self.deleted = True
        self.deleteLater()
        if hasattr(self, "isEventChild") and self.isEventChild:
            self.deleteEvents()

    def forceUpdateParent(
        self, depth=100, anyWidget=False
    ):  # depth is always "infinite" atm
        d = 0
        w = self
        while w.parentWidget() is not None:
            w = w.parentWidget()
            if isinstance(w, CollapsibleWidget):
                # idk why this is needed, but it is
                # otherwise things just dont update properly
                # also, only .adjustSize is also not good enough for some reason
                w.forceUpdateLayout()
                w.forceUpdateSize()
                d += 1
            elif isinstance(w, HorizontalExpandingScrollArea) or isinstance(
                w, ExpandingScrollArea
            ):
                # w.adjustSize()
                w.forceUpdateSize()
                # forces resize event, gives invalid "previous size" to force an update
                d += 1

            elif anyWidget:
                d += 1
                Widget.forceUpdateSize(w)

            if d >= depth:
                return

    def forceUpdateSize(self):
        self.resizeEvent(QtGui.QResizeEvent(self.size(), QtCore.QSize()))


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


class ProgressBar(QtWidgets.QProgressBar):
    def __init__(self, parent=None, color=None, styleSheet=""):
        super().__init__(parent=parent)

        Widget.applyDefaultName(self)
        Widget.applyDefaultStyleSheet(self, color=color, styleSheet=styleSheet)


class Slider(Widget):

    callbackFunc = None
    quiet = False
    smoothing = 1

    def __init__(
        self,
        *args,
        hasEditBox=True,
        label=None,
        nMin=0,
        nMax=99999,
        interval=1,
        **kwargs,
    ):
        super().__init__(*args, **kwargs, layout="horizontal")

        self.hasEditBox = hasEditBox
        self.interval = 1

        self.slider = QtWidgets.QSlider(Qt.Horizontal)
        self.layout.addWidget(self.slider)
        self.slider.valueChanged.connect(self.onUpdateSlider)

        if hasEditBox:
            self.lineEdit = LineEdit()
            self.lineEdit.setFixedWidth(70)
            self.layout.addWidget(self.lineEdit)
            self.lineEdit.setOnEdit(self.onUpdateLineEdit)

        if label is not None:
            self.label = QtWidgets.QLabel(label)
            self.layout.insertWidget(0, self.label)
            self.layout.setSpacing(8)

        self.setMinMax(nMin, nMax, interval)

    def setMinMax(self, nMin, nMax, interval=1):
        self.nMin = nMin
        self.nMax = nMax

        self.slider.setMinimum(nMin)
        self.slider.setMaximum(nMax)
        self.slider.setTickInterval(interval)

        val = QtGui.QIntValidator(nMin, nMax)
        self.lineEdit.setValidator(val)

    def onUpdateSlider(self, value):
        self.lineEdit.setText(str(value))
        self.callback()

    def onUpdateLineEdit(self):
        value = self.lineEdit.text()
        self.slider.setValue(int(value))
        self.callback()

    def setValue(self, value, quiet=False):
        self.quiet = quiet
        self.lineEdit.setText(str(value))
        self.slider.setValue(int(value))
        self.quiet = False

    def getValue(self):
        return self.slider.value()

    def setCallbackFunc(self, func):
        self.callbackFunc = func

    def callback(self):
        if not self.quiet and (self.callbackFunc is not None):
            self.callbackFunc(self.getValue())


class ComboBox(QtWidgets.QComboBox):
    def __init__(self, *args, color=None, styleSheet="", **kwargs):
        super().__init__(*args, **kwargs)

        Widget.applyDefaultName(self)
        Widget.applyDefaultStyleSheet(self, color=color, styleSheet=styleSheet)


class LineEdit(QtWidgets.QLineEdit):

    callbackFunc = None

    def __init__(self, *args, color=None, styleSheet="", **kwargs):
        super().__init__(*args, **kwargs)

        Widget.applyDefaultName(self)
        Widget.applyDefaultStyleSheet(self, color=color, styleSheet=styleSheet)

        self.editingFinished.connect(self.callback)

    def setOnEdit(self, func):
        self.callbackFunc = func

    def callback(self):
        self.clearFocus()
        if self.callbackFunc is not None:
            self.callbackFunc()


class CodeLineEdit(LineEdit):

    returnCallback = None

    def __init__(self, *args, validationFunc=None, **kwargs):
        kwargs.update(color="black")
        super().__init__(*args, **kwargs)

        self.validationFunc = validationFunc
        self.setOnEdit(self.onLineEdit)

    def validate(self):
        valid, validT = True, self.getValue()
        if validT is None:
            return False, None

        if self.validationFunc is not None:
            try:
                valid, validT = self.validationFunc(validT)
            except Exception as e:
                logger.exception(
                    f"Tried validating CodeLineEdit input, but got error {e}"
                )
                return False, None

        return valid, validT

    def setReturnCallback(self, func):
        self.returnCallback = func

    def onLineEdit(self):
        validated, cleanedT = self.validate()
        if not validated:
            return
        self.clearFocus()
        self.setCode(cleanedT)
        if self.returnCallback is not None:
            self.returnCallback()

    def getValue(self):
        t = self.text()
        t = t.replace("; ", "\n").replace(";", "\n")
        code = None
        try:
            code = ast.literal_eval(t)
        except (TypeError, MemoryError, SyntaxError, ValueError):
            logger.exception("Input cannot be evaluated")

        return code

    def setCode(self, value):
        text = pprint.pformat(value, width=30)
        self.setText(text.replace("\n", "; "))


class CodeTextEdit(QtWidgets.QTextEdit):

    returnCallback = None

    def __init__(self, *args, validationFunc=None, **kwargs):
        super().__init__(*args, **kwargs)

        Widget.applyDefaultName(self)
        Widget.applyDefaultStyleSheet(self, color="black")

        self.validationFunc = validationFunc

        self.installEventFilter(self)

    def setReturnCallback(self, func):
        self.returnCallback = func

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            if event.modifiers() == Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                validated, cleanedT = self.validate()
                if not validated:
                    return
                self.clearFocus()
                self.setCode(cleanedT)
                if self.returnCallback is not None:
                    self.returnCallback()
        else:
            super().keyPressEvent(event)

    def validate(self):
        valid, validT = True, self.getValue()
        if validT is None:
            return False, None

        if self.validationFunc is not None:
            try:
                valid, validT = self.validationFunc(validT)
            except Exception as e:
                logger.exception(
                    f"Tried validating CodeTextEdit input, but got error {e}"
                )
                return False, None

        return valid, validT

    def getValue(self):
        t = self.toPlainText()
        code = None
        try:
            code = ast.literal_eval(t)
        except (TypeError, MemoryError, SyntaxError, ValueError):
            logger.exception("Input cannot be evaluated")

        return code

    def setCode(self, value):
        text = pprint.pformat(value, width=30)
        self.setText(text)


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
    padding = 4

    def __init__(
        self, func, icon="default", padding=None, width=25, height=25, **kwargs
    ):
        super().__init__(**kwargs)
        if padding is not None:
            self.padding = padding
        self.clicked.connect(func)
        self.setIconByName(icon)
        self.setButtonSize(width, height)

    def setIconByName(self, name):
        icon = getIcon(name)
        self.setIcon(QtGui.QIcon(icon))

    def setButtonSize(self, w, h):
        self.setFixedSize(w, h)
        self.setIconSize(
            QtCore.QSize(w - self.padding * 2, h - self.padding * 2)
        )


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
        # h = 0
        # if self.contentWidget is not None:
        #     h = self.contentWidget.height()
        return self.contentWidget.sizeHint()

    def resizeEvent(self, *args):
        # w = self.contentWidget.minimumSizeHint().width() # sizeHint().width()
        # self.setMinimumWidth(w+10)
        QtWidgets.QScrollArea.resizeEvent(self, *args)

    def forceUpdateSize(self):
        self.resizeEvent(QtGui.QResizeEvent(self.size(), QtCore.QSize()))


class HorizontalExpandingScrollArea(QtWidgets.QScrollArea):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setWidgetResizable(True)
        # horizontal then vertical
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        self.setMaximumWidth(0)
        self.setMinimumWidth(0)

    contentWidget = None

    def setContent(self, widget):
        self.setWidget(widget)
        widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.contentWidget = widget
        self.setMaximumWidth(16777215)

    def sizeHint(self):
        w = 0
        if self.contentWidget is not None:
            w = self.contentWidget.width()
        return QtCore.QSize(w, super().sizeHint().height() + 10)

    def resizeEvent(self, *args):
        self.setMinimumHeight(self.contentWidget.sizeHint().height() + 10)
        self.setMaximumHeight(self.contentWidget.sizeHint().height() + 10)
        QtWidgets.QScrollArea.resizeEvent(self, *args)

    def forceUpdateSize(self):
        self.contentWidget.forceUpdateSize()
        self.resizeEvent(QtGui.QResizeEvent(self.size(), QtCore.QSize()))


class HorizontalContainerScrollArea(Widget):
    def __init__(self, **kwargs):
        super().__init__(layout="vertical", **kwargs)
        self.scrollArea = HorizontalExpandingScrollArea()
        self.content = Widget(layout="horizontal")
        self.scrollArea.setContent(self.content)
        self.layout.addWidget(self.scrollArea)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def addContent(self, widget):
        self.content.layout.addWidget(widget)

    def addStretch(self):
        self.content.layout.addStretch()

    def resizeEvent(self, *args):
        Widget.resizeEvent(self, *args)
        self.scrollArea.setMaximumWidth(self.width())


class CollapseButton(QtWidgets.QPushButton, Widget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("collapseButton")
        self.setIcon(QtGui.QIcon(getIcon("expanded")))
        self.clicked.connect(self.onClick)

    collapsingWidget = None
    callbackFunc = None

    def setCollapsingWidget(self, widget):
        self.collapsingWidget = widget
        self.updateIcon()
        self.setCollapsed()

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
        if self.callbackFunc is not None:
            self.callbackFunc()

    def setExpanded(self):
        self.collapsingWidget.show()
        self.updateIcon()
        self.updateSize()
        if self.callbackFunc is not None:
            self.callbackFunc()

    def isExpanded(self):
        return self.collapsingWidget.isVisible()

    def updateSize(self):
        self.forceUpdateParent()

    def setCallback(self, func):
        self.callbackFunc = func


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

        self.scrollWidget.setMaximumWidth(self.titleButton.width())

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

    def setCallback(self, func):
        self.titleButton.setCallback(func)

    def resizeEvent(self, event):
        Widget.resizeEvent(self, event)
        self.scrollWidget.setMaximumWidth(self.titleButton.width())


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

        self.widgets = {}

    def addContent(self, name, widget=None, callback=None):
        content = CollapsibleWidget(
            self.handler, name=name, widget=widget, parent=self
        )
        self.layout.insertWidget(self.layout.count() - 1, content)
        self.widgets[name] = content
        return content

    def setCollapsed(self, name):
        self.widgets[name].setCollapsed()

    def setExpanded(self, name):
        self.widgets[name].setExpanded()

    def setContentVisibility(self, name, vis):
        widget = self.widgets.get(name)
        if widget is None:
            return

        if vis:
            widget.show()
        else:
            widget.hide()


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
        self.objectsRemoved = set()

    def newObject(self, id, **kwargs):
        if id in self.widgets:
            logger.error(
                f"ID {id} already exists for ObjectList {self} and widgetType {self.widgetType}."
            )
            return

        if id in self.objectsRemoved:
            self.objectsRemoved.remove(id)

        w = self.widgetType(self.handler, id, parent=self, **kwargs)
        self.widgets[id] = w
        self.layout.addWidget(w)

        self.forceUpdateParent()

    def getWidget(self, id):
        return self.widgets.get(id, None)

    def removeObject(self, id):
        if id is self.objectsRemoved:
            return

        w = self.getWidget(id)

        if w is None:
            return

        del self.widgets[id]

        self.layout.removeWidget(w)
        w.prepareDeletion()

        self.objectsRemoved.add(id)

        # force udpate parents if they're collapsible scrollareas
        self.forceUpdateParent()


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
                w.prepareDeletion()
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


class ObjectComboBox(ComboBox, EventChildClass):

    updateFunc = None
    selectedKey = None
    currentlyUpdatingList = False

    def __init__(
        self, handler, hasDatasets=True, watcher=None, *args, **kwargs
    ):
        self.handler = handler
        self.env = handler.env
        super().__init__(*args, **kwargs)
        EventChildClass.__init__(self)

        self.hasDatasets = hasDatasets
        self.watcher = watcher

        if self.hasDatasets:
            self.eventSubscribe("DATASET_LOADED", self.updateList)
            self.eventSubscribe("DATASET_DELETED", self.updateList)

        else:
            self.eventSubscribe("MODEL_LOADED", self.updateList)
            self.eventSubscribe("MODEL_DELETED", self.updateList)

        self.eventSubscribe("OBJECT_NAME_CHANGED", self.updateList)

        self.currentKeyList = []
        self.updateList()

        self.currentIndexChanged.connect(self.onIndexChanged)

    def updateList(self, *args):
        self.currentlyUpdatingList = True
        l = []
        if self.hasDatasets:
            l = l + self.env.getAllDatasetKeys()

        else:
            l = l + self.env.getAllModelKeys()

        self.currentKeyList = l
        self.updateComboBox()

        # RESELECT PREVIOUS ONE
        if self.selectedKey in self.currentKeyList:
            index = self.currentKeyList.index(self.selectedKey)
            self.setCurrentIndex(index)
        elif len(self.currentKeyList) > 0:
            self.setCurrentIndex(0)
            self.forceUpdate()

        self.currentlyUpdatingList = False

    def updateComboBox(self, *args):
        self.clear()
        self.addItems(
            [
                self.env.getModelOrDataset(x).getDisplayName()
                for x in self.currentKeyList
            ]
        )

    def setOnIndexChanged(self, func):
        self.updateFunc = func

    def forceUpdate(self):
        self.onIndexChanged(self.currentIndex())

    def updateWatcher(self):
        key = self.getActiveKey()
        if self.hasDatasets:
            self.watcher.setDatasetDependencies(key)
        else:
            self.watcher.setModelDependencies(key)

    def getActiveKey(self):
        index = self.currentIndex()
        if (index < 0) or (index >= len(self.currentKeyList)):
            return None

        return self.currentKeyList[index]

    def onIndexChanged(self, index):
        if self.currentlyUpdatingList:
            return

        key = self.getActiveKey()
        self.selectedKey = key

        if self.watcher is not None:
            self.updateWatcher()

        if self.updateFunc is not None:
            self.updateFunc(key)


class BasicLabelWidget(Widget):
    def __init__(self, spacing=0, **kwargs):
        super().__init__(layout="vertical", **kwargs)

        self.layout.setContentsMargins(spacing, spacing, spacing, spacing)

        self.label = QtWidgets.QLabel("")
        self.layout.addWidget(self.label)

    def setText(self, s):
        self.label.setText(s)


class TableView(Widget):
    """Simple view-only table.

    Note: internally everything is column major! Accessing externally is row.
    """

    tableSize = (0, 0)
    headerLeft = True
    headerTop = True
    spacing = 10

    borderQSS = "1px inset @BGColor5"

    styleSheet = """
    """

    headerLabelStyleSheet = """
        QLabel{
            font-weight: bold;
        }

        QWidget#tableHeaderLabelLeft{
            border-top: @borderQSS;
        }

        QWidget#tableHeaderLabelTop{
            border-left: @borderQSS;
        }

    """

    labelStyleSheet = """
        @OBJECT{
            border-top: @borderQSS;
            border-left: @borderQSS;
        }
    """

    def __init__(
        self, headerLeft=True, headerTop=True, spacing=None, **kwargs
    ):
        kwargs.update(layout="horizontal")
        super().__init__(styleSheet=self.styleSheet, **kwargs)

        if spacing is not None:
            self.spacing = spacing
        else:
            spacing = self.spacing

        self.headerLabelStyleSheet = self.headerLabelStyleSheet.replace(
            "@borderQSS", self.borderQSS
        )
        self.styleSheet = self.styleSheet.replace("@borderQSS", self.borderQSS)
        self.labelStyleSheet = self.labelStyleSheet.replace(
            "@borderQSS", self.borderQSS
        )

        # self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        self.headerLeft = headerLeft
        self.headerTop = headerTop

        self.labels = []
        self.headerTopLabels = []
        self.headerLeftLabels = []
        self.cornerLabel = BasicLabelWidget(
            widgetName="tableHeaderLabelCorner",
            styleSheet=self.headerLabelStyleSheet,
            spacing=self.spacing,
            color="transparent",
        )
        self.columnWidgets = []
        self.headerLeftWidget = Widget(layout="vertical")
        self.headerLeftWidget.layout.addWidget(self.cornerLabel)
        self.layout.addWidget(self.headerLeftWidget)

    def setSize(self, nRows, nCols):
        self.tableSize = (nRows, nCols)
        self.updateHeaders()

        # create labels if necessary
        for col in range(0, nCols):
            for row in range(len(self.labels[col]), nRows):
                label = BasicLabelWidget(
                    widgetName="tableHeaderLabel",
                    styleSheet=self.labelStyleSheet,
                    spacing=self.spacing,
                    color="transparent",
                )
                # need transparent color for borders to show, idk why and honestly I dont care to find out

                self.labels[col].append(label)
                self.columnWidgets[col].layout.addWidget(label)

        # hide/show those needed
        for col in range(len(self.labels)):
            for row in range(len(self.labels[col])):

                if (row >= nRows) or (col >= nCols):
                    self.hideLabel(self.labels[col][row])
                else:
                    self.showLabel(self.labels[col][row])

        self.forceUpdateParent()  # doesnt do anything, idk whyyyy

    def showLabel(self, label):
        label.show()

    def hideLabel(self, label):
        label.hide()

    def updateHeaders(self):
        nRows, nCols = self.tableSize

        # CREATE LEFT HEADERS
        for row in range(len(self.headerLeftLabels), nRows):
            label = BasicLabelWidget(
                widgetName="tableHeaderLabelLeft",
                styleSheet=self.headerLabelStyleSheet,
                spacing=self.spacing,
                color="transparent",
            )
            self.headerLeftLabels.append(label)
            self.headerLeftWidget.layout.addWidget(label)

        # CREATE TOP HEADERS
        for col in range(len(self.columnWidgets), nCols):
            self.columnWidgets.append(Widget(layout="vertical"))
            self.layout.addWidget(self.columnWidgets[col])
            self.labels.append([])

            label = BasicLabelWidget(
                widgetName="tableHeaderLabelTop",
                styleSheet=self.headerLabelStyleSheet,
                spacing=self.spacing,
                color="transparent",
            )
            self.headerTopLabels.append(label)
            self.columnWidgets[col].layout.addWidget(label)

        # CORNER LABEL
        if not self.headerTop:
            self.cornerLabel.hide()
        else:
            self.cornerLabel.show()

        # HIDE/SHOW LEFT HEADERS
        for row in range(len(self.headerLeftLabels)):
            if self.headerLeft and row < nRows:
                self.showLabel(self.headerLeftLabels[row])
            else:
                self.hideLabel(self.headerLeftLabels[row])

        # HIDE/SHOW TOP HEADERS
        for col in range(len(self.headerTopLabels)):
            if self.headerTop and col < nCols:
                self.showLabel(self.headerTopLabels[col])
            else:
                self.hideLabel(self.headerTopLabels[col])

    def setValue(self, row, col, s):
        nRows, nCols = self.tableSize

        if (row > nRows) or (col > nCols):
            logger.error(
                f"Tried to set table value at ({row},{col}) but size is {self.tableSize}"
            )

        label = self.labels[col][row]
        label.setText(s)

    def setLeftHeader(self, row, s):
        self.headerLeftLabels[row].setText(s)

    def setTopHeader(self, col, s):
        self.headerTopLabels[col].setText(s)


#############
## SETTINGS
#############


class SettingsWidgetBase(Widget, EventChildClass):

    hideFunc = None
    callbackFunc = None
    quiet = False

    def __init__(
        self,
        handler,
        name,
        settings=None,
        settingsKey=None,
        hasLabel=True,
        layout="horizontal",
        fixedHeight=True,
        parent=None,
        **kwargs,
    ):
        super().__init__(layout=layout, parent=parent, **kwargs)
        self.handler = handler
        self.name = name

        if parent is None:
            logger.exception(
                f"SettingsWidget {self} was not given pane as parent: parent = {parent}"
            )
        self.paneParent = parent

        self.settings = settings
        self.settingsKey = settingsKey
        self.hasSettingsKey = (settings is not None) and (
            settingsKey is not None
        )

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        if fixedHeight:
            self.setFixedHeight(40)

        if hasLabel:
            self.label = QtWidgets.QLabel(str(name))
            self.layout.addWidget(self.label)
            # self.layout.addStretch()

        # update the widget if parameter changes
        if self.hasSettingsKey:
            settings.addParameterActions(
                settingsKey, partial(self.setDefault, quiet=True)
            )

    def setHideCondition(self, func):
        self.hideFunc = func

    def updateVisibility(self):
        if (self.hideFunc is not None) and self.hideFunc():
            self.hide()
        else:
            self.show()

        self.forceUpdateParent()

    def setCallback(self, func):
        self.callbackFunc = func

    def callback(self):
        self.paneParent.updateVisibilities()
        if self.quiet:
            return
        if self.hasSettingsKey:
            self.settings.setParameter(self.settingsKey, self.getValue())
        if self.callbackFunc is not None:
            self.callbackFunc()

    def setDefault(self, quiet=False):
        if not self.hasSettingsKey:
            return
        if quiet:
            self.quiet = True
            self.setValue(self.settings.get(self.settingsKey, None))
            self.quiet = False
        else:
            self.setValue(self.settings.get(self.settingsKey, None))

    def setValue(self, *args):
        self._setValue(*args)
        self.paneParent.updateVisibilities()

    def getValue(self, *args):
        return self._getValue(*args)


class SettingsCheckBox(SettingsWidgetBase):
    def __init__(self, *args, settings=None, settingsKey=None, **kwargs):
        super().__init__(
            *args, settings=settings, settingsKey=settingsKey, **kwargs
        )

        self.checkBox = QtWidgets.QCheckBox("", self)
        self.setDefault()
        self.layout.addWidget(self.checkBox)

        self.checkBox.stateChanged.connect(self.callback)

    def _getValue(self):
        return self.checkBox.checkState()

    def _setValue(self, b):
        self.checkBox.setChecked(b)


class SettingsComboBox(SettingsWidgetBase):
    def __init__(
        self,
        *args,
        settings=None,
        settingsKey=None,
        isNumber=False,
        items=(),
        **kwargs,
    ):
        super().__init__(
            *args, settings=settings, settingsKey=settingsKey, **kwargs
        )
        self.isNumber = isNumber
        self.comboBox = ComboBox(parent=self)
        self.comboBox.setFixedWidth(150 - 8)

        self.setItems(items)
        self.setDefault()

        self.comboBox.currentIndexChanged.connect(self.callback)
        self.layout.addWidget(self.comboBox)

    def setItems(self, items):
        self.items = []
        self.comboBox.clear()
        self.comboBox.addItems(items)

    def addItems(self, items):
        self.items = self.items + items
        self.comboBox.addItems(items)

    def _getValue(self):
        t = self.comboBox.currentText()
        if self.isNumber:
            return float(t)
        else:
            return str(t)

    def _setValue(self, value):
        self.comboBox.setCurrentText(value)


class SettingsCodeBox(SettingsWidgetBase):
    def __init__(
        self,
        *args,
        settings=None,
        settingsKey=None,
        validationFunc=None,
        labelDirection="vertical",
        singleLine=False,
        **kwargs,
    ):
        super().__init__(
            *args,
            settings=settings,
            settingsKey=settingsKey,
            layout=labelDirection,
            fixedHeight=False,
            **kwargs,
        )

        if not singleLine:
            self.codeBox = CodeTextEdit(
                parent=self, validationFunc=validationFunc
            )
        else:
            self.codeBox = CodeLineEdit(
                parent=self, validationFunc=validationFunc
            )

        self.codeBox.setReturnCallback(self.callback)

        self.layout.addWidget(self.codeBox)
        self.layout.setSpacing(8)

    def _setValue(self, value):
        self.codeBox.setCode(value)

    def _getValue(self):
        return self.codeBox.getValue()


class SettingsLineEdit(SettingsWidgetBase):
    def __init__(
        self,
        *args,
        settings=None,
        settingsKey=None,
        isFloat=False,
        isInt=False,
        nMin=0,
        nMax=99999,
        **kwargs,
    ):
        super().__init__(
            *args, settings=settings, settingsKey=settingsKey, **kwargs
        )

        self.isFloat = isFloat
        self.isInt = isInt

        self.lineEdit = LineEdit("?", parent=self)
        self.lineEdit.setFixedWidth(150 - 8)
        self.lineEdit.setMaxLength(10)

        if self.isInt:
            val = QtGui.QIntValidator(nMin, nMax)
            self.lineEdit.setValidator(val)
        elif self.isFloat:
            val = QtGui.QDoubleValidator(
                nMin, nMax, 4, notation=QtGui.QDoubleValidator.StandardNotation
            )
            self.lineEdit.setValidator(val)

        self.setDefault()

        self.lineEdit.setOnEdit(self.callback)
        self.layout.addWidget(self.lineEdit)

    def _getValue(self):
        t = self.lineEdit.text()
        if self.isFloat:
            return float(t)
        elif self.isInt:
            return int(t)
        else:
            return str(t)

    def _setValue(self, value):
        self.lineEdit.setText(str(value))


class SettingsContainer(SettingsWidgetBase):
    def __init__(self, *args, **kwargs):
        super().__init__(
            self, *args, hasLabel=False, fixedHeight=False, **kwargs
        )


class SettingsPane(Widget, EventChildClass):
    def __init__(self, UIHandler, settings, **kwargs):
        self.handler = UIHandler
        super().__init__(layout="vertical", **kwargs)
        EventChildClass.__init__(self)
        self.settingsWidgets = {}
        self.settings = settings
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)

    def addSetting(
        self,
        typ,
        name,
        manualLayout=False,
        insertIndex=None,
        settingsKey=None,
        toolTip=None,
        **kwargs,
    ):

        if settingsKey is None:
            logger.warn(
                f"Adding setting of name {name} and type {typ} to SettingsPane, but no settings key given."
            )

        if name in self.settingsWidgets:
            logger.error(
                f"Tried to add setting of name {name} and type {typ} but name already taken in pane."
            )
            return

        if typ == "ComboBox":
            el = SettingsComboBox(
                self.handler,
                name,
                settingsKey=settingsKey,
                settings=self.settings,
                parent=self,
                **kwargs,
            )

        elif typ == "LineEdit":
            el = SettingsLineEdit(
                self.handler,
                name,
                settingsKey=settingsKey,
                settings=self.settings,
                parent=self,
                **kwargs,
            )

        elif typ == "CheckBox":
            el = SettingsCheckBox(
                self.handler,
                name,
                settingsKey=settingsKey,
                settings=self.settings,
                parent=self,
                **kwargs,
            )

        elif typ == "CodeBox":
            el = SettingsCodeBox(
                self.handler,
                name,
                settingsKey=settingsKey,
                settings=self.settings,
                parent=self,
                **kwargs,
            )

        elif typ == "Container":
            el = SettingsContainer(self.handler, name, parent=self, **kwargs)

        else:
            logger.error(
                f"Tried to make setting for SettingsPane {self} but type {typ} not recognised"
            )
            return

        if not manualLayout:
            if insertIndex is None:
                self.layout.addWidget(el)
            else:
                self.layout.insertWidget(insertIndex, el)
            self.settingsWidgets[name] = el

        if toolTip is not None:
            el.setToolTip(toolTip)

        self.updateVisibilities()

        return el

    def getSettingValue(self, name):
        el = self.settingsWidgets.get(name, None)
        if el is None:
            return None
        return el.getValue()

    def updateVisibilities(self):
        for _, v in self.settingsWidgets.items():
            v.updateVisibility()


#############
## MISC
#############


def customFileDialog(parent, fileTypes=None, extensions=None, save=False):
    options = QFileDialog.Options()

    if fileTypes is None:
        if save:
            fileName, selectedFilter = QFileDialog.getSaveFileName(
                parent, "Save File", "", options=options
            )
        else:
            fileName, selectedFilter = QFileDialog.getOpenFileName(
                parent, "Open File", "", options=options
            )
        return fileName, None
    else:
        if extensions is None:
            extensions = ["*"] * len(fileTypes)

        filterList = [
            f"{fileTypes[i]} ({extensions[i]})" for i in range(len(fileTypes))
        ]

        filterString = ";;".join(filterList)
        if save:
            fileName, selectedFilter = QFileDialog.getSaveFileName(
                parent, "Save File", "", filterString, options=options
            )
        else:
            fileName, selectedFilter = QFileDialog.getOpenFileName(
                parent, "Open File", "", filterString, options=options
            )

        if fileName == "":
            return None, None

        filterIndex = filterList.index(selectedFilter)
        return fileName, fileTypes[filterIndex]
