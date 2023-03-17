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

    def __init__(self, layout = None, color = None):
        super().__init__()
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


class MenuButton(QtWidgets.QPushButton):

    def __init__(self, name):
        super().__init__(name, flat = True)

        self.menu = QtWidgets.QMenu()
        self.setMenu(self.menu)

        self.setStyleSheet("::menu-indicator{ image: none; }")

    def addAction(self, *args):
        self.menu.addAction(*args)

class MovingHandle(Widget):

    _mousePressed = False

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def mousePressEvent(self, event):
        self._mousePressed = True
        self.oldPos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self._mousePressed = False

    def mouseMoveEvent(self, event):
        if not self._mousePressed:
            return QWidget.mouseMoveEvent(self, event)
        delta = QtCore.QPoint(event.globalPos() - self.oldPos)
        window = self.parent
        window.move(window.x() + delta.x(), window.y() + delta.y())
        self.oldPos = event.globalPos()

class MenuBar(Widget):

    def __init__(self, handler, parent):
        super().__init__()

        self.handler = handler
        self.setObjectName("menuBar")

        self.paddingLayout = QtWidgets.QHBoxLayout()
        self.paddingLayout.setContentsMargins(BORDER_DRAG_SIZE, BORDER_DRAG_SIZE, BORDER_DRAG_SIZE, 0)
        self.setLayout(self.paddingLayout)
        self.window = MovingHandle(parent)
        self.paddingLayout.addWidget(self.window)

        self.layout = QtWidgets.QHBoxLayout()
        self.window.setLayout(self.layout)        
        self.layout.setContentsMargins(0,0,0,BORDER_DRAG_SIZE)
        self.setMaximumHeight(40)

        self.layout.addStretch()

        closeButton = ToolButton(self.handler, self.closeFunc, icon = 'close')
        self.layout.addWidget(closeButton)

        self.setAttribute(Qt.WA_StyledBackground, True)
        styleSheet = '''
            QWidget#menuBar{
               background-color:@BGColor1;
            }
        '''
        self.setStyleSheet(configStyleSheet(styleSheet))
        self.parentWidget = parent

    def closeFunc(self):
        if hasattr(self, "onClose"):
            self.onClose()
        self.parentWidget.close()

    def sizeHint(self):
        return QtCore.QSize(super().sizeHint().width(),self.maximumHeight())
    

class ToolButton(QtWidgets.QToolButton):

    def __init__(self, handler, func, icon = 'default'):
        self.handler = handler
        super().__init__()
        self.clicked.connect(func)
        icon = getIcon(icon)
        self.setIcon(QtGui.QIcon(icon))

class FramelessResizableWindow(Widget):

    _mouseButtonPressed = False
    _dragTop = False
    _dragRight = False
    _dragDown = False
    _dragLeft = False

    def __init__(self):
        super().__init__()

        self.setWindowFlag(Qt.FramelessWindowHint)
        self._startGeometry = self.geometry()

        self.installEventFilter(self)

    def checkBorderDragging(self, event):

        if self.isMaximized():
            return
        
        pos = event.globalPos()

        if self._mouseButtonPressed:
            # screen = self.window().windowHandle().screen()
            # availGeo = screen.availableGeometry()
            # h, w = availGeo.height(), availGeo.width()
            
            newW = self._startGeometry.width()
            newH = self._startGeometry.height()
            newX = self._startGeometry.x()
            newY = self._startGeometry.y()

            # LOGIC
            # if self._dragLeft:
            #     newX = pos.x() - self._startGeometry.x()
            if self._dragLeft:
                newW = self._startGeometry.width() + (self._startGeometry.x() - pos.x())
                newX = pos.x()

            if self._dragRight:
                newW = pos.x() - self._startGeometry.x()

            if self._dragTop:
                newY = pos.y()
                newH = self._startGeometry.height() + (self._startGeometry.y() - pos.y())

            if self._dragBottom:
                newH = pos.y() - self._startGeometry.y()

            self.setGeometry(newX, newY, newW, newH)

        # NO MOUSE BTN 
        else:
            top, right, bottom, left = self.bordersHit(event)

            if (left and top) or (right and bottom):
                QApplication.setOverrideCursor(Qt.SizeFDiagCursor)
            elif (right and top) or (left and bottom):
                QApplication.setOverrideCursor(Qt.SizeBDiagCursor)
            elif left or right:
                QApplication.setOverrideCursor(Qt.SizeHorCursor)
            elif top or bottom:
                QApplication.setOverrideCursor(Qt.SizeVerCursor)
            else:
                QApplication.restoreOverrideCursor()

    def bordersHit(self, event):
        # top, right, bottom, left
        geo = self.geometry()
        x, y, w, h = event.x(), event.y(), geo.width(), geo.height()

        top = (y >= 0) and (y <= BORDER_DRAG_SIZE)
        right = (x >= w - BORDER_DRAG_SIZE) and (x <= w)
        bottom = (y >= h - BORDER_DRAG_SIZE) and (y <= h)
        left = (x >= 0) and (x <= BORDER_DRAG_SIZE)

        return top, right, bottom, left

    def mousePressEvent(self, event):
        if self.isMaximized():
            return

        self._mouseButtonPressed = True
        self._startGeometry = self.geometry()
        top, right, bottom, left = self.bordersHit(event)
        
        self._dragTop = top
        self._dragRight = right
        self._dragBottom = bottom
        self._dragLeft = left

    def mouseReleaseEvent(self, event):
        if self.isMaximized():
            return 

        self._mouseButtonPressed = False
        self._dragTop = False
        self._dragRight = False
        self._dragBottom = False
        self._dragLeft = False

    def eventFilter(self, obj, event):
        # needed to reimplement border resizing
        # see https://github.com/Jorgen-VikingGod/Qt-Frameless-Window-DarkStyle/blob/master/framelesswindow/framelesswindow.cpp
        
        if self.isMaximized():
            return QWidget.eventFilter(self, obj, event)

        if event.type() == QEvent.MouseMove:
            self.checkBorderDragging(event)

        elif event.type() == QEvent.MouseButtonPress and (obj is self):
            self.mousePressEvent(event)
        
        elif event.type() == QEvent.MouseButtonRelease:
            self.mouseReleaseEvent(event)

        return QWidget.eventFilter(self, obj, event)
    
class ExpandingScrollArea(QtWidgets.QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setMaximumHeight(0)
        self.setMinimumHeight(0)

    contentWidget = None
    def setContent(self, widget):
        self.setWidget(widget)
        self.contentWidget = widget
        self.setMaximumHeight(16777215)

    def sizeHint(self):
        h = 0
        if self.contentWidget is not None:
            h = self.contentWidget.height()
        return QtCore.QSize(super().sizeHint().width(),h)

done = False
class CollapsibleWidget(Widget):

    def __init__(self, handler, name = 'N/A', titleHeight = 25, widget = None):
        super().__init__(layout = 'vertical')
        self.handler = handler
        self.titleHeight = titleHeight

        # make title button
        self.titleButton = QtWidgets.QPushButton(name)
        self.titleButton.setObjectName("collapseButton") # for styling
        self.titleButton.setFixedHeight(self.titleHeight)

        self.titleButton.setIcon(QtGui.QIcon(getIcon("expanded")))
        self.layout.addWidget(self.titleButton)

        if widget is None:
            self.scrollWidget = Widget(layout='vertical')
            self.scrollLayout = self.scrollWidget.layout
        else:
            self.scrollWidget = widget

        self.scrollArea = ExpandingScrollArea()
        self.scrollArea.setContent(self.scrollWidget)

        self.layout.addWidget(self.scrollArea)

        self.setExpanded()
   
        self.titleButton.clicked.connect(self.onClick)

    def sizeHint(self):
        return QtCore.QSize(super().sizeHint().width(),super().sizeHint().height())

    def setCollapsed(self):
        self.expanded = False
        self.scrollArea.hide()

    def setExpanded(self):
        self.expanded = True
        self.scrollArea.show()

    def onClick(self):
        if self.expanded:
            self.setCollapsed()
        else:
            self.setExpanded()

class ContentBar(Widget):
    def __init__(self, handler):
        super().__init__(color = "@BGColor1")
        self.handler = handler

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0,0,0,0)
        self.setLayout(self.layout)

        self.setFixedWidth(300)
        self.layout.addStretch()

    def addContent(self, name, widget = None):
        content = CollapsibleWidget(self.handler, name = name, widget = widget)
        self.layout.insertWidget(self.layout.count() - 1, content)

class ObjectListItem(Widget):
    def __init__(self, handler, id, color = None, layout = 'vertical'):
        self.handler = handler
        self.objectID = id
        super().__init__(color = color, layout = layout)

class ObjectList(Widget):
    def __init__(self, handler, widgetType, color = None):
        super().__init__(color=color, layout = 'vertical')
        self.handler = handler
        self.widgetType = widgetType
        self.widgets = {}

    def newObject(self, id, **kwargs):
        if id in self.widgets:
            logger.error(f'ID {id} already exists for ObjectList {self} and widgetType {self.widgetType}.')
            return
        w = self.widgetType(self.handler, id, **kwargs)
        self.widgets[id] = w
        self.layout.addWidget(w)
