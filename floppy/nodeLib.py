import logging
from collections import OrderedDict
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from PyQt5.QtGui import *
from floppy.node import NODECLASSES,_NODECLASSES

logger = logging.getLogger("Floppy")

class NodeFilter(QLineEdit):
    """
    Widget for filtering a list of available nodes by user specified characteristics.
    """
    def __init__(self, parent=None):
        super(NodeFilter, self).__init__(parent)
        self.textEdited.connect(self.check)
        self.lastText = ''
        self.setStyleSheet("NodeFilter {background-color:rgb(75,75,75) ;border:1px solid rgb(0, 0, 0); "
                           "border-color:black; color: white }")

    def focusInEvent(self, event):
        """
        This is supposed to selected the whole text whenever the widget is focused. Apparently, things don't work that
        way here.
        :param event: QFocusEvent.
        :return: None
        """
        super(NodeFilter, self).focusInEvent(event)
        self.selectAll()

    def check(self, text):
        """
        Interpret the text in the LineEdit and send the filtered node list to the registered NodeList widget.
        :param text: string that is used for filtering the node list.
        :return: None
        """
        text = text.lower()
        self.lastText = text
        # nodes = [str(node) for node in nodeList if text in str(node).lower()]
        if not text[:1] != '$':
            nodes = [node for node in NODECLASSES.keys() if text in node.lower()]
        else:
            # nodes = set(self.nodeScanner.getHints(text[1:]) + self.nodeScanner.getHints(text[1:], False))
            text = text[1:]
            nodes = set([nodeName for nodeName, node in NODECLASSES.items() if node.matchHint(text[1:])])
        model = QStandardItemModel()
        for node in sorted(nodes):
            item = QStandardItem()
            item.setText(node)
            model.appendRow(item)
        self.listView.setModel(model)

    def reCheck(self):
        self.check(self.lastText)

    def registerNodeListLayout(self, layout, widget):
        """
        Do I still need this? It doesn't look like it.
        :param layout:
        :param widget:
        :return:
        """
        self.check('')
        # print layout.children()

    def registerListView(self, view):
        """
        Establishes a reference to the NodeList instance used for displaying the filtering results.
        :param view: Reference to a NodeList instance.
        :return: None
        """
        self.listView = view
        self.check('')

    def getSelectedNode(self):
        """
        Do I still need this? It doesn't look like it.
        """
        pass

    def keyPressEvent(self, event):
        """
        Handling navigation through the nodeLib widgets by key presses.
        :param event: QKeyEvent.
        :return: None
        """
        super(NodeFilter, self).keyPressEvent(event)
        self.parent().keyPressEvent(event)
        if event.key() == Qt.Key_Down:
            self.listView.setFocus()
            self.listView.setCurrentIndex(self.listView.model().index(0, 0))


class NodeList(QListView):
    """
    Widget for displaying the available (and filtered) list of nodes and handling drag&drop spawning of nodes.
    """
    def __init__(self,  parent=None):
        super(NodeList, self).__init__(parent)
        self.filter = None
        self.graph = None
        self.down = False
        self.selectedClass = None
        self.setStyleSheet('''
        NodeList {background-color:rgb(75,75,75) ;border:1px solid rgb(0, 0, 0);
                  border-color:black}
        NodeList::item {color: white}
        ''')

    def setup(self, nodeFilter, graph):
        self.filter = nodeFilter
        self.graph = graph
        self.filter.registerListView(self)

    def mousePressEvent(self, event):
        """
        Handling drag&drop of nodes in the list into the diagram.
        :param event: QMouseEvent
        :return: None
        """
        if not self.down:
            super(NodeList, self).mousePressEvent(event)
            self.down = True
            name = self.filter.listView.selectedIndexes()[0].data()
            print(name,"\n",name in NODECLASSES,'\n',NODECLASSES)
            self.selectedClass = NODECLASSES[name]
            # self.blockSignals(True)
            # self.selectionChanged()
            try:
                floppy.floppyUi.mainWindow.getPainter().reportWidget.updateReport(self.selectedClass.classReport())
            except AttributeError:
                pass


    def mouseReleaseEvent(self, event):
        """
        Handling drag&drop of nodes in the list into the diagram.
        :param event: QMouseEvent
        :return: None
        """
        super(NodeList, self).mouseReleaseEvent(event)
        self.down = False
        if event.pos().x() < 0:
            # transform = self.graph.painter.transform
            pos = QCursor.pos()
            try:
                topLeft = floppy.floppyUi.mainWindow.getPainter().mapToGlobal(floppy.floppyUi.mainWindow.getPainter().pos())
            except AttributeError:
                pass
            else:
                pos -= topLeft

                pos -= floppy.floppyUi.mainWindow.getPainter().center
                # pos -= self.graph.painter.center
                # print(pos, self.graph.painter.center, pos*transform)
                pos /= floppy.floppyUi.mainWindow.getPainter().scale
                # print(transform)

                floppy.floppyUi.mainWindow.getGraph().spawnNode(self.selectedClass, position=(pos.x(), pos.y()))
                floppy.floppyUi.mainWindow.getGraph().update()


    def mouseMoveEvent(self, event):
        """
        Handling drag&drop of nodes in the list into the diagram.
        :param event: QMouseEvent
        :return: None
        """
        if not self.down:
            super(NodeList, self).mouseMoveEvent(event)


class ContextNodeList(NodeList):
    """
    A NodeList widget adapted to work in the context menu created when dragging a connection into open space in the
    diagram.
    """
    def registerDialog(self, dialog):
        """
        Establish a reference to the context menu holding the widget.
        :param dialog: Reference to a NodeDialog instance
        :return: None
        """
        self.dialog = dialog

    def registerGraph(self, graph):
        self.graph = graph

    def registerPainter(self, painter):
        self.painter = painter
        self.down = False

    # def mousePressEvent(self, event):
    #     """
    #     Handling drag&drop of nodes in the list into the diagram.
    #     :param event: QMouseEvent
    #     :return: None
    #     """
    #     # super(NodeList, self).mousePressEvent(event)
    #     self.down = True
    #     name = self.filter.listView.selectedIndexes()[0].data()
    #     self.selectedClass = NODECLASSES[name]

    def mouseReleaseEvent(self, event):
        """
        Handling the selection and spawning of nodes in the list.
        :param event: QMouseEvent.
        :return: None
        """
        super(ContextNodeList, self).mouseReleaseEvent(event)
        painter = floppy.floppyUi.mainWindow.getPainter()
        # pos = QCursor.pos()
        pos = self.parent().mapToGlobal(self.parent().pos())
        topLeft = painter.mapToGlobal(painter.pos())
        pos -= topLeft

        pos -= painter.center
        pos /= painter.scale
        floppy.floppyUi.mainWindow.getGraph().spawnNode(self.selectedClass, position=(pos.x(), pos.y()))
        self.down = False
        floppy.floppyUi.mainWindow.getGraph().requestUpdate()
        self.dialog.close(True)

    def keyPressEvent(self, event):
        """
        Handling the selection and spawning of nodes in the list.
        :param event: QMouseEvent.
        :return: None
        """
        super(ContextNodeList, self).keyPressEvent(event)
        if event.key() == Qt.Key_Return:
            painter = floppy.floppyUi.mainWindow.getPainter()
            graph = floppy.floppyUi.mainWindow.getGraph()
            name = self.filter.listView.selectedIndexes()[0].data()
            self.selectedClass = NODECLASSES[name]
            pos = self.parent().mapToGlobal(self.parent().pos())
            topLeft = painter.mapToGlobal(painter.pos())
            pos -= topLeft

            pos -= painter.center
            pos /= painter.scale
            graph.spawnNode(self.selectedClass, position=(pos.x()-5, pos.y()-40))
            self.down = False
            graph.requestUpdate()
            self.dialog.close(True)


class ContextNodeFilter(NodeFilter):
    """
    A NodeFilter widget adapted to work in the context menu created when dragging a connection into open space in the
    diagram.
    """
    def registerDialog(self, dialog, back=False):
        """
        Establish a reference to the context menu holding the widget and specifying whether a connection to an InputPin
        or an OutputPin is about to be established.
        :param dialog: Reference to a NodeDialog instance
        :param back: boolean. True if the newly created node will be connected to the nodes input. False if otherwise.
        :return: None
        """
        self.dialog = dialog
        self.back = back

    def check(self, text):
        """
        Adapted method from base class to do hinting by default.
        :param text: string interpreted for filtering the node list.
        :return: None
        """
        try:
            text = text.lower()
        except AttributeError:
            text = ''
        # nodes = [str(node) for node in nodeList if text in str(node).lower()]
        if self.dialog.cB.checkState():
            if text:
                text = '$' + text
            else:
                text = '$' + self.dialog.getTypeHint()
        if not text.startswith('$'):
            nodes = [node for node in NODECLASSES.keys() if text in node.lower()]
        else:
            text = text[1:]
            nodes = set([nodeName for nodeName, node in NODECLASSES.items() if node.matchHint(text)])
        model = QStandardItemModel()
        for node in sorted(nodes):
            item = QStandardItem()
            item.setText(node)
            model.appendRow(item)
        self.listView.setModel(model)

import floppy.floppyUi
