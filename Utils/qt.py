from PySide6 import QtCore, QtGui, QtWidgets


def makeStretchingTable(tbl):
    tbl.setSizePolicy(
        QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum
    )

    tbl.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    tbl.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)


def stretchTableToContent(tbl):
    tbl.resizeColumnsToContents()
    tbl.setFixedSize(
        tbl.horizontalHeader().length() + tbl.verticalHeader().width(),
        tbl.verticalHeader().length() + tbl.horizontalHeader().height(),
    )
