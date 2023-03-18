from PySide6 import QtCore, QtGui, QtWidgets
from config.uiConfig import config, configStyleSheet
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QWidget, QApplication
from config.uiConfig import config, getIcon
from PySide6.QtWidgets import QSizePolicy
import logging

BORDER_DRAG_SIZE = config['borderDragSize']
WIDGET_ID = 0

logger = logging.getLogger("FFAST")

class Widget(QWidget):

    def __init__(self, layout = None, color = None, parent = None):
        super().__init__(parent = parent)

        if parent is None:
            logger.warn(f'Parent not being set for widget {self}')

        global WIDGET_ID
        self.setMouseTracking(True)
        self.id = WIDGET_ID
        self.objectName = f'WIDGET_{self.id}'
        WIDGET_ID += 1
        self.setObjectName(self.objectName)

        if layout == 'vertical':
            self.layout = QtWidgets.QVBoxLayout()
        elif layout == 'horizontal':
            self.layout = QtWidgets.QHBoxLayout()

        if layout == 'vertical' or layout == 'horizontal':
            self.setLayout(self.layout)
            self.layout.setContentsMargins(0,0,0,0)
            self.layout.setSpacing(0)
        
        if color is not None:
            self.setAttribute(Qt.WA_StyledBackground, True)
            styleSheet = '''
                QWidget#__ID__{
                background-color:__COLOR__;
                }
            '''.replace('__ID__', self.objectName).replace("__COLOR__", color)
            self.setStyleSheet(configStyleSheet(styleSheet))

class ToolButton(QtWidgets.QToolButton):

    def __init__(self, handler, func, icon = 'default', **kwargs):
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
        return QtCore.QSize(super().sizeHint().width(),h)

class CollapseButton(QtWidgets.QPushButton):
    def __init__(self, *args, layoutUpdateWidget = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("collapseButton")
        self.setIcon(QtGui.QIcon(getIcon("expanded")))
        self.clicked.connect(self.onClick)
        self.layoutUpdateWidget = layoutUpdateWidget

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
                w.scrollArea.setMaximumHeight(10)
                w.scrollArea.setMaximumHeight(100000)
                w.scrollWidget.setMaximumHeight(10)
                w.scrollWidget.setMaximumHeight(100000)

                w.scrollArea.adjustSize()
                w.scrollWidget.adjustSize()


class CollapsibleWidget(Widget):

    def __init__(self, handler, name = 'N/A', titleHeight = 25, widget = None, **kwargs):
        super().__init__(layout = 'vertical', **kwargs)
        self.handler = handler
        self.titleHeight = titleHeight

        # make title button
        self.titleButton = CollapseButton(name)
        self.titleButton.setFixedHeight(self.titleHeight)

        self.layout.addWidget(self.titleButton)

        if widget is None:
            self.scrollWidget = Widget(layout='vertical')
            self.scrollLayout = self.scrollWidget.layout
        else:
            self.scrollWidget = widget

        self.scrollArea = ExpandingScrollArea()
        self.scrollArea.setContent(self.scrollWidget)

        self.layout.addWidget(self.scrollArea)
   
        self.titleButton.setCollapsingWidget(self.scrollArea)

    def sizeHint(self):
        return QtCore.QSize(super().sizeHint().width(),super().sizeHint().height())

    def isExpanded(self):
        return self.titleButton.isExpanded()

    def setCollapsed(self):
        self.titleButton.setCollapsed()

    def setExpanded(self):
        self.titleButton.setExpanded()

class ContentBar(Widget):
    def __init__(self, handler, **kwargs):
        super().__init__(color = "@BGColor1", **kwargs)
        self.handler = handler

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0,0,0,0)
        self.setLayout(self.layout)

        self.setFixedWidth(300)
        self.layout.addStretch()

    def addContent(self, name, widget = None):
        content = CollapsibleWidget(self.handler, name = name, widget = widget, parent = self)
        self.layout.insertWidget(self.layout.count() - 1, content)

class ObjectListItem(Widget):
    def __init__(self, handler, id, color = None, layout = 'vertical', **kwargs):
        super().__init__(color = color, layout = layout, **kwargs)
        self.handler = handler
        self.objectID = id

class ObjectList(Widget):
    def __init__(self, handler, widgetType, color = None, **kwargs):
        super().__init__(color=color, layout = 'vertical', **kwargs)
        self.handler = handler
        self.widgetType = widgetType
        self.widgets = {}

    def newObject(self, id, **kwargs):
        if id in self.widgets:
            logger.error(f'ID {id} already exists for ObjectList {self} and widgetType {self.widgetType}.')
            return
        w = self.widgetType(self.handler, id, parent = self, **kwargs)
        self.widgets[id] = w
        self.layout.addWidget(w)


