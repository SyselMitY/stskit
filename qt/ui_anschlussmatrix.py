# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'anschlussmatrix.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_AnschlussmatrixWindow(object):
    def setupUi(self, AnschlussmatrixWindow):
        AnschlussmatrixWindow.setObjectName("AnschlussmatrixWindow")
        AnschlussmatrixWindow.resize(800, 600)
        self.centralwidget = QtWidgets.QWidget(AnschlussmatrixWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.stackedWidget = QtWidgets.QStackedWidget(self.centralwidget)
        self.stackedWidget.setObjectName("stackedWidget")
        self.settings_page = QtWidgets.QWidget()
        self.settings_page.setObjectName("settings_page")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.settings_page)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.formLayout = QtWidgets.QFormLayout()
        self.formLayout.setObjectName("formLayout")
        self.bahnhofLabel = QtWidgets.QLabel(self.settings_page)
        self.bahnhofLabel.setObjectName("bahnhofLabel")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.bahnhofLabel)
        self.bahnhofBox = QtWidgets.QComboBox(self.settings_page)
        self.bahnhofBox.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.bahnhofBox.setObjectName("bahnhofBox")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.bahnhofBox)
        self.verticalLayout_2.addLayout(self.formLayout)
        self.stackedWidget.addWidget(self.settings_page)
        self.display_page = QtWidgets.QWidget()
        self.display_page.setObjectName("display_page")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.display_page)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.displaySplitter = QtWidgets.QSplitter(self.display_page)
        self.displaySplitter.setOrientation(QtCore.Qt.Vertical)
        self.displaySplitter.setObjectName("displaySplitter")
        self.grafikWidget = QtWidgets.QWidget(self.displaySplitter)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.grafikWidget.sizePolicy().hasHeightForWidth())
        self.grafikWidget.setSizePolicy(sizePolicy)
        self.grafikWidget.setObjectName("grafikWidget")
        self.zuginfoLabel = QtWidgets.QLabel(self.displaySplitter)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.zuginfoLabel.sizePolicy().hasHeightForWidth())
        self.zuginfoLabel.setSizePolicy(sizePolicy)
        self.zuginfoLabel.setMaximumSize(QtCore.QSize(16777215, 50))
        self.zuginfoLabel.setBaseSize(QtCore.QSize(0, 0))
        self.zuginfoLabel.setFrameShape(QtWidgets.QFrame.Box)
        self.zuginfoLabel.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.zuginfoLabel.setTextFormat(QtCore.Qt.AutoText)
        self.zuginfoLabel.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.zuginfoLabel.setObjectName("zuginfoLabel")
        self.horizontalLayout.addWidget(self.displaySplitter)
        self.stackedWidget.addWidget(self.display_page)
        self.verticalLayout.addWidget(self.stackedWidget)
        AnschlussmatrixWindow.setCentralWidget(self.centralwidget)
        self.toolBar = QtWidgets.QToolBar(AnschlussmatrixWindow)
        self.toolBar.setIconSize(QtCore.QSize(16, 16))
        self.toolBar.setObjectName("toolBar")
        AnschlussmatrixWindow.addToolBar(QtCore.Qt.TopToolBarArea, self.toolBar)
        self.actionSetup = QtWidgets.QAction(AnschlussmatrixWindow)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/equalizer.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        icon.addPixmap(QtGui.QPixmap(":/equalizer-dis.png"), QtGui.QIcon.Disabled, QtGui.QIcon.Off)
        self.actionSetup.setIcon(icon)
        self.actionSetup.setObjectName("actionSetup")
        self.actionAnzeige = QtWidgets.QAction(AnschlussmatrixWindow)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap(":/slots.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        icon1.addPixmap(QtGui.QPixmap(":/slots-dis.png"), QtGui.QIcon.Disabled, QtGui.QIcon.Off)
        self.actionAnzeige.setIcon(icon1)
        self.actionAnzeige.setObjectName("actionAnzeige")
        self.actionPlusEins = QtWidgets.QAction(AnschlussmatrixWindow)
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap(":/clock--plus.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionPlusEins.setIcon(icon2)
        self.actionPlusEins.setObjectName("actionPlusEins")
        self.actionMinusEins = QtWidgets.QAction(AnschlussmatrixWindow)
        icon3 = QtGui.QIcon()
        icon3.addPixmap(QtGui.QPixmap(":/clock--minus.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionMinusEins.setIcon(icon3)
        self.actionMinusEins.setObjectName("actionMinusEins")
        self.actionFix = QtWidgets.QAction(AnschlussmatrixWindow)
        icon4 = QtGui.QIcon()
        icon4.addPixmap(QtGui.QPixmap(":/clock--pencil.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionFix.setIcon(icon4)
        self.actionFix.setObjectName("actionFix")
        self.actionLoeschen = QtWidgets.QAction(AnschlussmatrixWindow)
        icon5 = QtGui.QIcon()
        icon5.addPixmap(QtGui.QPixmap(":/cross-script.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionLoeschen.setIcon(icon5)
        self.actionLoeschen.setObjectName("actionLoeschen")
        self.actionAnkunftAbwarten = QtWidgets.QAction(AnschlussmatrixWindow)
        icon6 = QtGui.QIcon()
        icon6.addPixmap(QtGui.QPixmap(":/zug-ankunft-abwraten.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionAnkunftAbwarten.setIcon(icon6)
        self.actionAnkunftAbwarten.setObjectName("actionAnkunftAbwarten")
        self.actionAbfahrtAbwarten = QtWidgets.QAction(AnschlussmatrixWindow)
        icon7 = QtGui.QIcon()
        icon7.addPixmap(QtGui.QPixmap(":/zug-abfahrt-abwarten.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionAbfahrtAbwarten.setIcon(icon7)
        self.actionAbfahrtAbwarten.setObjectName("actionAbfahrtAbwarten")
        self.actionWarnungSetzen = QtWidgets.QAction(AnschlussmatrixWindow)
        icon8 = QtGui.QIcon()
        icon8.addPixmap(QtGui.QPixmap(":/flag.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionWarnungSetzen.setIcon(icon8)
        self.actionWarnungSetzen.setObjectName("actionWarnungSetzen")
        self.actionWarnungIgnorieren = QtWidgets.QAction(AnschlussmatrixWindow)
        icon9 = QtGui.QIcon()
        icon9.addPixmap(QtGui.QPixmap(":/flag-green.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionWarnungIgnorieren.setIcon(icon9)
        self.actionWarnungIgnorieren.setObjectName("actionWarnungIgnorieren")
        self.actionWarnungReset = QtWidgets.QAction(AnschlussmatrixWindow)
        icon10 = QtGui.QIcon()
        icon10.addPixmap(QtGui.QPixmap(":/flag-white.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionWarnungReset.setIcon(icon10)
        self.actionWarnungReset.setObjectName("actionWarnungReset")
        self.actionBelegteGleise = QtWidgets.QAction(AnschlussmatrixWindow)
        self.actionBelegteGleise.setCheckable(True)
        self.actionBelegteGleise.setChecked(False)
        self.actionBelegteGleise.setEnabled(True)
        icon11 = QtGui.QIcon()
        icon11.addPixmap(QtGui.QPixmap(":/funnel-small.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        icon11.addPixmap(QtGui.QPixmap(":/funnel-small-dis"), QtGui.QIcon.Disabled, QtGui.QIcon.Off)
        self.actionBelegteGleise.setIcon(icon11)
        self.actionBelegteGleise.setObjectName("actionBelegteGleise")
        self.toolBar.addAction(self.actionSetup)
        self.toolBar.addAction(self.actionAnzeige)
        self.toolBar.addAction(self.actionBelegteGleise)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionWarnungSetzen)
        self.toolBar.addAction(self.actionWarnungIgnorieren)
        self.toolBar.addAction(self.actionWarnungReset)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionPlusEins)
        self.toolBar.addAction(self.actionMinusEins)
        self.toolBar.addAction(self.actionFix)
        self.toolBar.addAction(self.actionAnkunftAbwarten)
        self.toolBar.addAction(self.actionAbfahrtAbwarten)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.actionLoeschen)
        self.bahnhofLabel.setBuddy(self.bahnhofBox)

        self.retranslateUi(AnschlussmatrixWindow)
        self.stackedWidget.setCurrentIndex(1)
        QtCore.QMetaObject.connectSlotsByName(AnschlussmatrixWindow)

    def retranslateUi(self, AnschlussmatrixWindow):
        _translate = QtCore.QCoreApplication.translate
        AnschlussmatrixWindow.setWindowTitle(_translate("AnschlussmatrixWindow", "MainWindow"))
        self.bahnhofLabel.setText(_translate("AnschlussmatrixWindow", "&Bahnhof"))
        self.zuginfoLabel.setText(_translate("AnschlussmatrixWindow", "Zuginfo: (keine Auswahl)"))
        self.toolBar.setWindowTitle(_translate("AnschlussmatrixWindow", "toolBar"))
        self.actionSetup.setText(_translate("AnschlussmatrixWindow", "Setup"))
        self.actionSetup.setToolTip(_translate("AnschlussmatrixWindow", "Gleisauswahl (S)"))
        self.actionSetup.setShortcut(_translate("AnschlussmatrixWindow", "S"))
        self.actionAnzeige.setText(_translate("AnschlussmatrixWindow", "Grafik"))
        self.actionAnzeige.setToolTip(_translate("AnschlussmatrixWindow", "Grafik anzeigen (G)"))
        self.actionAnzeige.setShortcut(_translate("AnschlussmatrixWindow", "G"))
        self.actionPlusEins.setText(_translate("AnschlussmatrixWindow", "+1"))
        self.actionPlusEins.setToolTip(_translate("AnschlussmatrixWindow", "Feste Verspätung +1 Minute auf ausgewähltem Slot (+)"))
        self.actionPlusEins.setShortcut(_translate("AnschlussmatrixWindow", "+"))
        self.actionMinusEins.setText(_translate("AnschlussmatrixWindow", "-1"))
        self.actionMinusEins.setToolTip(_translate("AnschlussmatrixWindow", "Feste Verspätung -1 Minute auf ausgewähltem Slot (-)"))
        self.actionMinusEins.setShortcut(_translate("AnschlussmatrixWindow", "-"))
        self.actionFix.setText(_translate("AnschlussmatrixWindow", "Fix"))
        self.actionFix.setToolTip(_translate("AnschlussmatrixWindow", "Feste Verspätung auf ausgewähltem Slot festlegen (V)"))
        self.actionFix.setShortcut(_translate("AnschlussmatrixWindow", "V"))
        self.actionLoeschen.setText(_translate("AnschlussmatrixWindow", "Löschen"))
        self.actionLoeschen.setToolTip(_translate("AnschlussmatrixWindow", "Korrekturen auf ausgewähltem Slot löschen (Del)"))
        self.actionLoeschen.setShortcut(_translate("AnschlussmatrixWindow", "Del"))
        self.actionAnkunftAbwarten.setText(_translate("AnschlussmatrixWindow", "Ankunft"))
        self.actionAnkunftAbwarten.setToolTip(_translate("AnschlussmatrixWindow", "Kreuzung/Ankunft von zweitem gewählten Zug abwarten (K)"))
        self.actionAnkunftAbwarten.setShortcut(_translate("AnschlussmatrixWindow", "K"))
        self.actionAbfahrtAbwarten.setText(_translate("AnschlussmatrixWindow", "Abfahrt"))
        self.actionAbfahrtAbwarten.setToolTip(_translate("AnschlussmatrixWindow", "Überholung/Abfahrt von zweitem gewählten Zug abwarten (F)"))
        self.actionAbfahrtAbwarten.setShortcut(_translate("AnschlussmatrixWindow", "F"))
        self.actionWarnungSetzen.setText(_translate("AnschlussmatrixWindow", "Warnung"))
        self.actionWarnungSetzen.setToolTip(_translate("AnschlussmatrixWindow", "Slot-Warnung setzen (W)"))
        self.actionWarnungSetzen.setShortcut(_translate("AnschlussmatrixWindow", "W"))
        self.actionWarnungIgnorieren.setText(_translate("AnschlussmatrixWindow", "Ignorieren"))
        self.actionWarnungIgnorieren.setToolTip(_translate("AnschlussmatrixWindow", "Slot-Warnung ignorieren (I)"))
        self.actionWarnungIgnorieren.setShortcut(_translate("AnschlussmatrixWindow", "I"))
        self.actionWarnungReset.setText(_translate("AnschlussmatrixWindow", "Reset"))
        self.actionWarnungReset.setToolTip(_translate("AnschlussmatrixWindow", "Slot-Warnung zurücksetzen (R)"))
        self.actionWarnungReset.setShortcut(_translate("AnschlussmatrixWindow", "R"))
        self.actionBelegteGleise.setText(_translate("AnschlussmatrixWindow", "Belegte Gleise"))
        self.actionBelegteGleise.setToolTip(_translate("AnschlussmatrixWindow", "Nur belegte Gleise anzeigen (B)"))
        self.actionBelegteGleise.setShortcut(_translate("AnschlussmatrixWindow", "B"))

import resources_rc