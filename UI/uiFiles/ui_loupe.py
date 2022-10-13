# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'loupe.ui'
##
## Created by: Qt User Interface Compiler version 6.2.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QTabWidget, QToolButton, QVBoxLayout,
    QWidget)

class Ui_Form(object):
    def setupUi(self, Form):
        if not Form.objectName():
            Form.setObjectName(u"Form")
        Form.resize(944, 1044)
        self.horizontalLayout_3 = QHBoxLayout(Form)
        self.horizontalLayout_3.setSpacing(0)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.leftContainer = QFrame(Form)
        self.leftContainer.setObjectName(u"leftContainer")
        self.leftContainer.setFrameShape(QFrame.StyledPanel)
        self.leftContainer.setFrameShadow(QFrame.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.leftContainer)
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.header = QWidget(self.leftContainer)
        self.header.setObjectName(u"header")
        self.headerLayout = QHBoxLayout(self.header)
        self.headerLayout.setObjectName(u"headerLayout")
        self.headerLayout.setContentsMargins(9, 0, 9, 0)
        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.headerLayout.addItem(self.horizontalSpacer_4)

        self.datasetLabel = QLabel(self.header)
        self.datasetLabel.setObjectName(u"datasetLabel")

        self.headerLayout.addWidget(self.datasetLabel)

        self.horizontalSpacer_3 = QSpacerItem(352, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.headerLayout.addItem(self.horizontalSpacer_3)

        self.headerLayout.setStretch(0, 1)
        self.headerLayout.setStretch(2, 1)

        self.verticalLayout_3.addWidget(self.header)

        self.leftContent = QWidget(self.leftContainer)
        self.leftContent.setObjectName(u"leftContent")
        self.leftContent.setMinimumSize(QSize(100, 0))
        self.verticalLayout_2 = QVBoxLayout(self.leftContent)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.mainFrame = QFrame(self.leftContent)
        self.mainFrame.setObjectName(u"mainFrame")
        self.mainFrame.setFrameShape(QFrame.StyledPanel)
        self.mainFrame.setFrameShadow(QFrame.Raised)
        self.mainFrameLayout = QVBoxLayout(self.mainFrame)
        self.mainFrameLayout.setObjectName(u"mainFrameLayout")
        self.mainFrameLayout.setContentsMargins(0, 0, 0, 0)
        self.infoFrame = QFrame(self.mainFrame)
        self.infoFrame.setObjectName(u"infoFrame")
        self.infoFrame.setFrameShape(QFrame.StyledPanel)
        self.infoFrame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_5 = QHBoxLayout(self.infoFrame)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.currentAtomSelectionLabel = QLabel(self.infoFrame)
        self.currentAtomSelectionLabel.setObjectName(u"currentAtomSelectionLabel")

        self.horizontalLayout_5.addWidget(self.currentAtomSelectionLabel)

        self.horizontalSpacer_6 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer_6)

        self.cancelAtomSelectionButton = QPushButton(self.infoFrame)
        self.cancelAtomSelectionButton.setObjectName(u"cancelAtomSelectionButton")

        self.horizontalLayout_5.addWidget(self.cancelAtomSelectionButton)


        self.mainFrameLayout.addWidget(self.infoFrame)

        self.plot3dPH = QWidget(self.mainFrame)
        self.plot3dPH.setObjectName(u"plot3dPH")
        self.plot3dPH.setStyleSheet(u"")

        self.mainFrameLayout.addWidget(self.plot3dPH)

        self.selectedIndicesLabel = QLabel(self.mainFrame)
        self.selectedIndicesLabel.setObjectName(u"selectedIndicesLabel")
        self.selectedIndicesLabel.setAlignment(Qt.AlignCenter)

        self.mainFrameLayout.addWidget(self.selectedIndicesLabel)

        self.nFramesLabel = QLabel(self.mainFrame)
        self.nFramesLabel.setObjectName(u"nFramesLabel")
        self.nFramesLabel.setAlignment(Qt.AlignCenter)

        self.mainFrameLayout.addWidget(self.nFramesLabel)

        self.toolbar = QWidget(self.mainFrame)
        self.toolbar.setObjectName(u"toolbar")
        self.horizontalLayout = QHBoxLayout(self.toolbar)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalSpacer = QSpacerItem(275, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.leftButton = QToolButton(self.toolbar)
        self.leftButton.setObjectName(u"leftButton")

        self.horizontalLayout.addWidget(self.leftButton)

        self.startButton = QToolButton(self.toolbar)
        self.startButton.setObjectName(u"startButton")

        self.horizontalLayout.addWidget(self.startButton)

        self.pauseButton = QToolButton(self.toolbar)
        self.pauseButton.setObjectName(u"pauseButton")

        self.horizontalLayout.addWidget(self.pauseButton)

        self.rightButton = QToolButton(self.toolbar)
        self.rightButton.setObjectName(u"rightButton")

        self.horizontalLayout.addWidget(self.rightButton)

        self.horizontalSpacer_2 = QSpacerItem(275, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer_2)


        self.mainFrameLayout.addWidget(self.toolbar)

        self.mainFrameLayout.setStretch(1, 1)

        self.verticalLayout_2.addWidget(self.mainFrame)

        self.bottomFrame = QFrame(self.leftContent)
        self.bottomFrame.setObjectName(u"bottomFrame")
        self.bottomFrame.setFrameShape(QFrame.StyledPanel)
        self.bottomFrame.setFrameShadow(QFrame.Raised)
        self.verticalLayout_5 = QVBoxLayout(self.bottomFrame)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.bottomHeader = QFrame(self.bottomFrame)
        self.bottomHeader.setObjectName(u"bottomHeader")
        self.bottomHeader.setFrameShape(QFrame.StyledPanel)
        self.bottomHeader.setFrameShadow(QFrame.Raised)
        self.bottomHeaderLayout = QHBoxLayout(self.bottomHeader)
        self.bottomHeaderLayout.setObjectName(u"bottomHeaderLayout")
        self.bottomHeaderLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_8 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.bottomHeaderLayout.addItem(self.horizontalSpacer_8)


        self.verticalLayout_5.addWidget(self.bottomHeader)

        self.bottomTabWidget = QTabWidget(self.bottomFrame)
        self.bottomTabWidget.setObjectName(u"bottomTabWidget")

        self.verticalLayout_5.addWidget(self.bottomTabWidget)


        self.verticalLayout_2.addWidget(self.bottomFrame)

        self.verticalLayout_2.setStretch(0, 1)

        self.verticalLayout_3.addWidget(self.leftContent)


        self.horizontalLayout_3.addWidget(self.leftContainer)

        self.rightContainer = QFrame(Form)
        self.rightContainer.setObjectName(u"rightContainer")
        self.rightContainer.setFrameShape(QFrame.StyledPanel)
        self.rightContainer.setFrameShadow(QFrame.Raised)
        self.rightContainerLayout = QVBoxLayout(self.rightContainer)
        self.rightContainerLayout.setObjectName(u"rightContainerLayout")
        self.sidebarWidget = QTabWidget(self.rightContainer)
        self.sidebarWidget.setObjectName(u"sidebarWidget")
        self.sidebarWidget.setMinimumSize(QSize(300, 0))
        self.sidebarWidget.setMaximumSize(QSize(0, 16777215))
        self.bondsTab = QWidget()
        self.bondsTab.setObjectName(u"bondsTab")
        self.bondsTabLayout = QVBoxLayout(self.bondsTab)
        self.bondsTabLayout.setObjectName(u"bondsTabLayout")
        self.dynamicBondsCB = QCheckBox(self.bondsTab)
        self.dynamicBondsCB.setObjectName(u"dynamicBondsCB")
        self.dynamicBondsCB.setChecked(True)

        self.bondsTabLayout.addWidget(self.dynamicBondsCB)

        self.frame = QFrame(self.bondsTab)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_4 = QHBoxLayout(self.frame)
        self.horizontalLayout_4.setSpacing(0)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.bondsTextEditLabel = QLabel(self.frame)
        self.bondsTextEditLabel.setObjectName(u"bondsTextEditLabel")

        self.horizontalLayout_4.addWidget(self.bondsTextEditLabel)

        self.horizontalSpacer_5 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_4.addItem(self.horizontalSpacer_5)

        self.selectBondsButton = QPushButton(self.frame)
        self.selectBondsButton.setObjectName(u"selectBondsButton")
        self.selectBondsButton.setEnabled(False)

        self.horizontalLayout_4.addWidget(self.selectBondsButton)


        self.bondsTabLayout.addWidget(self.frame)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.bondsTabLayout.addItem(self.verticalSpacer)

        self.sidebarWidget.addTab(self.bondsTab, "")
        self.alignTab = QWidget()
        self.alignTab.setObjectName(u"alignTab")
        self.verticalLayout = QVBoxLayout(self.alignTab)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.alignConfigsCB = QCheckBox(self.alignTab)
        self.alignConfigsCB.setObjectName(u"alignConfigsCB")

        self.verticalLayout.addWidget(self.alignConfigsCB)

        self.frame_2 = QFrame(self.alignTab)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_6 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self.frame_2)
        self.label.setObjectName(u"label")

        self.horizontalLayout_6.addWidget(self.label)

        self.horizontalSpacer_7 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_6.addItem(self.horizontalSpacer_7)

        self.selectAlignAtomsButton = QPushButton(self.frame_2)
        self.selectAlignAtomsButton.setObjectName(u"selectAlignAtomsButton")
        self.selectAlignAtomsButton.setEnabled(False)

        self.horizontalLayout_6.addWidget(self.selectAlignAtomsButton)


        self.verticalLayout.addWidget(self.frame_2)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_2)

        self.sidebarWidget.addTab(self.alignTab, "")
        self.colorTab = QWidget()
        self.colorTab.setObjectName(u"colorTab")
        self.verticalLayout_4 = QVBoxLayout(self.colorTab)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.coloringComboBox = QComboBox(self.colorTab)
        self.coloringComboBox.addItem("")
        self.coloringComboBox.addItem("")
        self.coloringComboBox.setObjectName(u"coloringComboBox")

        self.verticalLayout_4.addWidget(self.coloringComboBox)

        self.colorTabModelFrame = QFrame(self.colorTab)
        self.colorTabModelFrame.setObjectName(u"colorTabModelFrame")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.colorTabModelFrame.sizePolicy().hasHeightForWidth())
        self.colorTabModelFrame.setSizePolicy(sizePolicy)
        self.colorTabModelFrame.setMinimumSize(QSize(0, 0))
        self.colorTabModelFrame.setFrameShape(QFrame.StyledPanel)
        self.colorTabModelFrame.setFrameShadow(QFrame.Raised)
        self.colorTabModelFrameLayout = QHBoxLayout(self.colorTabModelFrame)
        self.colorTabModelFrameLayout.setObjectName(u"colorTabModelFrameLayout")

        self.verticalLayout_4.addWidget(self.colorTabModelFrame)

        self.verticalSpacer_3 = QSpacerItem(20, 876, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_4.addItem(self.verticalSpacer_3)

        self.sidebarWidget.addTab(self.colorTab, "")
        self.imageTab = QWidget()
        self.imageTab.setObjectName(u"imageTab")
        self.verticalLayout_6 = QVBoxLayout(self.imageTab)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.checkBox = QCheckBox(self.imageTab)
        self.checkBox.setObjectName(u"checkBox")

        self.verticalLayout_6.addWidget(self.checkBox)

        self.verticalSpacer_4 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_6.addItem(self.verticalSpacer_4)

        self.sidebarWidget.addTab(self.imageTab, "")

        self.rightContainerLayout.addWidget(self.sidebarWidget)


        self.horizontalLayout_3.addWidget(self.rightContainer)

        self.horizontalLayout_3.setStretch(0, 1)

        self.retranslateUi(Form)

        self.bottomTabWidget.setCurrentIndex(-1)
        self.sidebarWidget.setCurrentIndex(3)


        QMetaObject.connectSlotsByName(Form)
    # setupUi

    def retranslateUi(self, Form):
        Form.setWindowTitle(QCoreApplication.translate("Form", u"Form", None))
        self.datasetLabel.setText(QCoreApplication.translate("Form", u"Dataset:", None))
        self.currentAtomSelectionLabel.setText("")
        self.cancelAtomSelectionButton.setText(QCoreApplication.translate("Form", u"Cancel", None))
        self.selectedIndicesLabel.setText("")
        self.nFramesLabel.setText("")
        self.leftButton.setText("")
        self.startButton.setText("")
        self.pauseButton.setText("")
        self.rightButton.setText("")
        self.dynamicBondsCB.setText(QCoreApplication.translate("Form", u"Dynamic Bonds", None))
        self.bondsTextEditLabel.setText(QCoreApplication.translate("Form", u"Bonds:", None))
        self.selectBondsButton.setText(QCoreApplication.translate("Form", u"Select", None))
        self.sidebarWidget.setTabText(self.sidebarWidget.indexOf(self.bondsTab), QCoreApplication.translate("Form", u"Bonds", None))
        self.alignConfigsCB.setText(QCoreApplication.translate("Form", u"Align Configurations", None))
        self.label.setText(QCoreApplication.translate("Form", u"Align along:", None))
        self.selectAlignAtomsButton.setText(QCoreApplication.translate("Form", u"Select", None))
        self.sidebarWidget.setTabText(self.sidebarWidget.indexOf(self.alignTab), QCoreApplication.translate("Form", u"Align", None))
        self.coloringComboBox.setItemText(0, QCoreApplication.translate("Form", u"Atomic Color", None))
        self.coloringComboBox.setItemText(1, QCoreApplication.translate("Form", u"Force Error", None))

        self.sidebarWidget.setTabText(self.sidebarWidget.indexOf(self.colorTab), QCoreApplication.translate("Form", u"Color", None))
        self.checkBox.setText(QCoreApplication.translate("Form", u"Periodic images", None))
        self.sidebarWidget.setTabText(self.sidebarWidget.indexOf(self.imageTab), QCoreApplication.translate("Form", u"Image", None))
    # retranslateUi

