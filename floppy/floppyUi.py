import json
import os
import time
from copy import deepcopy
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QPoint, QSettings
from PyQt5.Qt import QTimer
from collections import OrderedDict
import platform
import logging
from floppy.graph import Graph
from floppy.node import (
    MetaNode,ControlNode, DynamicNode,SubGraph,
    _NODECLASSES,NODECLASSES, ismanaged, isnotmanaged,validatenodename,
    ManagedNodeError,SaveNodesError,NodeUpdateError,InputAlreadySet,InputNotAvailable
)
#from floppy.Nodes.floppyBaseNodes import ControlNode, DynamicNode
from floppy.ressources.mainWindow import Ui_MainWindow
from floppy.floppySettings import SettingsDialog
from floppy.nodeLib import ContextNodeFilter, ContextNodeList
from floppy.FloppyTypes import FLOPPYTYPEMAP
import traceback
from pprint import pprint

logger = logging.getLogger('Floppy')

mainWindow = None

LOCALPORT = 8080
PINSIZE = 8
NODETITLEFONTSIZE = 12
CONNECTIONLINEWIDTH = 2
NODEWIDTHSCALE = 100
if platform.system() is 'Windows':
    TEXTYOFFSET = 4
    LINEEDITFONTSIZE = 7
else:
    TEXTYOFFSET = 0
    LINEEDITFONTSIZE = 8


class Painter(QWidget):
    def decorateNode(self, node, position):
        return node


class Painter2D(Painter):
    PINCOLORS = {
        None.__class__: QColor(128,128,128),# This is only used for NodeWizard to display dummy input and oputput
        str: QColor(255, 190, 0),
        int: QColor(0, 115, 130),
        float: QColor(0, 200, 0),
        object: QColor(190, 190, 190),
        bool: QColor(190, 0, 0),
    }
    nodes = []
    scale = 1.
    globalOffset = QPoint(0, 0)
    drag = False
    inputPinPositions = []
    clickedPin = None
    clickedNode = None
    nodePoints = []
    downOverNode = False
    
    def __init__(self, parent=None):
        super(Painter2D, self).__init__(parent)
        self.stretch = 0
        self.setMouseTracking(True)
        self.timer = QTimer()
        self.timer.timeout.connect(self.checkGraph)
        self.timer.start(500)
        self.setFocusPolicy(Qt.ClickFocus)
        self.graph = None
        self.shiftDown = False
        self.looseConnection = None
        self.reportWidget = None
        self.pinPositions = {}
        self.drawItems = []
        self.drawItemsOfNode = {}
        self.watchingItems = []
        self.triggers = set()
        self.contextSensitive = False
        self.rightClickedNode = None
        self.lastReport = None

        self.mouseDownPos = None
        self.dialog = None
        self.relayTo = None
        self.selectFrame = None
        self.selectFrame_End = None
        self.selectedSubgraph = ('main', None)
        self.groupSelection = []
        self.reset()

    def groupSelected(self):
        return len(self.groupSelection)

    def reset(self):
        self.nodes = []
        self.triggers = set()
        self.graph = None
        self.shiftDown = False
        self.looseConnection = None
        self.reportWidget = None
        self.pinPositions = {}
        self.drawItems = []
        self.drawItemsOfNode = {}
        self.watchingItems = []
        self.rightClickedNode = None
        self.lastReport = None
        self.contextSensitive = True

        self.contextSensitive = False

        self.mouseDownPos = None
        self.dialog = None
        self.relayTo = None
        self.selectFrame = None
        self.selectFrame_End = None
        self.selectedSubgraph = ('main', None)
        self.groupSelection = []

    def createSubgraph(self, name):
        subgraph = set()
        relayInputs = set()
        for node in self.groupSelection:
            node.subgraph = name
            subgraph.add(node)
        allInputs = [i for i in self.getAllInputsOfSubgraph(name)]
        for inp in allInputs:
            if inp.name == 'TRIGGER':
                continue
            con = self.graph.getConnectionOfInput(inp)
            if con:
                outNode = con.outputNode
                if not outNode in subgraph:
                    relayInputs.add((inp, outNode, con.outputName))
            else:
                relayInputs.add((inp, None, None))

        relayOutputs = set()
        allOutputs = self.getAllOutputsOfSubgraph(name)
        for out in allOutputs:
            cons = self.graph.getConnectionsOfOutput(out)
            if cons:
                for con in cons:
                    inpNode = con.inputNode
                    if not inpNode in subgraph:
                        relayOutputs.add((out, inpNode, con.inputName))
                        break
            else:
                relayOutputs.add((out, None, None))
        # print('xxx', self.graph.toJson(subgraph=name))
        # print([i for i in relayInputs])
        relayOutputs = sorted(relayOutputs, key=lambda item: item[0].name)
        relayInputs = sorted(relayInputs, key=lambda item: item[0].name)
        pos = self.mapToGlobal(self.parent().pos())
        topLeft = self.mapToGlobal(self.pos())
        pos -= topLeft
        # pos -= self.center
        pos /= self.scale
        newNode = self.graph.createSubGraphNode(name, self.graph.toJson(subgraph=name), relayInputs,
                                                relayOutputs, spawnAt=(pos.x(), pos.y()))
        self.update()


    def setSelectedSubgraph(self, graph, parent=None):
        if not parent:
            parent = self.selectedSubgraph[0]
        self.selectedSubgraph = (graph, parent)

    def getAllSubgraphs(self):
        return {node.subgraph for node in self.nodes}

    def getAllInputsOfSubgraph(self, subgraph=None):
        if not subgraph:
            subgraph = self.selectedSubgraph[0]
        inputs = {node.inputs.values() for node in self.nodes if node.subgraph == subgraph}
        return [j for i in inputs for j in i]

    def getAllOutputsOfSubgraph(self, subgraph=None):
        if not subgraph:
            subgraph = self.selectedSubgraph[0]
        outputs = {node.outputs.values() for node in self.nodes if node.subgraph == subgraph}
        return [j for i in outputs for j in i]

    def checkGraph(self):
        if not self.graph:
            return
        if self.graph.needsUpdate():
            self.update()

    def relayInputEventsTo(self, drawItem):
        self.relayTo = drawItem

    def stopInputRelayingTo(self, drawItem):
        if self.relayTo == drawItem:
            self.relayTo = None

    def registerWatchingItem(self, item):
        self.watchingItems.append(item)

    def removeWatchingItem(self, item):
        self.watchingItems.remove(item)

    def registerGraph(self, graph):
        self.graph = graph

    def keyPressEvent(self, event):
        super(Painter2D, self).keyPressEvent(event)
        if self.relayTo:
            self.relayTo.keyPressEvent(event)
        if event.key() == 16777248:
            self.shiftDown = True

    def keyReleaseEvent(self, event):
        super(Painter2D, self).keyReleaseEvent(event)
        if event.key() == 16777248:
            self.shiftDown = False

    def wheelEvent(self, event):
        # self.scale += event.deltaX()
        up = event.angleDelta().y()>0
        if up:
            x = 1.1
        else:
            x = .9
        self.scale *= x
        self.repaint()  # Dirty trick to make sure the connection beziers are drawn at the same zoom level as the nodes.
        self.update()

    def mousePressEvent(self, event):
        if self.dialog:
            self.dialog.close()
            self.dialog = None
        self.mouseDownPos = event.pos()
        if event.button() == Qt.RightButton:
            self.rightClickedNode = None
            for nodePoints in self.nodePoints:
                x1 = nodePoints[0].x()
                x2 = nodePoints[1].x() #+ x1
                y1 = nodePoints[0].y()
                y2 = nodePoints[1].y() #+ y1
                xx = event.pos()
                yy = xx.y()
                xx = xx.x()
                if x1 < xx < x2 and y1 < yy < y2:
                    self.rightClickedNode = nodePoints[-1]
                    break
            if not self.rightClickedNode:
                self.drag = event.pos()

        if event.button() == Qt.LeftButton:

            for item in self.watchingItems:
                item.watchDown(event.pos())
                item.collide(event.pos())
                return

            for drawItem in self.drawItems:
                if issubclass(type(drawItem), Selector) or issubclass(type(drawItem), LineEdit):
                    if drawItem.collide(event.pos()):
                        break

            for point, i in self.inputPinPositions:
                # print(event.pos(), point, i)
                if abs(event.pos().x() - point.x()) < PINSIZE * self.scale and abs(event.pos().y() - point.y()) < PINSIZE * self.scale:
                    self.clickedPin = i
                    if self.shiftDown:
                        self.graph.removeConnection(i)
                    self.update()
                    return
            for point, i in self.outputPinPositions:
                # print(event.pos(), point, i)
                # w = node.__size__[0]*100
                if abs(event.pos().x() - point.x()) < PINSIZE * self.scale and abs(event.pos().y() - point.y()) < PINSIZE * self.scale:
                    self.clickedPin = i
                    if self.shiftDown:
                        self.graph.removeConnection(i)
                    self.update()
                    return
            for nodePoints in self.nodePoints:
                x1 = nodePoints[0].x()
                x2 = nodePoints[1].x() #+ x1
                y1 = nodePoints[0].y()
                y2 = nodePoints[1].y() #+ y1
                xx = event.pos()
                yy = xx.y()
                xx = xx.x()
                if x1 < xx < x2 and y1 < yy < y2:
                    self.clickedNode = nodePoints[-1]
                    self.graph.requestReport(self.clickedNode.ID)
                    # print(self.clickedNode)
                    self.update()
                    self.downOverNode = event.pos()
                    return
            self.groupSelection = []
            self.selectFrame = event.pos() + (event.pos() - self.center) * (1-self.scale) * 1/self.scale
            self._selectFrame = event.pos()


    def getOutputPinAt(self, pos):
        for point, pin in self.outputPinPositions:
            if abs(pos.x() - point.x()) < 7 * self.scale and abs(pos.y() - point.y()) < 7 * self.scale:
                return pin

    def getInputPinAt(self, pos):
        for point, pin in self.inputPinPositions:
            if abs(pos.x() - point.x()) < 7 * self.scale and abs(pos.y() - point.y()) < 7 * self.scale:
                return pin

    def mouseReleaseEvent(self, event):
        super(Painter2D, self).mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton and self.looseConnection and self.clickedPin:
            valid = True
            if ':I' in self.clickedPin:
                inputNodeID, _, inputName = self.clickedPin.partition(':I')
                try:
                    outputNodeID, _, outputName = self.getOutputPinAt(event.pos()).partition(':O')
                except AttributeError:
                    valid = False
            else:
                outputNodeID, _, outputName = self.clickedPin.partition(':O')
                try:
                    inputNodeID, _, inputName = self.getInputPinAt(event.pos()).partition(':I')
                except AttributeError:
                    valid = False
            if valid:
                try:
                    self.graph.connect(outputNodeID, outputName, inputNodeID, inputName)
                except TypeError:
                    print('Cannot connect pins of different type')
            else:
                if not self.shiftDown and (abs((event.pos()-self.mouseDownPos).x()) > 10 or
                                                   abs((event.pos()-self.mouseDownPos).y()) > 10):
                    # print('Do something. NOW!!!')
                    self.openDialog(event)
            self.looseConnection = False
            self.clickedPin = None
        self.drag = False
        self.downOverNode = False

        if self.selectFrame and self.selectFrame_End:
            x1, x2 = self._selectFrame.x(), self._selectFrame_End.x()
            if x1 > x2:
                x2, x1 = x1, x2
            y1, y2 = self._selectFrame.y(), self._selectFrame_End.y()
            if y1 > y2:
                y2, y1 = y1, y2
            # x1 += self.globalOffset.x()
            # print(x1, '     ', self.globalOffset.x(), '    ', event.pos().x())
            # x2 += self.globalOffset.x()
            # y1 += self.globalOffset.y()
            # y2 += self.globalOffset.y()
            self.groupSelection = self.massNodeCollide(x1, y1,
                                                       x2, y2)
        self.selectFrame = None
        self.selectFrame_End = None
        self.repaint()
        self.update()

    def massNodeCollide(self, x, y, xx, yy):
        nodes = []
        for nodePoints in self.nodePoints:
            x1 = nodePoints[0].x()
            x2 = nodePoints[1].x() #+ x1
            y1 = nodePoints[0].y()
            y2 = nodePoints[1].y() #+ y1
            if x < x1 < xx and y < y1 < yy and x < x2 < xx and y < y2 < yy:
                nodes.append(nodePoints[-1])
                # print(self.clickedNode)
        return nodes


    def openDialog(self, event):
        dialog = NodeDialog(self, event, self.clickedPin, self.graph)
        self.dialog = dialog
        dialog.show()

    def mouseMoveEvent(self, event):
        for drawItem in self.watchingItems:
            drawItem.watch(event.pos())
        super(Painter2D, self).mouseMoveEvent(event)

        if self.drag:
            self.globalOffset += event.pos()-self.drag
            self.drag = event.pos()
            # self.repaint()
            self.update()
        if self.downOverNode:
            if self.groupSelection:
                for node in self.groupSelection:
                    newPos = (event.pos() - self.downOverNode)*self.scale**-1
                    oldPos = QPoint(node.__pos__[0], node.__pos__[1])
                    newPos = oldPos + newPos
                    node.__pos__ = (newPos.x(), newPos.y())
                self.downOverNode = event.pos()
                self.update()
            else:
                node = self.clickedNode
                newPos = (event.pos() - self.downOverNode)*self.scale**-1
                oldPos = QPoint(node.__pos__[0], node.__pos__[1])
                newPos = oldPos + newPos
                node.__pos__ = (newPos.x(), newPos.y())
                self.downOverNode = event.pos()
                self.update()

        else:
            self.drawLooseConnection(event.pos())
            self.update()
        if self.selectFrame:
            self.selectFrame_End = event.pos() + (event.pos() - self.center) * (1-self.scale) * 1/self.scale
            self._selectFrame_End = event.pos()

    def getSelectedNode(self):
        return self.clickedNode

    def contextMenuEvent(self, event):
        node = self.rightClickedNode
        if not node:
            return None
        menu = QMenu(self)
        if not node in self.triggers:
            triggerAction = menu.addAction('Add Trigger')
            action = menu.exec_(self.mapToGlobal(event.pos()))
            if action == triggerAction:
                self.triggers.add(node)
        else:
            triggerAction = menu.addAction('Remove Trigger')
            action = menu.exec_(self.mapToGlobal(event.pos()))
            if action == triggerAction:
                self.triggers.discard(node)
        return None

    def paintEvent(self, event):
        # before = time.time()
        self.inputPinPositions = []
        self.outputPinPositions = []
        self.nodePoints = []
        super(Painter2D, self).paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.HighQualityAntialiasing)
        self.drawGrid(painter)
        try:
            self.drawConnections(painter)
        except IOError:
            pass

        painter.translate(self.width()/2. + self.globalOffset.x(), self.height()/2. + self.globalOffset.y())
        self.center = QPoint(self.width()/2. + self.globalOffset.x(), self.height()/2. + self.globalOffset.y())
        painter.scale(self.scale, self.scale)
        #painter.translate(self.width()/2., self.height()/2.)
        painter.setRenderHint(QPainter.HighQualityAntialiasing)
        # painter.drawEllipse(QPoint(0,0),5,5)
        history, last = self.graph.getExecutionHistory()
        running = self.graph.getRunningNodes()
        report = self.graph.getReport()
        if report and not report == self.lastReport:
            try:
                returnValue = report[1]
                mb = QMessageBox(self)
                v, n = returnValue
                mb.setText('"{}"'.format(str(v)) + '\nby {}'.format(n))
                mb.setWindowTitle('Return Value')
                mb.setStandardButtons(QMessageBox.Ok)
                mb.show()
                mainWindow.setFloppyReturnValue(returnValue)
                self.lastReport = report
            except TypeError:
                self.reportWidget.updateReport(report)
                self.lastReport = report
            except KeyError:
                self.reportWidget.updateReport(report)
                self.lastReport = report

        lastDraws = []
        halfPinSize = PINSIZE//2

        for j, node in enumerate(self.nodes):
            if issubclass(type(node), SubGraph):
                node.probeGraph()
                self.updateDrawItems(node)
            if not self.selectedSubgraph[0] == node.subgraph:
                continue
            j *= 3
            j += 1
            pen = QPen()
            pen.setWidth(2)
            painter.setBrush(QColor(55, 55, 55))
            if self.clickedNode == node or node in self.groupSelection:
                # pen.setColor(Qt.green)
                painter.setBrush(QColor(75, 75, 75))
            if node.ID in history:
                # if node.ID in history:
                #     pen.setColor(QColor(175,175,175))
                # else:
                #     pen.setColor(QColor(125, 125, 125))
                if node.ID == last[0]:
                    pen.setColor(Qt.white)
                else:
                    dT = history[node.ID]
                    c = int(17*(15-dT))
                    pen.setColor(QColor(0, c, c))
            elif node.ID in running:
                pen.setColor(Qt.red)
            else:
                pen.setColor(Qt.black)

            font = QFont('Helvetica', 12)
            painter.setFont(font)
            path = QPainterPath()
            x = node.__pos__[0]# + self.globalOffset.x()
            y = node.__pos__[1]# + self.globalOffset.y()
            w = node.__size__[0]*NODEWIDTHSCALE
            h = node.__size__[1]*(8+PINSIZE)+40 + self.stretch

            path.addRoundedRect(x, y, w, h, 50, 5)
            self.nodePoints.append((QPoint(x, y)*painter.transform(), QPoint(x+w, y+h)*painter.transform(), node))
            painter.setPen(pen)

            painter.fillPath(path, QColor(55,55,55))
            # painter.drawRoundedRect(node.pos[0], node.pos[1], node.size[0], node.size[1], 50, 5)
            painter.drawPath(path)
            pen.setColor(QColor(150, 150, 150))
            painter.setFont(QFont('Helvetica', NODETITLEFONTSIZE))
            painter.setPen(pen)
            painter.drawText(x, y+3, w, h, Qt.AlignHCenter, node.__class__.__name__)
            painter.setBrush(QColor(40, 40, 40))
            drawOffset = 25
            #pprint(('dre',self.drawItemsOfNode))
            # for i, inputPin in enumerate(node.inputPins.values()):
            for i, drawItem in enumerate(self.drawItemsOfNode[node]['inp']):
                inputPin = drawItem.data
                if inputPin.name == 'TRIGGER':
                    if not node in self.triggers and not inputPin.info.connected:
                        drawItem.update(x, y+drawOffset+8, w, h, painter.transform())
                        drawItem.deactivate()
                        drawOffset += (8 + PINSIZE)
                        continue
                    else:
                        self.triggers.add(node)
                        drawItem.activeate()
                # pen.setColor(QColor(255, 190, 0))
                if inputPin.ID == self.clickedPin:
                    pen.setColor(Qt.red)
                else:
                    try:
                        pen.setColor(Painter2D.PINCOLORS[inputPin.info.varType])
                    except KeyError:
                        Painter2D.PINCOLORS[inputPin.info.varType] = QColor(*inputPin.info.varType.color)
                        pen.setColor(Painter2D.PINCOLORS[inputPin.info.varType])
                        #pen.setColor(Painter2D.PINCOLORS[inputPin.info.varType])
                        #pen.setColor(QColor(*inputPin.info.varType.color))
                pen.setWidth(2)
                painter.setPen(pen)
                if inputPin.name == 'Control':
                    painter.drawEllipse(x-halfPinSize+w/2., y-halfPinSize, PINSIZE, PINSIZE)
                    point = QPoint(x+w/2., y) * painter.transform()
                    self.inputPinPositions.append((point, inputPin.ID))
                    continue
                else:
                    if inputPin.info.list:
                        painter.drawRect(x-halfPinSize, y+drawOffset+PINSIZE, PINSIZE, PINSIZE)
                    else:
                        painter.drawEllipse(x-halfPinSize, y+drawOffset+PINSIZE, PINSIZE, PINSIZE)
                    point = QPoint(x, y+drawOffset+4+PINSIZE) * painter.transform()
                # self.pinPositions.append((point, i+j))
                self.inputPinPositions.append((point, inputPin.ID))
                # drawOffset += 16
                drawOffset += (8 + PINSIZE)
                drawItem.update(x, y+drawOffset+8, w, h, painter.transform())
                if self.graph.getConnectionOfInput(inputPin):
                    text = inputPin.name
                    drawItem.draw(painter, asLabel=text)
                    # self.drawLabel(x, y+drawOffset+8, w, h, text, painter, Qt.AlignLeft)
                else:
                    item = drawItem.draw(painter)
                    if item:
                        lastDraws.append(item)

            # for k, outputPin in enumerate(node.outputPins.values()):
            finalBuffer = None
            for k, drawItem in enumerate(self.drawItemsOfNode[node]['out']):
                outputPin = drawItem.data
                # pen.setColor(QColor(0, 115, 130))
                try:
                    pen.setColor(Painter2D.PINCOLORS[outputPin.info.varType])
                except KeyError:
                    pen.setColor(QColor(*outputPin.info.varType.color))
                pen.setWidth(2)
                painter.setPen(pen)
                if outputPin.ID == self.clickedPin:
                    pen.setColor(Qt.red)
                    painter.setPen(pen)
                if outputPin.name == 'Final':
                    finalBuffer = (k, drawItem)
                    continue
                    # painter.drawEllipse(x-4+w/2., y+10+drawOffset, 8, 8)
                    # point = QPoint(x+w/2., y+drawOffset+14) * painter.transform()
                    # self.outputPinPositions.append((point, outputPin.ID))
                    # continue
                else:
                    if outputPin.info.list:
                        painter.drawRect(x + w-halfPinSize, y+drawOffset+PINSIZE, PINSIZE, PINSIZE)
                    else:
                        painter.drawEllipse(x + w-halfPinSize, y+drawOffset+PINSIZE, PINSIZE, PINSIZE)
                    point = QPoint(x + w-4, y+drawOffset+4+PINSIZE) * painter.transform()
                # drawOffset += 16
                drawOffset += (8 + PINSIZE)
                self.outputPinPositions.append((point, outputPin.ID))
                if not outputPin.info.select:
                    text = outputPin.name
                    # self.drawLabel(x, y+drawOffset+8, w, h, text, painter, Qt.AlignRight)
                else:
                    text = outputPin.name
                    # self.drawSelector(x, y+drawOffset+8, w, h, text, painter, Qt.AlignRight)
                drawItem.update(x, y+drawOffset+8, w, h, painter.transform())
                drawItem.draw(painter)
            if finalBuffer:
                k, drawItem = finalBuffer
                outputPin = drawItem.data
                pen.setColor(Painter2D.PINCOLORS[outputPin.info.varType])
                pen.setWidth(2)
                painter.setPen(pen)
                if outputPin.ID == self.clickedPin:
                    pen.setColor(Qt.red)
                    painter.setPen(pen)
                painter.drawEllipse(x-halfPinSize+w/2., y+10-int(PINSIZE/10)+drawOffset, PINSIZE, PINSIZE)
                point = QPoint(x+w/2., y+drawOffset+14) * painter.transform()
                self.outputPinPositions.append((point, outputPin.ID))

            # trans = painter.transform()
        self.pinPositions = {value[1]: value[0] for value in self.inputPinPositions+self.outputPinPositions}
        # self.drawConnections(painter)
        self.transform = painter.transform()
        self.transform = painter.transform()
        for item in lastDraws:
            item.draw(painter, last=True)

        if self.selectFrame and self.selectFrame_End:
            painter.setBrush(QColor(255,255,255,25))
            painter.setPen(Qt.white)
            x = self.selectFrame.x()
            y = self.selectFrame.y()
            xx = self.selectFrame_End.x() - x
            yy = self.selectFrame_End.y() - y
            painter.translate(-self.width()/2. - self.globalOffset.x(), -self.height()/2. - self.globalOffset.y())
            painter.drawRect(x, y, xx, yy)
            painter.translate(self.width()/2. + self.globalOffset.x(), self.height()/2. + self.globalOffset.y())


    def drawConnections(self, painter):
        if not self.graph:
            print('No graph connected yet.')
            return
        if not self.pinPositions:
            return

        if self.looseConnection and self.clickedPin:
            start = self.pinPositions[self.clickedPin]
            if ':I' in self.clickedPin:
                start, end = self.looseConnection, start
            else:
                end = self.looseConnection
            self.drawBezier(start, end, Qt.white, painter)

        for outputNode, connList in self.graph.connections.items():
            for info in connList:
                outputID = outputNode.getOutputID(info['outputName'])
                inputID = info['inputNode'].getInputID(info['inputName'])
                varType = outputNode.getOutputInfo(info['outputName']).varType
                start = self.pinPositions[outputID]
                end = self.pinPositions[inputID]
                try:
                    color = Painter2D.PINCOLORS[varType]
                except KeyError:
                    color = QColor(*varType.color)
                rotate = None
                if issubclass(type(info['inputNode']), ControlNode) and info['inputName'] == 'Control':
                    rotate = 'input'
                    if issubclass(type(info['outputNode']), ControlNode) and info['outputName'] == 'Final':
                        rotate = 'both'
                elif issubclass(type(info['outputNode']), ControlNode) and info['outputName'] == 'Final':
                    rotate = 'output'
                self.drawBezier(start, end, color, painter, rotate)

    def drawLooseConnection(self, position):
        self.looseConnection = position

    def drawBezier(self, start, end, color, painter, rotate=None):
                pen = QPen()
                pen.setColor(color)
                pen.setWidth(CONNECTIONLINEWIDTH*self.scale)
                painter.setPen(pen)
                path = QPainterPath()
                path.moveTo(start)
                diffx = abs((start.x()-end.x())/2.)
                if diffx < 100 * self.scale:
                    diffx = 100 * self.scale
                if rotate == 'input':
                    p21 = start.x()+diffx
                    p22 = start.y()
                    p31 = end.x()
                    p32 = end.y() - 100*self.scale
                elif rotate == 'output':
                    p21 = start.x()
                    p22 = start.y() + 100 * self.scale
                    p31 = end.x()-diffx
                    p32 = end.y()
                elif rotate == 'both':
                    p21 = start.x()
                    p22 = start.y() + 100 * self.scale
                    p31 = end.x()
                    p32 = end.y() - 100*self.scale
                else:
                    p21 = start.x()+diffx
                    p22 = start.y()
                    p31 = end.x()-diffx
                    p32 = end.y()
                path.cubicTo(p21, p22, p31, p32, end.x(), end.y())
                painter.drawPath(path)


    def registerNode(self, node, position, silent=False):
        print("register node",node,node.__class__.__name__)

        #from PyQt5.QtCore import pyqtRemoveInputHook,pyqtRestoreInputHook
        #pyqtRemoveInputHook()
        #import pdb
        #pdb.set_trace()

        if not silent:
            # self.parent().parent().parent().parent().parent().statusBar.showMessage('Spawned node of class \'{}\'.'
            #                                                                         .format(type(node).__name__), 2000)
            mainWindow.statusBar.showMessage('Spawned node of class \'{}\'.'
                                                                                    .format(type(node).__name__), 2000)
        node.__painter__ = {'position': position}
        node.__pos__ = position
        node.__size__ = (1, len(node.inputs) + len(node.outputs))
        node.__size__ = (1, node.__size__[1] if not issubclass(type(node), ControlNode) else node.__size__[1]-2)
        self.nodes.append(node)
        self.drawItemsOfNode[node] = {'inp': [], 'out': []}
        for out in node.iterOutputs():
            if out.info.select:
                s = Selector(node, out, self)
            else:
                s = OutputLabel(node, out, self)
            self.drawItems.append(s)
            self.drawItemsOfNode[node]['out'].append(s)
        for inp in node.iterInputs():
            # print(inp.name)
            # if inp.name == 'TRIGGER':# and inp.connected:
            #      self.triggers.add(node)
            if inp.info.select:
                s = Selector(node, inp, self)
            elif inp.info.name == 'Control':
                s = InputLabel(node, inp, self)
            else:
                s = LineEdit(node, inp, self)
            self.drawItems.append(s)
            self.drawItemsOfNode[node]['inp'].append(s)
        pprint(('regn',self.drawItemsOfNode))
        print("register node successful",node,node.__class__.__name__)

    def unregisterNode(self, node):
        print("unregister node",node,node.__class__.__name__)
        self.nodes.remove(node)
        del self.drawItemsOfNode[node]

    def updateDrawItems(self, node):
        for drawItem in self.drawItemsOfNode[node]['inp'] + self.drawItemsOfNode[node]['out']:
            self.drawItems.remove(drawItem)
        self.drawItemsOfNode[node] = {'inp': [], 'out': []}
        for out in node.iterOutputs():
            if out.info.select:
                s = Selector(node, out, self)
            else:
                s = OutputLabel(node, out, self)
            self.drawItems.append(s)
            self.drawItemsOfNode[node]['out'].append(s)
        for inp in node.iterInputs():
            # print(inp.name)
            # if inp.name == 'TRIGGER':# and inp.connected:
            #      self.triggers.add(node)
            if inp.info.select:
                s = Selector(node, inp, self)
            elif inp.info.name == 'Control':
                s = InputLabel(node, inp, self)
            else:
                s = LineEdit(node, inp, self)
            self.drawItems.append(s)
            self.drawItemsOfNode[node]['inp'].append(s)
        pprint(('udi',self.drawItemsOfNode))
        # node.__size__ = (1, len(node.inputs) + len(node.outputs) + len(node.INNERINPUTS))
        node.__size__ = (1, len(node.inputs) + len(node.outputs))


    def drawGrid(self, painter):
        painter.setBrush(QBrush(QColor(75,75,75)))
        painter.drawRect(self.rect())
        color = 105

        spacing = 100 * self.scale
        while spacing < 25:
            spacing *= 9
            color = 70 + (color-70) / 2.5
        if color < 0:
            return


        pen = QPen()
        pen.setColor(QColor(color, color, color))
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        verticalN = int(self.width() / spacing / 2) + 1
        horizontalN = int(self.height() / spacing / 2) + 1
        for i in range(verticalN):
            # painter.drawLine(self.width()/2 + self.globalOffset.x()+i*spacing, 0, self.width()/2+ self.globalOffset.x() + i*spacing, self.height())
            painter.drawLine(self.width()/2 +i*spacing, 0, self.width()/2 + i*spacing, self.height())
            # painter.drawLine(QPoint(self.width()/2 + self.globalOffset.x()-i*spacing, 0), QPoint(self.width()/2+ self.globalOffset.x() - i*spacing, self.height()))
            painter.drawLine(QPoint(self.width()/2 -i*spacing, 0), QPoint(self.width()/2 - i*spacing, self.height()))

        for i in range(horizontalN):
            # painter.drawLine(0, self.height()/2+self.globalOffset.y()+i*spacing, self.width(), self.height()/2+self.globalOffset.y()+i*spacing)
            painter.drawLine(0, self.height()/2+i*spacing, self.width(), self.height()/2+i*spacing)
            # painter.drawLine(0, self.height()/2+self.globalOffset.y()-i*spacing, self.width(), self.height()/2+self.globalOffset.y()-i*spacing)
            painter.drawLine(0, self.height()/2-i*spacing, self.width(), self.height()/2-i*spacing)
        painter.setBrush(QBrush(QColor(0, 0, 0,0)))


class WizardPainter(Painter2D):
    def __init__(self, parent=None):
        super(WizardPainter, self).__init__(parent)
        self.stretch = 0
        self.setMinimumSize(300, 236)

        b1 = QPushButton(self)
        b1.setText('Name')
        b1.setGeometry(self.width()/10,35, 50 ,20)
        b1.clicked.connect(parent.editName)
        self.namB = b1

        b2 = QPushButton(self)
        b2.setText('Input')
        b2.setGeometry(10, 75, 50, 20)
        b2.clicked.connect(parent.editInput)

        b3 = QPushButton(self)
        b3.setText('Output')
        b3.setGeometry(self.width() - 60, 92, 50, 20)
        self.outB = b3
        b3.clicked.connect(parent.editOutput)

        b4 = QPushButton(self)
        b4.setText('Setup')
        b4.setGeometry(self.width() - 60, 53, 50, 20)
        b4.clicked.connect(parent.editSetup)
        self.setB = b4

        b5 = QPushButton(self)
        b5.setText('Run')
        b5.setGeometry(self.width()/10, 150, 50, 20)
        b5.clicked.connect(parent.editRun)
        self.runB = b5

        self.setStyleSheet('''
QPushButton {
    background-color: #414141;
    color: white;
}
        ''')

    def resizeEvent(self, event):
        super(WizardPainter, self).resizeEvent(event)
        self.namB.setGeometry(self.width()/10,35, 50 ,20)
        self.outB.setGeometry(self.width() - 60, 92, 50, 20)
        self.setB.setGeometry(self.width() *.75, 53, 50, 20)
        self.runB.setGeometry(self.width()/10, 150, 50, 20)

    def wheelEvent(self, event):
        pass

    def paintEvent(self, event):
        try:
            super(WizardPainter, self).paintEvent(event)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.HighQualityAntialiasing)
            c = 125
            pen = QPen(QColor(c,c,c), 2, Qt.SolidLine)
            painter.setPen(pen)
    
            # Name
            painter.drawLine(self.width()/10+20,45,self.width()/2-39, 45)
            painter.drawLine(self.width()/2-39,45, self.width()/2, 75)
    
            # Input
            painter.drawLine(30, 85, self.width()/2-74, 85)
            painter.drawLine(self.width()/2-74, 85, self.width()/2 -49, 105)
    
            # Output
            tmpNode = list(self.graph.nodes.values())[0]
            inpNum = len(tmpNode.__inputs__.values()) -1
            offset = inpNum * 20
            painter.drawLine(self.width()-45, 102+offset, self.width() / 2 + 74, 102+offset)
            painter.drawLine(self.width() / 2 + 74, 102+offset, self.width() / 2 + 49, 122+offset)
            self.outB.setGeometry(self.width() - 60, 92+offset, 50, 20)
    
            # Setup
            painter.drawLine(self.width()*.75 +20, 63, self.width() / 2 + 39, 63)
            painter.drawLine(self.width() / 2 + 39, 63, self.width() / 2, 93)
    
            # Run
            outNum = len(tmpNode.__outputs__.values()) - 1
            offset += outNum * 20
            painter.drawLine(self.width()/10 + 20, 160+offset, self.width() / 2 - 39, 160+offset)
            painter.drawLine(self.width() / 2 - 39, 160+offset, self.width() / 2, 140+offset)
            self.runB.setGeometry(self.width() / 10, 150+offset, 50, 20)
        except:
            import traceback
            traceback.print_exc()
            print("fail in paint event for now")
            import pdb
            from PyQt5.QtCore import pyqtRemoveInputHook, pyqtRestoreInputHook
            pyqtRemoveInputHook()
            pdb.set_trace()
            raise

    def mousePressEvent(self, event):
        pass

    def mouseReleaseEvent(self, event):
        pass




class NodeWizardDialog(QDialog):
    def __init__(self, parent=None, updateFunc=None):
        super(NodeWizardDialog, self).__init__(parent)
        self.setStyleSheet('''
        QDialog {
            background-color: #414141;
        }
        
        QLabel {
            color: white;
        }

        QLineEdit {
            color: white ;
            background-color: rgb(95,95,95) ;
            border: 2px solid rgb(65,65,65);
        }
        
        QPlainTextEdit {
            color: white;
            background-color: #555555;
        
        }

        QPushButton {
            color: white ;
            background-color: rgb(95,95,95) ;
        }
        
        QComboBox {
            color: white ;
            background-color: rgb(95,95,95) ;
        }
        
        QComboBox QAbstractItemView {
            color: white ;
            background-color: rgb(95,95,95) ;
        }
        
        HeadlineLabel {
            color: white;
            font: bold 12px;
        }
                
        
        HeadlineLabel2 {
            color: white;
            font: bold 14px;
        }
                ''')
        self.updateFunc = updateFunc
        self.name = ''
        self.baseClassName = 'Node'
        self.setupCodeString = 'super(type(self), self).setup()'
        self.runCodeString = 'super(type(self), self).run()'
        # self.setupCodeString = 'print("Hello World")'
        # self.runCodeString = 'print("Hello World")'
        self.inputs = OrderedDict()
        self.outputs = OrderedDict()

        self.resize(500,500)
        self.setLayout(QVBoxLayout())
        l = self.layout()

        self.saveButton = QPushButton('Save')
        self.saveButton.clicked.connect(self.saveNodes)
        self.addSaveButton = False
        self.spacer = QWidget(self)

        newPainter = WizardPainter(self)
        self.painter = newPainter
        # self.painter.resize(self.painter.width(), 800)
        self.painter.setMinimumSize(self.painter.width(),500)
        newPainter.globalOffset = QPoint(-50, -50)
        newPainter.reportWidget = parent.BottomWidget
        newGraph = Graph(painter=newPainter)
        self.graph = newGraph
        self.painter.setSizePolicy(QSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed))

        self.painterBox = QScrollArea(self)
        self.painterBox.setWidgetResizable(True)

        self.painterBox.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff )
        self.painterBox.setWidget(newPainter)
        self._defaultinput = True
        self._defaultoutput = True


        #from PyQt5.QtCore import pyqtRemoveInputHook,pyqtRestoreInputHook
        #pyqtRemoveInputHook()
        #import pdb
        #pdb.set_trace()


        NewNode = MetaNode.makeManaged(
            'NewNode',
            _NODECLASSES[self.baseClassName],
            inputs = [{
                'name':'Input',
                'varType': None.__class__
            }],
            outputs = [{
                'name':'Output',
                'varType': None.__class__
            }],
            nosafe = True
        )
        newNode = newGraph.spawnNode(NewNode)
        newNode.__pos__ = (0,-135)
        self.currentNodeName = 'NewNode'
        # l.addWidget(newPainter)
        l.addWidget(self.painterBox)
        self.editWidget = QWidget(self)
        self.layout().addWidget(self.editWidget)
        self.ready = False
        # with open('test.dat', 'r') as fp:
        #     self.fromJson(fp.read())
        #     self.ready=True
        #     self.updateNode()
        #     self.editName()
        self.startWizard()

    def removeNode(self):
        node = self.painter.nodes[0]
        self.graph.deleteNode(node)
        self.painter.unregisterNode(node)
        return node

    def spawnNode(self, nodeName, nodeClassName):
        # using NODECLASSES instead of _NODECLASSES as the latter would also
        # allow to spawn abstract nodes which does not make sense at all_
        NodeClass = _NODECLASSES[nodeClassName]
        # NodeClass = MetaNode(nodeName, (_NODECLASSES[self.baseClassName],), {})
        # try:
        #     NodeClass.__inputs__ = NodeClass.__bases__[0].__inputs__.copy()
        # except AttributeError as e:
        #     print(e)
        #     NodeClass.__inputs__ = OrderedDict()
        # try:
        #     NodeClass.__outputs__ = NodeClass.__bases__[0].__outputs__.copy()
        # except AttributeError:
        #     NodeClass.__outputs__ = OrderedDict()



        # if nodeClassName in ('Node', 'DynamicNode'):
        #
        #     NodeClass.__inputs__ = OrderedDict()
        #     NodeClass._addInput(data={'name': 'Input',
        #                               'varType': object}, cls=NodeClass)
        #     NodeClass.__outputs__ = OrderedDict()
        #     NodeClass._addOutput(data={'name': 'Output',
        #                                'varType': object}, cls=NodeClass)
        newNode = self.graph.spawnNode(NodeClass)


        newNode.__pos__ = (0, -135)
        self.currentNodeName = nodeName
        self.painter.repaint()

    def startWizard(self):
        
        try:
            self.editWidget.deleteLater()
        except:
            pass
        else:
            if self.addSaveButton:
                ol = self.editWidget.layout()
                ol.removeWidget(self.spacer)
                self.spacer.setParent(self)
                ol.removeWidget(self.saveButton)
                self.saveButton.setParent(self)
        editWidget = QWidget(self)
        l = QFormLayout()
        l.setFormAlignment(Qt.AlignHCenter)
        l.setLabelAlignment(Qt.AlignHCenter)
        editWidget.setLayout(l)
        self.editWidget = editWidget

        editButton = QPushButton('Edit Node Class')
        self.editButton = editButton
        editButton.setEnabled(False)
        editButton.setToolTip('Only managed Node classes can be edited.')
        editButton.clicked.connect(self.editNode)

        baseLabel = QLabel('Select Node Class:')
        selectBase = QComboBox(editWidget)
        selectBase.currentTextChanged.connect(self.onBaseChange)
        newFont = QFont("FontFamily", italic=True, weight=3)
        for i, ( key,value ) in enumerate(
            [('Node',None)] +
             sorted(
                list((
                    (_key,_value)
                    for _key,_value in _NODECLASSES.items()
                    if _value != self.painter.nodes[0].__class__
                ))
            )
        ):
            selectBase.addItem(key)
            if ismanaged(value):
                selectBase.setItemData(i, newFont, Qt.FontRole)
        selectBase.setCurrentText('Node')
        self.selectBase = selectBase
        l.addRow(baseLabel, selectBase)

        subclassButton = QPushButton('Create Subclass')
        subclassButton.clicked.connect(self.subclassNode)


        l.addRow(editButton, subclassButton)



        ll = self.layout()
        ll.addWidget(editWidget)

    def onBaseChange(self, text):
        _oldnodeclass = self.painter.nodes[0].__class__
        if _oldnodeclass.__bases__[0].__name__ != text:
            self.removeNode()
            # _NODECLASSES here as this just changes the
            # the display of the node layout of the basic node
            # managed ones may directly be edited all others are just
            # displayed to simplify selection of proper node for creation
            # of new managed mode
            _newNodeBase = _NODECLASSES[text]
            if ismanaged(_newNodeBase):
                self.editButton.setEnabled(True)
                _makename = _newNodeBase.__name__
                _makebase = _newNodeBase.__bases__[0]
            else:
                _makename = _oldnodeclass.__name__
                _makebase = _newNodeBase
                self.editButton.setEnabled(False)
            _needdummyinputs = len(_newNodeBase.__inputs__) < 1 or ( len(_newNodeBase.__inputs__) == 1 and 'Trigger' in _newNodeBase.__inputs__)
            _needdummyoutputs = len(_newNodeBase.__outputs__) < 1
            if _needdummyinputs or _needdummyoutputs:
                _nodebasebody = _newNodeBase.toDict()
                if _needdummyinputs:
                    _nodebasebody['inputs'] = _nodebasebody.get('inputs',[]) +[{
                        'name':'Input',
                        'varType': None.__class__
                    }]
                    self._defaultinput = True
                else:
                    _defaultinput = False
                if _needdummyoutputs:
                    _nodebasebody['outputs'] = _nodebasebody.get('outputs',[]) + [{
                        'name':'Output',
                        'varType': None.__class__
                    }]
                    self._defaultoutput = True
                else:
                    self._defaultoutput = False
                _newNodeClass = MetaNode.makeManaged(
                    _makename,
                    _makebase,
                    inputs = _nodebasebody['inputs'],
                    outputs = _nodebasebody['outputs'],
                    nodemethods = _nodebasebody,
                    nosafe = True
                )
            else:
                _newNodeClass = _newNodeBase
            _currentNodeName = self.currentNodeName
            try:
                _newNode = self.graph.spawnNode(_newNodeClass)
                _currentNodeName = text
            except:
                print('Cannot spawn Node of Class {}.'.format(text))
                if ismanaged(_newNodeClass):
                    MetaNode.revertUnsavedManaged(_newNodeClass)
                try:
                    _newNode=self.graph.spawnNode(_oldnodeclass)
                except:
                    print('Total failure in updating wizard exiting')
                    raise
            else:
                if ismanaged(_oldnodeclass):
                    MetaNode.revertUnsavedManaged(_oldnodeclass)
            _newNode.__pos__ = (0, -135)
            self.currentNodeName = _currentNodeName
            self.baseClassName = text
        self.painter.repaint()


    def editNode(self):

        #from PyQt5.QtCore import pyqtRemoveInputHook,pyqtRestoreInputHook
        #pyqtRemoveInputHook()
        #import pdb
        #pdb.set_trace()

        _nodetoedit = _NODECLASSES.get(self.baseClassName,None)
        if _nodetoedit is not None and MetaNode.ismanaged(_nodetoedit):
            node = self.painter.nodes[0]
            MetaNode.revertUnsavedManaged(node.__class__)
            if _nodetoedit == node.__class__:
                _nodetoedit = _NODECLASSES.get(self.baseClassName,None)
                assert(ismanaged(_nodetoedit),"editNode may only called when baseClassName selected by onBaseChange is managed")
            self.fromClass(_nodetoedit)
            self.graph.deleteNode(node)
            self.painter.unregisterNode(node)
            self.setupCodeString = _nodetoedit.__setup_source__ if _nodetoedit.__setup_source__ is not None else 'super(type(self), self).setup()'
            _nodebaseclass = _nodetoedit.__bases__[0]
            self.runCodeString = _nodetoedit.__run_source__ if _nodetoedit.__run_source__ is not None else 'super(type(self), self).run()'
            if len(self.inputs) < 1 and ( len(_nodebaseclass.__inputs__) < 1 or ( len(_nodebaseclass.__inputs__) == 1 and 'TRIGGER' in _nodebaseclass.__inputs__ )) :
                _inputs = [dict(
                    name = 'Input',
                    varType = None.__class__
                )]
                self._defaultinput = True
            else:
                _inputs = self.inputs.values()
                self._defaultinput = False
            if len(self.outputs) > 0 or len(_nodebaseclass.__outputs__) > 0:
                _outputs = self.outputs.values()
                self._defaultoutput = False
            else:
                _outputs = [dict(
                    name = 'Output',
                    varType = None.__class__
                )]
                self._defaultoutput = True
            NodeClass = MetaNode.makeManaged(
                _nodetoedit.__name__,
                _nodebaseclass,
                nodemethods = dict(
                    setup = self.setupCodeString,
                    run = self.runCodeString
                ),
                inputs = _inputs,
                outputs = _outputs,
                nosafe = True
            )
            newNode = self.graph.spawnNode(NodeClass)
            newNode.__pos__ = (0, -135)
            if self.baseClassName == NodeClass.__name__:
                self.baseClassName = NodeClass.__bases__[0].__name__
            self.name = NodeClass
        self.painter.repaint()
        self.ready = True
        self.editInput()

    def subclassNode(self):
        self.ready = True
        self.baseClassName = self.selectBase.currentText()
        self.editName()


    def editName(self):
        if not self.ready:
            return
        try:
            self.editWidget.deleteLater()
        except:
            pass
        else:
            if self.addSaveButton:
                ol = self.editWidget.layout()
                ol.removeWidget(self.spacer)
                self.spacer.setParent(self)
                ol.removeWidget(self.saveButton)
                self.saveButton.setParent(self)
        nameEdit = QWidget(self)
        l = QFormLayout()
        l.addRow(HeadlineLabel2('Set Node Name'))
        self.e = QLineEdit(self)
        l.addRow('Node Name', self.e)
        b = QPushButton('Confirm')
        self.e.returnPressed.connect(self.confirmName)
        b.clicked.connect(self.confirmName)
        l.addRow(b)
        nameEdit.setLayout(l)

        ll = self.layout()
        ll.addWidget(nameEdit)
        try:
            self.editWidget.deleteLater()
        except:
            pass
        else:
            if self.addSaveButton:
                ol = self.editWidget.layout()
                ol.removeWidget(self.spacer)
                self.spacer.setParent(self)
                ol.removeWidget(self.saveButton)
                self.saveButton.setParent(self)
        self.editWidget = nameEdit

    def confirmName(self):

        #from PyQt5.QtCore import pyqtRemoveInputHook,pyqtRestoreInputHook
        #pyqtRemoveInputHook()
        #import pdb
        #pdb.set_trace()

        print("cn",self.name)
        newName = self.e.text()
        if newName is None or validatenodename(newName) is None:
            return # TODO indicate name error on text edit
        node = self.painter.nodes[0]
        _nodeclass = node.__class__
        if self.name is not None and len(self.name) > 0:
            _nodebaseclass = _nodeclass.__bases__[0]
            if _nodebaseclass.__name__ == self.baseClassName and node.__class__.__name__ == self.name:
                _renamecurrent = self.name
            else:
                _renamecurrent = None
        else:
            # backup baseClassName
            _baseclassname = self.baseClassName
            MetaNode.revertUnsavedManaged(_nodeclass)
            _nodeclass = _NODECLASSES[self.baseClassName]
            _nodebaseclass = _nodeclass
            #self.fromClass(_nodeclass)
            # restore baseClassName
            self.baseClassName = _baseclassname
            _renamecurrent = None
        # if self.inputs is empty fake em
        if _renamecurrent != newName:
            if len(self.inputs) < 1 and ( len(_nodebaseclass.__inputs__) < 1 or ( len(_nodebaseclass.__inputs__) == 1 and 'TRIGGER' in _nodebaseclass.__inputs__ )) :
                _inputs = [dict(
                    name = 'Input',
                    varType = None.__class__
                )]
                self._defaultinput = True
            else:
                _inputs = self.inputs.values()
                self._defaultinput = False
            if len(self.outputs) > 0 or len(_nodeclass.__outputs__) > 0:
                _outputs = self.outputs.values()
                self._defaultoutput = False
            else:
                _outputs = [dict(
                    name = 'Output',
                    varType = None.__class__
                )]
                self._defaultoutput = True
            try:
                NodeClass = MetaNode.makeManaged(
                    newName,
                    self.baseClassName,
                    rename = _renamecurrent,
                    inputs = _inputs,
                    outputs = _outputs,
                    nodemethods = dict(
                        run = self.runCodeString,
                        setup = self.setupCodeString,
                    ),
                    nosafe = True
                )
            except NodeUpdateError as _errors:
                print("{}\n\nrun:\n----\n{}\n\nsetup:\n------\n{}\n".format(_errors,_errors.runerror,_errors.setuperror))
                return
            except ManagedNodeError:
                return # Node is not managed or new name would overwrite non managed node indicate error on text edit
            self.graph.deleteNode(node)
            self.painter.unregisterNode(node)
            if _renamecurrent is None:
                MetaNode.revertUnsavedManaged(node.__class__)
            newNode = self.graph.spawnNode(NodeClass)
            newNode.__pos__ = (0, -135)
            self.name = newName
        self.updateNode()
        self.addSaveButton = True
        self.editInput()

    def editSetup(self):
        if not self.ready:
            return
        try:
            self.editWidget.deleteLater()
        except:
            pass
        else:
            if self.addSaveButton:
                ol = self.editWidget.layout()
                ol.removeWidget(self.spacer)
                self.spacer.setParent(self)
                ol.removeWidget(self.saveButton)
                self.saveButton.setParent(self)
        inputWidget = QWidget(self)
        self.editWidget = inputWidget
        self.layout().addWidget(inputWidget)
        l = QVBoxLayout()
        inputWidget.setLayout(l)

        self.warningLabel = QLabel('<font color="red">Warning: All code will be executed with the same '
                                   'privileges as the Floppy editor itself.</font>')
        l.addWidget(self.warningLabel)

        self.signatureLabel = QLabel('<font color="orange">def</font> <font color="yellow">setup'
                                     '</font>(<font color="gray">self</font>):')
        l.addWidget(self.signatureLabel)

        ww = QWidget(inputWidget)
        ll = QHBoxLayout()
        ww.setLayout(ll)
        ll.addWidget(QWidget())

        self.codeEdit = CodeEdit(self)
        codeString = self.setupCodeString
        # if 'super(' in codeString:
        #     codeString = codeString.split(',')
        #     codeString = codeString[0][:6] + ',' + self.name + codeString[1]
        if codeString.startswith('def'):
            codeString = '\n'.join([line.strip() for line in codeString.split('\n')[1:]])
        self.codeEdit.setPlainText(codeString)
        ll.addWidget(self.codeEdit)

        l.addWidget(ww)

        confirmButton = QPushButton('Confirm')
        confirmButton.clicked.connect(self.confirmSetup)
        l.addWidget(confirmButton)
        if self.addSaveButton:
            l.addWidget(self.spacer)
            l.addWidget(self.saveButton)

    def confirmSetup(self):
        setupCodeString0 = self.codeEdit.toPlainText()
        self.setupCodeString = setupCodeString0




        # newNode = self.graph.spawnNode(cls)
        # newNode.setup()
        # print(newNode.foo)
        # newNode.foo.append(43)
        # newNode2 = self.graph.spawnNode(cls)
        #
        #
        # print(newNode.foo)
        # print(newNode2.foo)


    def editInput(self):
        if not self.ready:
            return
        try:
            self.editWidget.deleteLater()
        except:
            pass
        else:
            if self.addSaveButton:
                ol = self.editWidget.layout()
                ol.removeWidget(self.spacer)
                self.spacer.setParent(self)
                ol.removeWidget(self.saveButton)
                self.saveButton.setParent(self)

        inputWidget = QWidget(self)
        self.editWidget = inputWidget
        self.layout().addWidget(inputWidget)
        l = QGridLayout()

        inputWidget.setLayout(l)
        l.addWidget(HeadlineLabel2('Set Inputs'), 0, 0)
        l.addWidget(HeadlineLabel('Name'), 1,0)
        l.addWidget(HeadlineLabel('Type'), 1,1)
        l.addWidget(HeadlineLabel('Default'), 1,2)
        l.addWidget(HeadlineLabel('Select'), 1,3)
        l.addWidget(HeadlineLabel('List'), 1,4)
        l.addWidget(HeadlineLabel('Opt'), 1,5)

        cls = self.getNodeClassObject()

        self.removeButtons = {}
        # preset i with 2 to ensure in case no inputs defined yet
        # or default input not available that headlines are not covered
        # by add input line. This will be used as start value for enumerate
        i = 2
        for i, (inpName,inp) in enumerate(cls.__inputs__.items(),i):
            if inp.name == 'TRIGGER':
                continue
            removeButton = QPushButton('Remove')
            self.removeButtons[removeButton] = inpName
            removeButton.pressed.connect(self.removeInput)

            if inpName == 'Input' and self._defaultinput:
                continue
            listBox = QCheckBox()
            listBox.setChecked(inp.list)
            optBox = QCheckBox()
            optBox.setChecked(inp.optional)
            defaultEdit = QLineEdit()
            defaultEdit.setText(str(inp.default))
            nameEdit = QLineEdit()
            nameEdit.setText(inp.name)
            typeEdit = TypeBox(current=inp.varType.__name__)
            selectEdit = TypeBox()
            if inpName not in self.inputs:
                listBox.setEnabled(False)
                typeEdit.setEnabled(False)
                optBox.setEnabled(False)
                defaultEdit.setEnabled(False)
                nameEdit.setEnabled(False)
                removeButton.setEnabled(False)
                removeButton.setText('Base')
            #    #disabled for now as set to None anyway below. change the commenting 
            #    # of these two and the follwoing two lines to activate select
            #    selectEdit.setEnabled(False)
            selectEdit.setEnabled(False)
            l.addWidget(nameEdit, i,0)
            l.addWidget(typeEdit, i, 1)
            l.addWidget(defaultEdit, i,2)
            l.addWidget(selectEdit, i,3)
            l.addWidget(listBox, i,4)
            l.addWidget(optBox, i,5)
            l.addWidget(removeButton, i, 6)

        addButton = QPushButton('Add')
        addButton.pressed.connect(self.addInput)
        newListBox = QCheckBox()
        newListBox.setChecked(inp.list)
        newOptBox = QCheckBox()
        newOptBox.setChecked(inp.optional)
        newDefaultEdit = QLineEdit()
        newDefaultEdit.setText(str(inp.default))
        newNameEdit = QLineEdit()
        newNameEdit.setText('newInput')
        newTypeBox = TypeBox()
        newSelect = TypeBox() ### Placeholder
        #    #disabled for now as set to None anyway below. change the commenting 
        #    # of these two and the follwoing line to activate select
        newSelect.setEnabled(False)
        i+=1
        l.addWidget(newNameEdit, i, 0)
        l.addWidget(newTypeBox, i, 1)
        l.addWidget(newDefaultEdit, i, 2)
        l.addWidget(newSelect, i, 3)
        l.addWidget(newListBox, i, 4)
        l.addWidget(newOptBox, i, 5)
        l.addWidget(addButton, i, 6)
        self.newListBox = newListBox
        self.newOptBox = newOptBox
        self.newDefaultEdit = newDefaultEdit
        self.newNameEdit = newNameEdit
        self.newTypeBox = newTypeBox
        self.newSelect = newSelect


        # confirmButton = QPushButton('Confirm')
        # l.addWidget(confirmButton, i+1,0,1,7 )
        if self.addSaveButton:
            l.addWidget(self.spacer, i+1,0)
            l.addWidget(self.saveButton, i+2,0,1,7 )

    def addInput(self):

        #from PyQt5.QtCore import pyqtRemoveInputHook,pyqtRestoreInputHook
        #pyqtRemoveInputHook()
        #import pdb
        #pdb.set_trace()

        node = self.painter.nodes[0]
        name = node.__class__.__name__
        cls = node.__class__

        isList = self.newListBox.checkState()
        isOptional = self.newOptBox.checkState()
        default = self.newDefaultEdit.text()
        newName = self.newNameEdit.text()
        valType = self.newTypeBox.getType()
        select = self.newSelect.getType()
        select = None

        if self._defaultinput:
            cls._removeInput('Input')
            self._defaultinput = False
        data = {'name': newName,
                'varType': valType,
                'list': isList,
                'optional': isOptional,
                'default': default,
                'select': select}
        cls._addInput(**data)
        self.inputs[newName] = data

        self.updateNode()
        self.editInput()

    def removeInput(self):

        #from PyQt5.QtCore import pyqtRemoveInputHook,pyqtRestoreInputHook
        #pyqtRemoveInputHook()
        #import pdb
        #pdb.set_trace()

        cls = self.getNodeClassObject()

        key =  self.removeButtons[self.sender()]
        #key = list(cls.__inputs__.keys())[i]
        del self.inputs[key]
        cls._removeInput(key)
        if len(self.inputs) < 1 and ( len(cls.__inputs__) < 1 or ( len(cls.__inputs__) == 1 and 'TRIGGER' in cls.__inputs__ )) :
            cls._addInput(**{
                'name': 'Input',
                'varType': None.__class__
            })
            self._defaultinput = True
        else:
            self._defaultinput = False
        self.updateNode()
        self.editInput()

    def editOutput(self):
        if not self.ready:
            return
        try:
            self.editWidget.deleteLater()
        except:
            pass
        else:
            if self.addSaveButton:
                ol = self.editWidget.layout()
                ol.removeWidget(self.spacer)
                self.spacer.setParent(self)
                ol.removeWidget(self.saveButton)
                self.saveButton.setParent(self)

        inputWidget = QWidget(self)
        self.editWidget = inputWidget
        self.layout().addWidget(inputWidget)
        l = QGridLayout()

        inputWidget.setLayout(l)
        l.addWidget(HeadlineLabel2('Set Outputs'), 0, 0)
        l.addWidget(HeadlineLabel('Name'), 1,0)
        l.addWidget(HeadlineLabel('Type'), 1,1)
        # l.addWidget(HeadlineLabel('Default'), 1,2)
        # l.addWidget(HeadlineLabel('Select'), 1,3)
        l.addWidget(HeadlineLabel('List'), 1,2)
        # l.addWidget(HeadlineLabel('Optional'), 1,5)

        cls = self.getNodeClassObject()

        self.removeButtons = {}
        i  = 2
        for i, (outName,out) in enumerate(cls.__outputs__.items(),i):
            removeButton = QPushButton('Remove')
            self.removeButtons[removeButton] = outName
            removeButton.pressed.connect(self.removeOutput)
            if outName == 'Output' and self._defaultoutput:
                continue
            listBox = QCheckBox()
            listBox.setChecked(out.list)
            nameEdit = QLineEdit()
            nameEdit.setText(out.name)
            typeEdit = TypeBox(current=out.varType.__name__)
            if outName not in self.outputs:
                listBox.setEnabled(False)
                typeEdit.setEnabled(False)
                nameEdit.setEnabled(False)
                removeButton.setEnabled(False)
                removeButton.setText('Parent')
            l.addWidget(nameEdit, i,0)
            l.addWidget(typeEdit, i, 1)
            l.addWidget(listBox, i,2)
            l.addWidget(removeButton, i, 3)

        addButton = QPushButton('Add')
        addButton.pressed.connect(self.addOutput)
        newListBox = QCheckBox()
        newListBox.setChecked(False)
        newNameEdit = QLineEdit()
        newNameEdit.setText('newOutput')
        newTypeBox = TypeBox()
        i+=1
        l.addWidget(newNameEdit, i, 0)
        l.addWidget(newTypeBox, i, 1)
        l.addWidget(newListBox, i, 2)
        l.addWidget(addButton, i, 3)
        self.newListBoxO = newListBox
        self.newNameEditO = newNameEdit
        self.newTypeBoxO = newTypeBox


        if self.addSaveButton:
            l.addWidget(self.spacer, i + 1, 0)
            l.addWidget(self.saveButton, i+2,0,1,7 )

    def addOutput(self):

        #from PyQt5.QtCore import pyqtRemoveInputHook,pyqtRestoreInputHook
        #pyqtRemoveInputHook()
        #import pdb
        #pdb.set_trace()

        node = self.painter.nodes[0]
        cls = node.__class__

        isList = self.newListBoxO.checkState()
        newName = self.newNameEditO.text()
        valType = self.newTypeBoxO.getType()

        if self._defaultoutput:
            cls._removeOutput('Output')
            self._defaultoutput = False
        data = {'name': newName,
                'varType': valType,
                'list': isList}
        cls._addOutput(**data)
        self.outputs[newName] = data

        self.updateNode()
        self.editOutput()

    def removeOutput(self):

        #from PyQt5.QtCore import pyqtRemoveInputHook,pyqtRestoreInputHook
        #pyqtRemoveInputHook()
        #import pdb
        #pdb.set_trace()

        cls = self.getNodeClassObject()

        key = self.removeButtons[self.sender()]
        cls._removeOutput(key)
        del self.outputs[key]
        if len(self.outputs) < 0 and len(cls.__outputs__) < 1:
            cls._addOutput(**{
                'name': 'Output',
                'varType': None.__class__
            })
            self._defaultoutput = True
        else:
            self._defaultoutput = False
        self.updateNode()
        self.editOutput()

    def editRun(self):
        if not self.ready:
            return
        try:
            self.editWidget.deleteLater()
        except:
            pass
        else:
            if self.addSaveButton:
                ol = self.editWidget.layout()
                ol.removeWidget(self.spacer)
                self.spacer.setParent(self)
                ol.removeWidget(self.saveButton)
                self.saveButton.setParent(self)
        inputWidget = QWidget(self)
        self.editWidget = inputWidget
        self.layout().addWidget(inputWidget)
        l = QVBoxLayout()
        inputWidget.setLayout(l)

        self.warningLabel = QLabel('<font color="red">Warning: All code will be executed with the same '
                                   'privileges as the Floppy editor itself.</font>')
        l.addWidget(self.warningLabel)

        self.signatureLabel = QLabel('<font color="orange">def</font> <font color="yellow">run'
                                     '</font>(<font color="gray">self</font>):')
        l.addWidget(self.signatureLabel)

        ww = QWidget(inputWidget)
        ll = QHBoxLayout()
        ww.setLayout(ll)
        ll.addWidget(QWidget())

        self.codeEdit = CodeEdit(self)
        codeString = self.runCodeString
        if codeString.startswith('def'):
            codeString = '\n'.join([line.strip() for line in codeString.split('\n')[1:]])
        self.codeEdit.setPlainText(codeString)
        ll.addWidget(self.codeEdit)

        l.addWidget(ww)

        confirmButton = QPushButton('Confirm')
        confirmButton.clicked.connect(self.confirmRun)
        l.addWidget(confirmButton)
        if self.addSaveButton:
            l.addWidget(self.spacer)
            l.addWidget(self.saveButton)

    def confirmRun(self):
        runCodeString0 = self.codeEdit.toPlainText()
        self.runCodeString = runCodeString0

    def getNode(self):
        return self.painter.nodes[0]

    def getNodeName(self):
        return self.getNodeClassObject().__name__

    def getNodeClassObject(self):
        node = self.getNode()
        # name = node.__class__.__name__
        cls = node.__class__
        return cls

    def updateNode(self):

        #from PyQt5.QtCore import pyqtRemoveInputHook,pyqtRestoreInputHook
        #pyqtRemoveInputHook()
        #import pdb
        #pdb.set_trace()

        node = self.getNode()
        name = self.getNodeName()
        try:
            MetaNode.updateManaged(
                self.getNodeClassObject(),
                dict(
                    run = self.runCodeString,
                    setup = self.setupCodeString
                )
            )
        except NodeUpdateError as _errors:
            print("{}\n\nrun:\n----\n{}\n\nsetup:\n------\n{}\n".format(_errors,_errors.runerror,_errors.setuperror))
            return
        self.graph.deleteNode(node)
        self.painter.unregisterNode(node)
        newNode = self.graph.spawnNode(NODECLASSES[name])
        newNode.__pos__ = (0, -135)
        self.painter.repaint()

    def toString(self):
        string = 'class {}({}):\n '.format(self.name, self.baseClassName)
        # need to turn of pylint error which is not aware of that format supports parameter names not just indices
        #pylint: disable=E1126
        string += '\n '.join((
            "{dummy}Input('{name}', {varType}, list={list}, default='{default}', select={select}, opt={opt})".format(
                name=_inp['name'],
                varType=_inp['varType'].__name__,
                list='True' if _inp['list'] else 'False',
                opt='True' if _inp['optional'] else 'False',
                default=_inp['default'],
                select=_inp['select'],
                dummy=('*' if self._defaultinput and _inp['name'] != 'TRIGGER' else '')
            )
            for _inp in self.inputs.values()
        ))
        string += '\n '
        string += '\n '.join((
            "{dummy}Output('{name}', {varType}, list={list})".format(
                name=out['name'],
                varType=out['varType'].__name__,
                list='True' if out['list'] else 'False',
                dummy=('*' if self._defaultoutput else '')
            )
            for out in self.outputs.values()
        ))
        #pylint: enable=E1126

        string += '\n\n def setup(self):\n   '
        string += '\n   '.join((line for line in self.setupCodeString.split('\n')))

        string += '\n\n def run(self):\n   '
        string += '\n   '.join((line for line in self.runCodeString.split('\n')))
        return string

    ##def toDict(self):
    ##    return {'name': self.name,
    ##            'baseClass': self.baseClassName,
    ##            'setup': self.setupCodeString,
    ##            'inputs': self.inputs.values(),
    ##            'outputs': self.outputs.values(),
    ##            'run': self.runCodeString}

    def fromClass(self,cls):
        self.name = cls.__name__
        self.inputs = OrderedDict((
            (_name,_inp.toDict()) for _name,_inp in cls.__classinputs__.items()
        ))
        self.outputs = OrderedDict((
            (_name,_out.toDict()) for _name,_out in cls.__classoutputs__.items()
        ))
        self.setupCodeString = cls.__setup_source__ if cls.__setup_source__ is not None else 'super(type(self), self).setup()'
        self.runCodeString = cls.__run_source__ if cls.__run_source__ is not None else 'super(type(self), self).run()'
        
    def fromDict(self, data):
        self.name = data['name']
        self._fromDict(data)

    ##def _fromDict(self, data):
    ##    self.baseClassName = data['baseClass']
    ##    _inputs = data.get('inputs',OrderedDict())
    ##    self.inputs = (
    ##        _inputs 
    ##        if isinstance(_inputs,OrderedDict) else
    ##        OrderedDict(
    ##            ( _inp['name'],_inp) for _inp in (
    ##                 _inputs.values() if isinstance(_inputs,dict) else _inputs
    ##            )
    ##        )
    ##    )
    ##    _outputs = data.get('outputs',OrderedDict())
    ##    self.outputs = (
    ##        _outputs 
    ##        if isinstance(_outputs,OrderedDict) else
    ##        OrderedDict(
    ##            ( _out['name'],_out) for _out in ( _outputs.values() if isinstance(_outputs,dict) else _outputs)
    ##        )
    ##    )
    ##    self.setupCodeString = data.get('setup','super(type(self), self).setup()')
    ##    self.runCodeString = data.get('run','super(type(self), self).run()')

    ##def toJson(self):
    ##    data = self.toDict()
    ##    for k, input in data['inputs'].items():
    ##        input['varType'] = input['varType'].__name__
    ##    for k, output in data['outputs'].items():
    ##        output['varType'] = output['varType'].__name__
    ##    return json.dumps(data)

    ## # TODO remove when not needed any more, node management done by nodeLis solemny
    ## @staticmethod
    ## def fromJsonStatic(data):
    ##     try:
    ##         data = json.loads(data)
    ##     except json.decoder.JSONDecodeError:
    ##         logger.error('Cannot load managed node class. String <{}> is invalid JSON.'.format(data))
    ##         return None
    ##     else:
    ##         logger.debug('Creating managed node class <{}>. Base class is <{}>.'.format(data['name'], data['baseClass']))
    ##     for k, input in data['inputs'].items():
    ##         input['varType'] = TypeBox.str2Type(input['varType'])
    ##     for k, output in data['outputs'].items():
    ##         output['varType'] = TypeBox.str2Type(output['varType'])



    ##     NodeClass = MetaNode(data['name'], (_NODECLASSES[data['baseClass']],), {})
    ##     try:
    ##         NodeClass.__inputs__ = NodeClass.__bases__[0].__inputs__.copy()
    ##     except AttributeError as e:
    ##         NodeClass.__inputs__ = OrderedDict()
    ##     try:
    ##         NodeClass.__outputs__ = NodeClass.__bases__[0].__outputs__.copy()
    ##     except AttributeError:
    ##         NodeClass.__outputs__ = OrderedDict()

    ##     # NodeClass.__inputs__ = OrderedDict()
    ##     for inp in data['inputs'].values():
    ##         NodeClass._addInput(data=inp)

    ##     # NodeClass.__outputs__ = OrderedDict()
    ##     for out in data['outputs'].values():
    ##         NodeClass._addOutput(data=out)

    ##     runCodeString = 'def run(self):\n ' + '\n '.join(data['run'].split('\n'))
    ##     scope = {}
    ##     exec(runCodeString, scope)

    ##     # ---Magic line. Don't touch!---
    ##     NodeClass.run = scope['run'].__get__(None, NodeClass)
    ##     # ------------------------------

    ##     setupCodeString = 'def setup(self):\n ' + '\n '.join(data['setup'].split('\n'))

    ##     scope = {}
    ##     exec(setupCodeString, scope)
    ##     # cls = self.getNodeClassObject()

    ##     # ---Magic line. Don't touch!---
    ##     NodeClass.setup = scope['setup'].__get__(None, NodeClass)
    ##     # ------------------------------

    ##     return NodeClass

    ## # TODO remove when not needed any more
    ## def fromJson(self, data):
    ##     try:
    ##         data = json.loads(data)
    ##     except json.decoder.JSONDecodeError:
    ##         logger.error('Cannot load managed node class. String <{}> is invalid JSON.'.format(data))
    ##         return None
    ##     for k, input in data['inputs'].items():
    ##         input['varType'] = TypeBox.str2Type(input['varType'])
    ##     for k, output in data['outputs'].items():
    ##         output['varType'] = TypeBox.str2Type(output['varType'])
    ##     self.fromDict(data)

    ##     node = self.painter.nodes[0]
    ##     self.graph.deleteNode(node)
    ##     self.painter.unregisterNode(node)
    ##     newName = self.name
    ##     NodeClass = MetaNode(newName, (_NODECLASSES[self.baseClassName],), {})
    ##     self._fromDict(data)
    ##     NodeClass.__inputs__ = OrderedDict()
    ##     if not self.inputs:
    ##         NodeClass._addInput(**{
    ##             'name': 'Input',
    ##             'varType': object
    ##         })
    ##     else:
    ##         for inp in self.inputs.values():
    ##             NodeClass._addInput(data=inp)

    ##     NodeClass.__outputs__ = OrderedDict()
    ##     if not self.outputs:
    ##         NodeClass._addOutput(**{
    ##             'name': 'Output',
    ##             'varType': object
    ##         })
    ##     else:
    ##         for out in self.outputs.values():
    ##             NodeClass._addOutput(data=out)
    ##     newNode = self.graph.spawnNode(NODECLASSES[newName])
    ##     newNode.__pos__ = (0, -135)


    def closeEvent(self, event):
        cls = self.getNodeClassObject()
        if self._defaultinput:
            cls._removeInput('Input')
        if self._defaultoutput:
            cls._removeOutput('Output')
        _reverted = MetaNode.revertUnsavedManaged(cls)
        if self.updateFunc:
            self.updateFunc()
        super(NodeWizardDialog, self).closeEvent(event)

    def saveNodes(self):
        

        #from PyQt5.QtCore import pyqtRemoveInputHook,pyqtRestoreInputHook
        #pyqtRemoveInputHook()
        #import pdb
        #pdb.set_trace()

        try:
            MetaNode.makeManaged(
                name = self.name,
                baseClass = self.baseClassName,
                inputs = self.inputs.values(),
                outputs = self.outputs.values(),
                nodemethods = dict(
                    run = self.runCodeString,
                    setup = self.setupCodeString
                )
            )
        except NodeUpdateError as _errors:
            print("{}\n\nrun:\n----\n{}\n\nsetup:\n------\n{}\n".format(_errors,_errors.runerror,_errors.setuperror))


class CodeEdit(QPlainTextEdit):
    pass


class HeadlineLabel(QLabel):
    pass

class HeadlineLabel2(QLabel):
    pass

class TypeBox(QComboBox):
    def __init__(self, parent=None, current=None):
        super(TypeBox, self).__init__(parent)
        for name in FLOPPYTYPEMAP.keys():
            if name == None.__class__.__name__:
                continue
            self.addItem(name)

        if current and current != None.__class__.__name__ and current in FLOPPYTYPEMAP:
            self.setCurrentText(current)

    def getType(self):
        return FLOPPYTYPEMAP[self.currentText()]

    @staticmethod
    def str2Type(string):
        return FLOPPYTYPEMAP[string]

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None, painter=None):
        #NodeWizardDialog.loadManagedNodes()
        self.closeOnReturn = False
        self.overrideReturn = False
        self.returnValue = None
        global mainWindow
        mainWindow = self
        super(MainWindow, self).__init__(parent)

        iconRoot = os.path.realpath(__file__)
        iconRoot = os.path.join(os.path.dirname(os.path.dirname(iconRoot)), 'floppy')
        self.iconRoot = os.path.join(iconRoot, 'ressources')
        self.settings = QSettings('Floppy', 'Floppy')

        self.setupUi(self)

        self.setWindowIcon(QIcon(os.path.join(self.iconRoot, 'appIcon.png')))

        self.resize(900, 700)
        self.setWindowTitle('Floppy')

        self.initActions()
        self.initMenus()
        drawWidget = painter
        painter.reportWidget = self.BottomWidget
        drawWidget.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(drawWidget.backgroundRole(), QColor(70, 70, 70))
        drawWidget.setPalette(p)
        # l = QGridLayout()
        # l.addWidget(drawWidget)
        # self.DrawArea.setLayout(l)
        self.DrawArea.addTab(drawWidget, 'New Graph')

        self.DrawArea.tabCloseRequested.connect(self.dummy)
        # self.getPainter() = drawWidget
        # self.painter = drawWidget
        self.setupNodeLib()
        # self.getGraph().spawnAndConnect()
        try:
            self.connectHint = self.settings.value('DefaultConnection', type=str)
        except TypeError:
            self.connectHint = '127.0.0.1'
        settingsDialog = SettingsDialog(self, settings=self.settings, globals=globals())
        settingsDialog.close()

        self.activeGraph = None
        self.activePainter = None
        self.activeIndex = None
        self.makeGraphActive()

    def dummy(self, index):
        self.DrawArea.removeTab(index)


    def setFloppyReturnValue(self, value):
        self.overrideReturn = True
        self.returnValue = value
        if self.closeOnReturn:
            self.close()

    def getFloppyReturnValue(self):
        return (self.overrideReturn, self.returnValue)

    def setArgs(self, args):
        if args.test:
            logger.info('Performing test.')
            self.closeOnReturn = True
            self.loadGraph(override=args.test[0], makeActive=True)
            self.runCode()

    def initActions(self):
        self.exitAction = QAction(QIcon(os.path.join(self.iconRoot, 'quit.png')), 'Quit', self)
        self.exitAction.setShortcut('Ctrl+Q')
        self.exitAction.setStatusTip('Exit application')
        self.exitAction.triggered.connect(self.close)

        self.newAction = QAction(QIcon(os.path.join(self.iconRoot, 'new.png')), 'New', self)
        self.newAction.setShortcut('Ctrl+N')
        self.newAction.setStatusTip('New Graph')
        self.newAction.triggered.connect(self.new)

        self.runAction = QAction(QIcon(os.path.join(self.iconRoot, 'run.png')), 'Run', self)
        self.runAction.setShortcut('Ctrl+R')
        self.runAction.triggered.connect(self.runCode)
        self.runAction.setIconVisibleInMenu(True)
        self.addAction(self.runAction)
        
        self.loadAction = QAction(QIcon(os.path.join(self.iconRoot, 'load.png')), 'load', self)
        self.loadAction.setShortcut('Ctrl+O')
        self.loadAction.triggered.connect(self.loadGraph)
        self.loadAction.setIconVisibleInMenu(True)
        self.addAction(self.loadAction)

        self.makeActiveAction = QAction(QIcon(os.path.join(self.iconRoot, 'makeActive.png')), 'makeActive', self)
        self.makeActiveAction.setShortcut('Ctrl+K')
        self.makeActiveAction.triggered.connect(self.makeGraphActive)
        self.makeActiveAction.setIconVisibleInMenu(True)
        self.addAction(self.makeActiveAction)
        
        self.saveAction = QAction(QIcon(os.path.join(self.iconRoot, 'save.png')), 'save', self)
        self.saveAction.setShortcut('Ctrl+S')
        self.saveAction.triggered.connect(self.saveGraph)
        self.saveAction.setIconVisibleInMenu(True)
        self.addAction(self.saveAction)

        self.killRunnerAction = QAction(QIcon(os.path.join(self.iconRoot, 'kill.png')), 'Kill Interpreter', self)
        self.killRunnerAction.setShortcut('Ctrl+K')
        self.killRunnerAction.triggered.connect(self.killRunner)
        self.killRunnerAction.setIconVisibleInMenu(True)
        self.addAction(self.killRunnerAction)

        self.pauseRunnerAction = QAction(QIcon(os.path.join(self.iconRoot, 'pause.png')), 'Pause', self)
        self.pauseRunnerAction.setShortcut('Ctrl+P')
        self.pauseRunnerAction.triggered.connect(self.pauseRunner)
        self.pauseRunnerAction.setIconVisibleInMenu(True)
        self.addAction(self.pauseRunnerAction)
        
        self.unpauseRunnerAction = QAction(QIcon(os.path.join(self.iconRoot, 'unpause.png')), 'Unpause', self)
        self.unpauseRunnerAction.setShortcut('Ctrl+L')
        self.unpauseRunnerAction.triggered.connect(self.unpauseRunner)
        self.unpauseRunnerAction.setIconVisibleInMenu(True)
        self.addAction(self.unpauseRunnerAction)
        
        self.stepRunnerAction = QAction(QIcon(os.path.join(self.iconRoot, 'step.png')), 'Step', self)
        self.stepRunnerAction.setShortcut('Ctrl+K')
        self.stepRunnerAction.triggered.connect(self.stepRunner)
        self.stepRunnerAction.setIconVisibleInMenu(True)
        self.addAction(self.stepRunnerAction)
        
        self.gotoRunnerAction = QAction(QIcon(os.path.join(self.iconRoot, 'goto.png')), 'GoTo', self)
        self.gotoRunnerAction.setShortcut('Ctrl+F')
        self.gotoRunnerAction.triggered.connect(self.gotoRunner)
        self.gotoRunnerAction.setIconVisibleInMenu(True)
        self.addAction(self.gotoRunnerAction)
        
        self.updateRunnerAction = QAction(QIcon(os.path.join(self.iconRoot, 'update.png')), 'Update', self)
        self.updateRunnerAction.setShortcut('Ctrl+U')
        self.updateRunnerAction.triggered.connect(self.updateRunner)
        self.updateRunnerAction.setIconVisibleInMenu(True)
        self.addAction(self.updateRunnerAction)
        
        self.spawnRunnerAction = QAction(QIcon(os.path.join(self.iconRoot, 'spawn.png')), 'Spawn', self)
        self.spawnRunnerAction.setShortcut('Ctrl+H')
        self.spawnRunnerAction.triggered.connect(self.spawnRunner)
        self.spawnRunnerAction.setIconVisibleInMenu(True)
        self.addAction(self.spawnRunnerAction)
        
        self.deleteNodeAction = QAction('Delete', self)
        self.deleteNodeAction.setShortcut('Ctrl+D')
        self.deleteNodeAction.triggered.connect(self.deleteNode)
        self.deleteNodeAction.setIconVisibleInMenu(True)
        self.addAction(self.deleteNodeAction)
        
        self.connectAction = QAction(QIcon(os.path.join(self.iconRoot, 'connect.png')), 'Connect', self)
        self.connectAction.setShortcut('Ctrl+C')
        self.connectAction.triggered.connect(self.connect)
        self.connectAction.setIconVisibleInMenu(True)
        self.addAction(self.connectAction)
        
        self.statusAction = QAction('Status', self)
        # self.statusAction.setShortcut('Ctrl+R')
        self.statusAction.triggered.connect(self.updateStatus)
        self.statusAction.setIconVisibleInMenu(True)
        self.addAction(self.statusAction)

        self.dropAction = QAction(QIcon(os.path.join(self.iconRoot, 'drop.png')), 'Drop', self)
        self.dropAction.setShortcut('Ctrl+I')
        self.dropAction.triggered.connect(self.dropGraph)
        self.dropAction.setIconVisibleInMenu(True)
        self.addAction(self.dropAction)

        self.pushAction = QAction(QIcon(os.path.join(self.iconRoot, 'push.png')), 'Push', self)
        self.pushAction.setShortcut('Ctrl+X')
        self.pushAction.triggered.connect(self.pushGraph)
        self.pushAction.setIconVisibleInMenu(True)
        self.addAction(self.pushAction)
        
        self.settingsAction = QAction(QIcon(os.path.join(self.iconRoot, 'settings.png')), 'Settings', self)
        self.settingsAction.setShortcut('Ctrl+T')
        self.settingsAction.triggered.connect(self.openSettingsDialog)
        self.settingsAction.setIconVisibleInMenu(False)
        self.addAction(self.settingsAction)
        
        # self.createSubgraphAction = QAction(QIcon(os.path.join(self.iconRoot, 'macro.png')), 'Create Macro', self)
        # self.createSubgraphAction.setShortcut('Ctrl+G')
        # self.createSubgraphAction.triggered.connect(self.openMacroDialog)
        # self.createSubgraphAction.setIconVisibleInMenu(False)
        # self.addAction(self.createSubgraphAction)
        
        self.configureAction = QAction(QIcon(os.path.join(self.iconRoot, 'configure.png')), 'configure', self)
        self.configureAction.setShortcut('Ctrl+Y')
        self.configureAction.triggered.connect(self.configureInterpreter)
        self.configureAction.setIconVisibleInMenu(False)
        self.addAction(self.configureAction)

        self.nodeWizardAction = QAction(QIcon(os.path.join(self.iconRoot, 'new.png')), 'nodeWizard', self)
        self.nodeWizardAction.setShortcut('Ctrl+M')
        self.nodeWizardAction.triggered.connect(self.openNodeWizard)
        self.nodeWizardAction.setIconVisibleInMenu(False)
        self.addAction(self.nodeWizardAction)

    def initMenus(self):
        fileMenu = self.menuBar.addMenu('&File')
        fileMenu.addAction(self.exitAction)
        fileMenu.addAction(self.newAction)
        fileMenu.addAction(self.runAction)

        advancedMenu = self.menuBar.addMenu('&Advanced')
        advancedMenu.addAction(self.connectAction)
        # advancedMenu.addAction(self.createSubgraphAction)

        settingsMenu = self.menuBar.addMenu('&Settings')
        settingsMenu.addAction(self.settingsAction)
        
        self.mainToolBar.addAction(self.exitAction)
        self.mainToolBar.addSeparator()
        self.mainToolBar.addAction(self.newAction)
        self.mainToolBar.addAction(self.saveAction)
        self.mainToolBar.addAction(self.loadAction)
        self.mainToolBar.addAction(self.makeActiveAction)
        self.mainToolBar.addSeparator()
        self.mainToolBar.addAction(self.runAction)
        self.mainToolBar.addSeparator()
        self.mainToolBar.addAction(self.pauseRunnerAction)
        self.mainToolBar.addAction(self.unpauseRunnerAction)
        self.mainToolBar.addAction(self.stepRunnerAction)
        self.mainToolBar.addAction(self.gotoRunnerAction)
        self.mainToolBar.addSeparator()
        self.mainToolBar.addAction(self.spawnRunnerAction)
        self.mainToolBar.addAction(self.pushAction)
        self.mainToolBar.addAction(self.updateRunnerAction)
        self.mainToolBar.addAction(self.killRunnerAction)
        self.mainToolBar.addSeparator()
        # self.mainToolBar.addAction(self.deleteNodeAction)
        self.mainToolBar.addAction(self.connectAction)
        # self.mainToolBar.addAction(self.statusAction)
        self.mainToolBar.addAction(self.dropAction)



        self.mainToolBar.addSeparator()
        self.mainToolBar.addAction(self.settingsAction)
        self.mainToolBar.addSeparator()
        self.mainToolBar.addAction(self.nodeWizardAction)
        # self.mainToolBar.addAction(self.deleteNodeAction)

        # self.mainToolBar.addWidget(QLabel('Display Macro:'))
        # macroSelector = QComboBox(self.mainToolBar)
        # self.macroSelector = macroSelector
        # macroSelector.addItem('main')
        self.knownSubgraphs = set()
        # macroSelector.currentTextChanged.connect(self.selectSubgraph)
        # macroSelector.activated.connect(self.getSubgraphList)
        # self.mainToolBar.addWidget(macroSelector)

    # def selectSubgraph(self):
    #     self.getPainter().setSelectedSubgraph(self.macroSelector.currentText())
    #     self.getPainter().update()

    def makeGraphActive(self):
        if not self.activeIndex == None:
            self.DrawArea.setTabText(self.activeIndex, self.DrawArea.tabText(self.activeIndex)[:-1])
        currentIndex = self.DrawArea.currentIndex()
        self.activeGraph = self.getGraph()
        self.activePainter = self.getPainter()
        self.activeIndex = currentIndex
        self.DrawArea.setTabText(currentIndex, self.DrawArea.tabText(currentIndex)+'*')

    def openNodeWizard(self):
        dialog = NodeWizardDialog(self, updateFunc=self.FilterEdit.reCheck)
        dialog.setStyleSheet('''
QDialog {
    background-color: #414141;
}
        ''')
        # l = QVBoxLayout()
        # dialog.setLayout(l)
        l = dialog.layout()


        # l.addWidget(QLabel('xxxx'))

        dialog.setWindowTitle('New Node')
        dialog.setWindowModality(Qt.ApplicationModal)
        # dialog.resize(300,500)
        dialog.show()

    def configureInterpreter(self):
        frameRate = self.settings.value('FrameRate', type=float)
        mode = self.settings.value('RGIMode', type=str)
        self.getGraph().configureInterpreter({'framerate': frameRate, 'mode': mode})

    def getSubgraphList(self):
        new = self.getPainter().getAllSubgraphs()
        self.macroSelector.addItems(new.difference(self.knownSubgraphs))
        self.knownSubgraphs = self.knownSubgraphs.union(new)

    def new(self):
        # self.getPainter().reset()
        # self.getPainter().registerGraph(Graph(self.getPainter()))
        # self.getPainter().reportWidget = self.BottomWidget
        # self.getPainter().repaint()
        try:
            oldGraph = self.getGraph()
        except AttributeError:
            oldGraph = None
        newPainter = Painter2D()
        newPainter.reportWidget = self.BottomWidget
        newGraph = Graph(painter=newPainter)
        if oldGraph:
            newGraph.registerExisitingInterpreterConnection(oldGraph.rgiConnection)
        self.DrawArea.addTab(newPainter, 'New Graph')
        number = self.DrawArea.count()
        self.DrawArea.setCurrentIndex(number-1)

    def getPainter(self):
        return self.DrawArea.currentWidget()

    def getGraph(self):
        return self.getPainter().graph

    def openMacroDialog(self):
        if not self.getPainter().groupSelected():
            self.statusBar.showMessage('You Must Select a Group to Create a Macro.', 2000)
            return
        name, state = QInputDialog.getText(self, 'Create Macro', 'Macro Name:')
        if not state:
            return
        self.getPainter().createSubgraph(name)
        self.getSubgraphList()


    def openSettingsDialog(self):
        settingsDialog = SettingsDialog(self, settings=self.settings, globals=globals())
        settingsDialog.show()

    def connect(self):
        self.connectHint = self.settings.value('DefaultConnection', type=str)
        text = ''
        while not text:
            text, ok = QInputDialog.getItem(self, 'Connect to remote Interpreter',
                                            'IP Address/Port: (xxx.xxx.xxx:Port)',
                                            [self.connectHint])
            if not ok:
                return
        if not ':' in text:
            ip = text
            port = ''
            while not port:
                port, ok = QInputDialog.getText(self, 'Port number is missing',
                                                'Port:')
                if not ok:
                    return
        else:
            ip, port = text.split(':')
        self.connectHint = text
        import socket
        try:
            self.getGraph().connect2RemoteRunner(ip, port)
        except ConnectionRefusedError:
            err = QErrorMessage(self)
            err.showMessage('Connection to {} on port {} refused.'.format(ip, port))
        except socket.timeout:
            err = QErrorMessage(self)
            err.showMessage('Connection to {} on port {} timed out.'.format(ip, port))
        else:
            self.statusBar.showMessage('Connection to {} on port {} established.'.format(ip, port), 2000)

    def close(self):
        try:
            self.getGraph().killRunner()
        except:
            print('No runner to kill.')
        workDir = self.settings.value('WorkDir', type=str)
        for file in os.listdir(workDir):
            if file.startswith('_'):
                try:
                    os.remove(workDir+'/'+file)
                except:
                    pass
        qApp.quit()

    def updateStatus(self):
        try:
            self.activeGraph.requestRemoteStatus()
        except AttributeError:
            self.statusBar.showMessage('Cannot Update Graph. No Interpreter Available..', 2000)

    def dropGraph(self):
        try:
            self.activeGraph.dropGraph()
        except AttributeError:
            self.statusBar.showMessage('Cannot Drop Graph. No Interpreter Available..', 2000)

    def pushGraph(self):
        try:
            self.activeGraph.push2Runner()
        except AttributeError:
            self.statusBar.showMessage('Cannot Push Graph. No Interpreter Available.', 2000)

    def killRunner(self):
        try:
            self.activeGraph.killRunner()
        except ConnectionRefusedError:
            pass

    def deleteNode(self):
        node = self.getPainter().getSelectedNode()
        if node:
            # print(1)
            self.getGraph().deleteNode(self.getPainter().getSelectedNode())
            # print(2)
            self.getPainter().unregisterNode(node)
            # print(3)
            time.sleep(.1)
            self.getPainter().repaint()
            # print(4)

    def stepRunner(self):
        try:
            self.activeGraph.stepRunner()
        except AttributeError:
            self.statusBar.showMessage('Cannot Execute Graph Step. No Interpreter Available.', 2000)

    def gotoRunner(self):
        try:
            self.activeGraph.gotoRunner(1)
        except AttributeError:
            self.statusBar.showMessage('Cannot Go To Node. No Interpreter Available.', 2000)

    def updateRunner(self):
        try:
            self.activeGraph.updateRunner()
        except AttributeError:
            self.statusBar.showMessage('Cannot Update Interpreter. No Interpreter Available.', 2000)

    def pauseRunner(self):
        try:
            self.activeGraph.pauseRunner()
        except AttributeError:
            self.statusBar.showMessage('Cannot Pause Interpreter. No Interpreter Available.', 2000)

    def unpauseRunner(self):
        try:
            self.activeGraph.unpauseRunner()
        except AttributeError:
            self.statusBar.showMessage('Cannot Unpause Interpreter. No Interpreter Available.', 2000)

    def spawnRunner(self):
        logger.debug('Spawning new Runner.')
        self.statusBar.showMessage('New Remote Interpreter spawned.', 2000)
        self.activeGraph.spawnAndConnect(LOCALPORT)
        self.configureInterpreter()
        logger.debug('Connected to Runner.')

    def runCode(self, *args):
        frameRate = self.settings.value('FrameRate', type=float)
        mode = self.settings.value('RGIMode', type=str)
        self.activeGraph.execute(options={'framerate': frameRate, 'mode': mode}, reuse=1)
        self.statusBar.showMessage('Code execution started.', 2000)

    def loadGraph(self, *args, override=False, makeActive=True):
        self.new()
        if not override:
            fileName = QFileDialog.getOpenFileName(self, 'Open File', '~/',
                                                   filter='Floppy Files (*.ppy);; Any (*.*)')[0]
        else:
            fileName = override
        if fileName:
            logger.debug('Attempting to load graph: {}'.format(fileName))
            self.getGraph().load(fileName, callback=self.raiseErrorMessage)
            self.statusBar.showMessage('Graph loaded from {}.'.format(fileName), 2000)
            logger.info('Successfully loaded graph: {}'.format(fileName))
            name = os.path.split(fileName)[-1][:-4]
            self.DrawArea.setTabText(self.DrawArea.currentIndex(), name)
            if makeActive:
                self.makeGraphActive()

    def raiseErrorMessage(self, message):
        err = QErrorMessage(self)
        err.showMessage(message)
        logger.error(message)

    def saveGraph(self, *args):
        """
        Callback for the 'SaveAction'.
        :param args: throwaway arguments.
        :return: None
        """
        fileName = QFileDialog.getSaveFileName(self, 'Save File', '~/')[0]
        if not fileName:
            return
        if not fileName.endswith('.ppy'):
             fileName += '.ppy'
        logger.debug('Attempting to save graph as {}'.format(fileName))
        self.getGraph().save(fileName)
        self.statusBar.showMessage('Graph saved as {}.'.format(fileName), 2000)
        logger.info('Save graph as {}'.format(fileName))
        label = os.path.split(fileName)[-1][:-4]
        if self.DrawArea.tabText(self.DrawArea.currentIndex()).endswith('*'):
            label += '*'
        self.DrawArea.setTabText(self.DrawArea.currentIndex(), label)


    def resizeEvent(self, event):
        super(MainWindow, self).resizeEvent(event)
        self.getPainter().repaint()
        self.getPainter().update()

    def setupNodeLib(self):
        self.NodeListView.setup(self.FilterEdit, self.getGraph())

    def closeEvent(self, event):
        logger.debug('Attempting to kill interpreter.')
        self.killRunner()
        logger.debug('MainWindow is shutting down.')
        super(MainWindow, self).closeEvent(event)

    def keyPressEvent(self, event):
        super(MainWindow, self).keyPressEvent(event)
        if event.key() == 16777248:
            self.getPainter().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        super(MainWindow, self).keyReleaseEvent(event)
        if event.key() == 16777248:
            self.getPainter().keyReleaseEvent(event)


class DrawItem(object):
    alignment = Qt.AlignRight
    def __init__(self, parent, data, painter):
        self.painter = painter
        self.state = False
        self.x = 0
        self.y = 0
        self.w = 0
        self.h = 0
        self.parent = parent
        self.data = data
        self.active = True

    def deactivate(self):
        self.active = False

    def activeate(self):
        self.active = True

    def update(self, x, y, w, h, transform):
        self.transform = transform
        self.x = x
        self.y = y
        self.w = w - 10
        self.h = h
        point = QPoint(x+12, y-16)*transform
        self._x = point.x()
        self._y = point.y()
        point = QPoint(x+w-24, y+h-60)*transform
        self._xx = point.x()
        self._yy = point.y()

        self._yy = self._y + PINSIZE

    def draw(self, painter, asLabel=False):
        alignment = self.__class__.alignment
        text = self.data.name
        pen = QPen(Qt.darkGray)
        painter.setPen(pen)
        painter.setBrush(QColor(40, 40, 40))
        xx, yy, ww, hh = self.x+(self.w)/2.-(self.w-25)/2., self.y-18, self.w-18, 4+PINSIZE
        painter.setFont(QFont('Helvetica', LINEEDITFONTSIZE))
        painter.setPen(pen)
        painter.drawText(xx+5, yy-3 + TEXTYOFFSET, ww-10, hh+5, alignment, text)

    def run(self):
        pass

    def setState(self, state):
        self.state = state

    def collide(self, pos):
        if not self.active:
            return False
        if self._x < pos.x() < self._xx and self._y < pos.y() < self._yy:
            return True

    def watch(self, pos):
         pass

    def watchDown(self, pos):
         pass

    def keyPressEvent(self, event):
        pass


class Selector(DrawItem):
    alignment = Qt.AlignLeft
    def __init__(self, *args, **kwargs):
        super(Selector, self).__init__(*args, **kwargs)
        self.highlight = 0
        self.select = None
        self.items = self.data.info.select
        if self.data.info.default is not None:
            self.select = str(self.data.info.default)

    def update(self, x, y, w, h, transform):
        super(Selector, self).update(x, y, w, h, transform)
        if self.select is not None:
            self.items = self.data.info.select
            if self.data.info.default is not None:
                self.select = str(self.data.info.default)

    def watch(self, pos):
        scale = self.painter.scale
        for i in range(1, len(self.items)+1):
            if self._x < pos.x() < self._xx and self._y+4*scale + PINSIZE*i*scale < pos.y() < (self._y+4*scale + (i+1)*scale*PINSIZE):
                self.highlight = i
                return

    def watchDown(self, pos):
        self.select = str(self.items[self.highlight-1])
        self.parent.inputs[self.data.name].setDefault(self.select)
        # self.parent._Boolean.setDefault(self.select)
        # self.painter.removeWatchingItem(self)

    def collide(self, pos):
        if self._x < pos.x() < self._xx+16 and self._y < pos.y() < self._yy:
            self.state = (self.state + 1) % 2
            try:
                self.painter.registerWatchingItem(self)
            except ValueError:
                pass
        else:
            if self.state:
                try:
                    self.painter.removeWatchingItem(self)
                except ValueError:
                    pass
            self.state = 0
        return super(Selector, self).collide(pos)

    def draw(self, painter, last=False, asLabel=False):
        if asLabel:
            text = asLabel
            alignment = self.__class__.alignment
            pen = QPen(Qt.darkGray)
            painter.setPen(pen)
            painter.setBrush(QColor(40, 40, 40))
            xx, yy, ww, hh = self.x+(self.w)/2.-(self.w-25)/2., self.y-18, self.w-18, 4+PINSIZE
            painter.setFont(QFont('Helvetica', LINEEDITFONTSIZE))
            painter.setPen(pen)
            painter.drawText(xx+5, yy-3 + TEXTYOFFSET, ww-10, hh+5, alignment, text)
            return
        if not self.state:
            alignment = self.alignment
            text = self.data.name
            if self.select:
                text = str(self.select)
            pen = QPen(Qt.darkGray)
            painter.setPen(pen)
            painter.setBrush(QColor(40, 40, 40))
            xx, yy, ww, hh = self.x+(self.w)/2.-(self.w-25)/2., self.y-18, self.w-25, 4+PINSIZE
            painter.drawRoundedRect(xx, yy, ww, hh, 2, 20)
            painter.setFont(QFont('Helvetica', LINEEDITFONTSIZE))
            painter.setPen(pen)
            painter.drawText(xx+5, yy-3+TEXTYOFFSET, ww-20, hh+5, alignment, text)
            pen.setColor(Qt.gray)
            # pen.setWidth(3)
            painter.setPen(pen)
            painter.setBrush(QBrush(Qt.gray))
            points = QPoint(xx+self.w-40, yy-2+PINSIZE/2), QPoint(xx+10-40 + self.w, yy-2+PINSIZE/2), QPoint(xx+5+self.w-40, yy+4+PINSIZE/2)
            painter.drawPolygon(*points)
            painter.setBrush(QColor(40, 40, 40))
        else:
            if not last:
                return self
            alignment = self.alignment
            text = self.data.name
            pen = QPen(Qt.darkGray)
            painter.setPen(pen)
            painter.setBrush(QColor(40, 40, 40))
            xx, yy, ww, hh = self.x+(self.w)/2.-(self.w-25)/2., self.y-26 + 12, self.w-25, (4+PINSIZE) * len(self.items)
            painter.drawRoundedRect(xx, yy+PINSIZE, ww, hh, 2, 20+PINSIZE)
            painter.setFont(QFont('Helvetica', LINEEDITFONTSIZE))
            painter.setPen(pen)

            for i, item in enumerate(self.items):
                item = str(item)
                if i+1 == self.highlight:
                    pen.setColor(Qt.white)
                    painter.setPen(pen)
                else:
                    pen = QPen(Qt.darkGray)
                    painter.setPen(pen)
                painter.drawText(xx+5, yy+PINSIZE-3+i*(4+PINSIZE)+TEXTYOFFSET, ww-20, hh+5+PINSIZE, alignment, item)
            # painter.drawText(xx-5, yy-3+0, ww-20, hh+5, alignment, 'True')
            # painter.drawText(xx-5, yy-3+12, ww-20, hh+5, alignment, 'False')

            pen = QPen(Qt.darkGray)
            painter.setPen(pen)
            painter.setBrush(QColor(60, 60, 60))
            xx, yy, ww, hh = self.x+(self.w)/2.-(self.w-25)/2., self.y-18, self.w-25, 4+PINSIZE
            painter.drawRoundedRect(xx, yy, ww, hh, 2, 20)
            painter.drawText(xx+5, yy-3+TEXTYOFFSET, ww-20, hh+5, alignment, text)


class LineEdit(DrawItem):
    alignment = Qt.AlignLeft

    def __init__(self, parent, data, painter):
        super(LineEdit, self).__init__(parent, data, painter)
        self.text = ''

    def collide(self, pos):
        collides = super(LineEdit, self).collide(pos)
        if collides:
            self.state = (self.state + 1) % 2
            self.painter.registerWatchingItem(self)
            self.painter.relayInputEventsTo(self)
        else:
            self.painter.stopInputRelayingTo(self)
            if self.state:
                self.painter.removeWatchingItem(self)
            self.state = 0
        return collides

    def draw(self, painter, asLabel=False):

        if not self.text and not self.data.info.default:
            text = self.data.name
        else:
            text = self.data.info.default
        if asLabel:
            text = asLabel
            alignment = self.__class__.alignment
            pen = QPen(Qt.darkGray)
            painter.setPen(pen)
            painter.setBrush(QColor(40, 40, 40))
            xx, yy, ww, hh = self.x+(self.w)/2.-(self.w-25)/2., self.y-18, self.w-18, 4+PINSIZE
            painter.setFont(QFont('Helvetica', LINEEDITFONTSIZE))
            painter.setPen(pen)
            painter.drawText(xx+5, yy-3 + TEXTYOFFSET, ww-10, hh+5, alignment, text)
            return
        text = str(text)
        if not self.state:
            alignment = self.__class__.alignment
            pen = QPen(Qt.darkGray)
            painter.setPen(pen)
            painter.setBrush(QColor(40, 40, 40))
            xx, yy, ww, hh = self.x+(self.w)/2.-(self.w-25)/2., self.y-18, self.w-18, 4+PINSIZE
            painter.drawRoundedRect(xx, yy, ww, hh, 2, 20)
            painter.setFont(QFont('Helvetica', LINEEDITFONTSIZE))
            painter.setPen(pen)
            painter.drawText(xx+5, yy-3+TEXTYOFFSET, ww-10, hh+5, alignment, text)
        else:
            alignment = self.__class__.alignment
            pen = QPen(Qt.darkGray)
            painter.setPen(pen)
            painter.setBrush(QColor(10, 10, 10))
            xx, yy, ww, hh = self.x+(self.w)/2.-(self.w-25)/2., self.y-18, self.w-18, 4+PINSIZE
            painter.drawRoundedRect(xx, yy, ww, hh, 2, 20)
            painter.setFont(QFont('Helvetica', LINEEDITFONTSIZE))
            painter.setPen(pen)
            painter.drawText(xx+5, yy-3+TEXTYOFFSET, ww-10, hh+5, alignment, text)

    def keyPressEvent(self, event):
        if event.key() == 16777249:
            return
        if event.key() == 16777219:
            self.text = self.text[:-1]
        else:
            self.text += self.sanitizeInputString(event.text())
        self.painter.update()
        self.parent.inputs[self.data.name].setDefault(self.text)
        super(LineEdit, self).keyPressEvent(event)
        # print(event.key())

    def sanitizeInputString(self, string):
        string = string.strip('\r\n')
        try:
            self.data.info.varType(string)
        except ValueError:
            return ''
        except TypeError:
            print('Was this a shortcut???')
            return ''
        return string


class InputLabel(DrawItem):
    alignment = Qt.AlignLeft


class OutputLabel(DrawItem):
    pass


class NodeDialog(QDockWidget):
    """
    Container Widget handling the set up of a ContextNodeFilter widget and a ContextNodeList when connections are
    dragged into open space.
    """
    def __init__(self, painter, event, pin, graph, parent=None):
        self.graph = graph
        self.painter = painter
        self.pin = pin
        super(NodeDialog, self).__init__(parent)
        self.setTitleBarWidget(QWidget(self))
        self.setStyleSheet("NodeDialog {background-color:rgb(45,45,45) ;border:1px solid rgb(0, 0, 0); "
                           "border-color:black}")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint |Qt.X11BypassWindowManagerHint | Qt.FramelessWindowHint)
        self.setFeatures(QDockWidget.DockWidgetMovable)
        self.setFloating(True)
        pos = event.globalPos()
        self.setGeometry(pos.x(), pos.y(), 150, 250)
        dL = QVBoxLayout()
        cB = QCheckBox('Context sensitive')
        cB.setChecked(painter.contextSensitive)
        self.cB = cB

        nFilter = ContextNodeFilter()
        self.back = True if ':I' in pin else False
        nFilter.registerDialog(self, back=self.back)
        nFilter.setFocus()
        # nodeList = ContextNodeList(nFilter, painter, self)
        nodeList = ContextNodeList(self)
        nodeList.registerDialog(self)
        nodeList.registerGraph(graph)
        nodeList.registerPainter(painter)
        nodeList.setup(nFilter, graph)
        cB.stateChanged.connect(nFilter.check)
        nFilter.registerListView(nodeList)
        dL.addWidget(nFilter)
        dL.addWidget(cB)
        dL.addWidget(nodeList)
        # self.cl
        self.dialogWidget = QWidget()
        self.dialogWidget.setLayout(dL)
        self.setWidget(self.dialogWidget)

    def close(self, spawned=False):
        """
        Close the dialog and connect a newly connected node if necessary.
        :param spawned: Boolean defining whether a node was spawned and needs connecting.
        :return: None
        """
        if spawned:
            self.painter.contextSensitive = self.cB.checkState()
            newNode = self.graph.getNewestNode()
            pin = self.graph.getPinWithID(self.pin)
            if not self.back:
                endPin = newNode.getInputofType(pin.info.varType)
                if endPin:
                    self.graph.connect(self.graph.getNodeFromPinID(self.pin), self.pin.split(':')[1][1:], newNode, endPin.name)
            else:
                endPin = newNode.getOutputofType(pin.info.varType)
                if endPin:
                    # self.graph.connect(self.graph.getNodeFromPinID(self.pin), self.pin.split(':')[1][1:], newNode, endPin.name)
                    self.graph.connect(newNode, endPin.name, self.graph.getNodeFromPinID(self.pin), self.pin.split(':')[1][1:])

                # self.painter.app.connectionManager.registerStart(pin, pin.node)
                # self.painter.app.connectionManager.registerEnd(endPin, newNode)

        # painter.contextSensitive = self.cB.checkState()
        self.painter.update()
        super(NodeDialog, self).close()

    def getTypeHint(self):
        """
        Returns the name of the type of the pin the new node will be connected to.
        This is used to filter the node list for appropriate nodes.
        :return: String representing a Hint. In this case a type Hint.
        """
        pin = self.graph.getPinWithID(self.pin)
        return pin.info.varType.__name__


