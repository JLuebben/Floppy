# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'mainwindow.ui'
#
# Created by: PyQt5 UI code generator 5.7
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):

        from floppy.nodeLib import NodeFilter, NodeList
        from floppy.reportWidget import ReportWidget
        import floppy.ressources.icons_rc

        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1250, 910)
        MainWindow.setStyleSheet("MainWindow { background-color: rgb(95,95,95); border-color: black }\n"
"\n"
"QSplitter::handle{background: rgb(55,55,55);}\n"
"QSplitter::handle:horizontal {\n"
"    image: url(:/icons/handleV.png);\n"
"    border-radius: 4px;\n"
"\n"
"}\n"
"\n"
"QSplitter::handle:vertical {\n"
"    image: url(:/icons/handle.png);\n"
"}\n"
"\n"
"\n"
"QMenuBar{background: rgb(75,75,75); border-color: black}\n"
"\n"
"        QMenuBar::item {spacing: 3px; padding: 1px 4px;background: transparent; border-radius: 4px; color: white}\n"
"        QMenuBar::item:selected { /* when selected using mouse or keyboard */\n"
"        background: #a8a8a8;}\n"
"\n"
"        QMenu {\n"
"        background-color: rgb(95,95,95); /* sets background of the menu */\n"
"        border: 1px solid black;\n"
"        }\n"
"\n"
"        QMenu::item {\n"
"        /* sets background of menu item. set this to something non-transparent\n"
"        if you want menu color and menu item color to be different */\n"
"        background-color: transparent;\n"
"        color: white;\n"
"        }\n"
"\n"
"        QMenu::item:selected { /* when user selects item using mouse or keyboard */\n"
"        background-color: rgb(0,85,100);\n"
"        }\n"
"\n"
"\n"
"QToolBar {background: rgb(75,75,75); border:1px solid rgb(55,55,55)}\n"
"        QToolButton { color: white }\n"
"\n"
"QTabWidget::pane { /* The tab widget frame */\n"
"    border-top: 6px solid #414141;\n"
"\n"
"}\n"
"QTabWidget::tab-bar {\n"
"    left: 0px; /* move to the right by 5px */\n"
"}\n"
"\n"
"QTabBar::tab {\n"
"    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,\n"
"                                stop: 0 #626262, stop: 0.4 #626262,\n"
"                                stop: 0.5 #626262, stop: 1.0 #626262);\n"
"    border: 2px solid #414141;\n"
"    border-bottom-color: #414141; /* same as the pane color */\n"
"    border-top-left-radius: 16px;\n"
"    border-top-right-radius: 4px;\n"
"    min-width: 15ex;\n"
"    padding: 3px;\n"
"    padding-right: 8px;\n"
"    color: white;\n"
"}\n"
"\n"
"QTabBar::tab:selected, QTabBar::tab:hover {\n"
"    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,\n"
"                                stop: 0 #414141, stop: 0.4 #414141,\n"
"                                stop: 0.5 #414141, stop: 1.0 #414141);\n"
"}\n"
"\n"
"QTabBar::tab:selected {\n"
"    border-color: #414141;\n"
"    border-bottom-color: #414141; /* same as pane color */\n"
"    margin-top: 0px;\n"
"}\n"
"\n"
"QTabBar::tab:!selected {\n"
"    margin-top: 2px; /* make non-selected tabs look smaller */\n"
"}\n"
"\n"
"QTabBar::close-button {\n"
"    image: url(:/icons/closeTab.png);\n"
"}\n"
"QTabBar::close-button:hover {\n"
"   image: url(:/icons/kill.png);\n"
"}\n"
"\n"
"\n"
"\n"
"NodeFilter {background-color:rgb(75,75,75) ;border:1px solid rgb(0, 0, 0); \n"
"                           border-color:black; color: white }\n"
"\n"
"NodeList {background-color:rgb(75,75,75) ;border:1px solid rgb(0, 0, 0);\n"
"                  border-color:black}\n"
"        NodeList::item {color: white}")
        self.centralWidget = QtWidgets.QWidget(MainWindow)
        self.centralWidget.setObjectName("centralWidget")
        self.gridLayout = QtWidgets.QGridLayout(self.centralWidget)
        self.gridLayout.setContentsMargins(11, 11, 11, 11)
        self.gridLayout.setSpacing(6)
        self.gridLayout.setObjectName("gridLayout")
        self.HorizontalSplitter = QtWidgets.QSplitter(self.centralWidget)
        self.HorizontalSplitter.setOrientation(QtCore.Qt.Horizontal)
        self.HorizontalSplitter.setObjectName("HorizontalSplitter")
        self.DrawArea = QtWidgets.QTabWidget(self.HorizontalSplitter)
        self.DrawArea.setStyleSheet("")
        self.DrawArea.setTabsClosable(True)
        self.DrawArea.setObjectName("DrawArea")
        self.RightContainer = QtWidgets.QWidget(self.HorizontalSplitter)
        self.RightContainer.setEnabled(True)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.RightContainer.sizePolicy().hasHeightForWidth())
        self.RightContainer.setSizePolicy(sizePolicy)
        self.RightContainer.setMaximumSize(QtCore.QSize(450, 16777215))
        self.RightContainer.setBaseSize(QtCore.QSize(0, 0))
        self.RightContainer.setObjectName("RightContainer")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.RightContainer)
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_2.setSpacing(6)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.VerticalSplitter = QtWidgets.QSplitter(self.RightContainer)
        self.VerticalSplitter.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.VerticalSplitter.setOrientation(QtCore.Qt.Vertical)
        self.VerticalSplitter.setObjectName("VerticalSplitter")
        self.TopContainer = QtWidgets.QWidget(self.VerticalSplitter)
        self.TopContainer.setObjectName("TopContainer")
        self.gridLayout_3 = QtWidgets.QGridLayout(self.TopContainer)
        self.gridLayout_3.setContentsMargins(0, 0, 0, 0)
        self.gridLayout_3.setSpacing(6)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.TopLayout = QtWidgets.QVBoxLayout()
        self.TopLayout.setContentsMargins(11, 11, 11, 11)
        self.TopLayout.setSpacing(6)
        self.TopLayout.setObjectName("TopLayout")
        self.FilterEdit = NodeFilter(self.TopContainer)
        self.FilterEdit.setObjectName("FilterEdit")
        self.TopLayout.addWidget(self.FilterEdit)
        self.NodeListView = NodeList(self.TopContainer)
        self.NodeListView.setObjectName("NodeListView")
        self.TopLayout.addWidget(self.NodeListView)
        self.gridLayout_3.addLayout(self.TopLayout, 0, 0, 1, 1)
        self.BottomWidget = ReportWidget(self.VerticalSplitter)
        self.BottomWidget.setObjectName("BottomWidget")
        self.gridLayout_2.addWidget(self.VerticalSplitter, 0, 0, 1, 1)
        self.gridLayout.addWidget(self.HorizontalSplitter, 0, 0, 1, 1)
        MainWindow.setCentralWidget(self.centralWidget)
        self.menuBar = QtWidgets.QMenuBar(MainWindow)
        self.menuBar.setGeometry(QtCore.QRect(0, 0, 1250, 18))
        self.menuBar.setObjectName("menuBar")
        MainWindow.setMenuBar(self.menuBar)
        self.mainToolBar = QtWidgets.QToolBar(MainWindow)
        self.mainToolBar.setObjectName("mainToolBar")
        MainWindow.addToolBar(QtCore.Qt.TopToolBarArea, self.mainToolBar)
        self.statusBar = QtWidgets.QStatusBar(MainWindow)
        self.statusBar.setObjectName("statusBar")
        MainWindow.setStatusBar(self.statusBar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))


if __name__ == "__main__":

    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())


