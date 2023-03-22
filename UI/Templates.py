from PySide6 import QtCore, QtGui, QtWidgets
from config.uiConfig import config, configStyleSheet
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QWidget, QTabWidget
from config.uiConfig import config, getIcon
from PySide6.QtWidgets import QSizePolicy
from events import EventChildClass
import pyqtgraph
import logging

WIDGET_ID = 0

logger = logging.getLogger("FFAST")


class Widget(QWidget):
    def __init__(self, layout=None, color=None, parent=None, styleSheet = ''):
        super().__init__(parent=parent)

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

    def applyDefaultLayout(self, layout = None):
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

    def applyDefaultStyleSheet(self, color = None, styleSheet = ""):
        ss = f'QWidget#{self.objectName}' + '{\n' # closing '}' later
        if color is not None:
            self.setAttribute(Qt.WA_StyledBackground, True)
            ss = ss + f"background-color:{color};\n"

        if len(styleSheet) > 0:
            ss = ss + styleSheet + '\n'

        ss = ss + '}'

        self.setStyleSheet(configStyleSheet(ss))


class WidgetOld(QWidget):
    def __init__(self, layout=None, color=None, parent=None, styleSheet = ''):
        super().__init__(parent=parent)

        if parent is None:
            logger.warn(f"Parent not being set for widget {self}")

        global WIDGET_ID
        self.id = WIDGET_ID
        self.objectName = f"WIDGET_{self.id}"
        WIDGET_ID += 1
        self.setObjectName(self.objectName)

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

        ss = f'QWidget#{self.objectName}' + '{\n' # closing '}' later
        if color is not None:
            self.setAttribute(Qt.WA_StyledBackground, True)
            ss = ss + f"background-color:{color};\n"

        if len(styleSheet) > 0:
            ss = ss + styleSheet + '\n'

        ss = ss + '}'

        self.setStyleSheet(configStyleSheet(ss))


class TabWidget(QTabWidget):
    def __init__(self, parent=None, color=None, styleSheet = ""):
        super().__init__(parent=parent)

        Widget.applyDefaultName(self)
        Widget.applyDefaultStyleSheet(self, color=color, styleSheet=styleSheet)


class PushButton(QtWidgets.QPushButton):
    def __init__(self, text, parent=None, color=None, styleSheet = ""):
        super().__init__(text, parent=parent)

        Widget.applyDefaultName(self)
        Widget.applyDefaultStyleSheet(self, color=color, styleSheet=styleSheet)


class ToolCheckButton(QtWidgets.QToolButton):
    checked = False
    def __init__(self, handler, func, icon="default", **kwargs):
        super().__init__(**kwargs)
        self.handler = handler
        self.clicked.connect(func)
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
        pass

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


class InfoWidget(Widget):
    nRows = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

        self.setStyleSheet(
            configStyleSheet(
                """
                QLabel#LeftLabel{
                    font-weight: bold;
                }
                QLabel{
                    qproperty-alignment: AlignLeft;
                }
                """
            )
        )

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


class ContentTab(ExpandingScrollArea):
    def __init__(self, layout=None, color="@BGColor2", **kwargs):
        super().__init__(**kwargs)

        self.widget = Widget(layout=layout, color=color, parent=self)
        self.setContent(self.widget)

        self.widget.layout.setContentsMargins(40, 40, 40, 40)
        self.widget.layout.setSpacing(40)

    def addWidget(self, *args, **kwargs):
        self.widget.layout.addWidget(*args, **kwargs)

