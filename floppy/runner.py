"""
Module implementing a program for executing a Floppy graph.
The program can be called from the Floppy editor but will run independently from the calling process.
Communication between the editor and the runner is realized via Sockets.
The runner will report its status to the editor and the editor is able to send commands to the runner.
"""

from threading import Thread, Lock
import time
from queue import Queue
from socket import AF_INET, SOCK_STREAM, socket, SHUT_RDWR, timeout, SHUT_RDWR, SO_REUSEADDR, SOL_SOCKET
import json
import struct
import logging

logger = logging.getLogger('Floppy-Interpreter')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('floppy.log')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)


# host = '127.0.0.1'
# host = '10.76.64.86'
host = ''
port = 8079


# updatePort = 7237

xLock = Lock()


class Runner(object):

    def __init__(self):
        logger.info('Creating new interpreter.')
        self.status = []
        self.runningNodes = []
        self.conn = None
        self.nextNodePointer = None
        self.currentNodePointer = None
        self.lastNodePointer = None
        self.graphData = {}
        self.cmdQueue = Queue(1)
        self.listener = Listener(self)
        self.executionThread = ExecutionThread(self.cmdQueue, self)

        # self.updateSocket = socket(AF_INET, SOCK_STREAM)
        # self.updateSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        # self.updateSocket.bind((host, updatePort))
        # self.updateSocket.listen(1)
        # self.conn, self.clientAddress = None, None


    # def __del__(self):
    #     self.updateSocket.close()
    def join(self):
        self.executionThread.join()

    def resetPointers(self):
        self.nextNodePointer = None
        self.currentNodePointer = None
        self.lastNodePointer = None

    # def recvall(self, sock, n, retry=5):
    #     # Helper function to recv n bytes or return None if EOF is hit
    #     data = b''
    #     while len(data) < n:
    #         packet = sock.recv(n - len(data))
    #         if not packet:
    #             if retry>0:
    #                 time.sleep(.1)
    #                 self.recvall(sock, n, retry-1)
    #             else:
    #                 self.conn , address = self.updateSocket.accept()
    #                 return self.loadGraph('[]')
    #         data += packet
    #     return data

    def loadGraph(self, data):
        data = json.loads(data)

        self.graphData = data
        xLock.acquire()
        if not self.cmdQueue.empty():
            self.cmdQueue.get()
        self.cmdQueue.put(ExecutionThread.loadGraph)
        xLock.release()

    def updateGraph(self, data):
        data = json.loads(data)

        self.graphData = data
        xLock.acquire()
        if not self.cmdQueue.empty():
            self.cmdQueue.get()
        self.cmdQueue.put(ExecutionThread.updateGraph)
        xLock.release()

    def pause(self):
        xLock.acquire()
        if not self.cmdQueue.empty():
            self.cmdQueue.get()
        self.cmdQueue.put(ExecutionThread.pause)
        xLock.release()

    def drop(self):
        self.pause()
        self.loadGraph('[]')

    def kill(self):
        # self.updateSocket.close()
        xLock.acquire()
        if not self.cmdQueue.empty():
            self.cmdQueue.get()
        self.cmdQueue.put(ExecutionThread.kill)
        xLock.release()

    def configure(self, options):
        # print(options)
        try:
            framerate = options['framerate']
        except KeyError:
            pass
        else:
            self.executionThread.setFrameRate(framerate)

        try:
            mode = options['mode']
        except KeyError:
            pass
        else:
            self.executionThread.setMode(mode)

    def unpause(self):
        xLock.acquire()
        if not self.cmdQueue.empty():
            self.cmdQueue.get()
        self.cmdQueue.put(ExecutionThread.unpause)
        xLock.release()

    def goto(self, nextID):
        self.nextNodePointer = nextID

    def step(self):
        xLock.acquire()
        if not self.cmdQueue.empty():
            self.cmdQueue.get()
        self.cmdQueue.put(ExecutionThread.step)
        xLock.release()

    def updateStatus(self, ID):
        nodeID = ID
        self.status.append((nodeID, time.time()))# '{:12.1f}'.format(time.time())))

    def updateRunningNodes(self, running):
        self.runningNodes = running

    def getStatus(self):
        # string = '#'.join([str(i) for i in self.status])
        state = {'ran': self.status,
                            'running': self.runningNodes}
        self.status = []
        return state

    def getReport(self, nodeID):
        if self.executionThread.graph and nodeID in self.executionThread.graph.nodes:
            report = self.executionThread.graph.nodes[nodeID].report()
            logger.debug('Generated node instance report: {}'.format(report))
            return report
        else:
            return ''


class ExecutionThread(Thread):
    def __init__(self, cmdQueue, master):
        logger.debug('Creating new ExecutionThread.')
        self.graph = None
        self.framerate = 0.1
        self.master = master
        self.paused = True
        self.alive = True
        self._executeGraphStep = self.executeGraphStepPar
        self.cmdQueue = cmdQueue
        super(ExecutionThread, self).__init__()
        self.daemon = True
        # self.updateGraph()
        self.start()

    def setFrameRate(self, framerate):
        self.framerate = framerate
        logger.info('Framerate set to {}'.format(framerate))

    def setMode(self, mode):
        if mode == 'Parallel':
            self._executeGraphStep = self.executeGraphStepPar
        else:
            self._executeGraphStep = self.executeGraphStep

    def run(self):
        try:
            while self.alive:
                xLock.acquire()
                cmd = None
                if not self.cmdQueue.empty():
                    cmd = self.cmdQueue.get()
                xLock.release()
                # print(cmd)
                if cmd:
                    cmd(self)
                if self.paused:
                    # print('Sleeping')
                    time.sleep(1)
                    continue
                if self.alive and self.graph:
                    if not self.graph.returnValue == -1:
                        # print(self.graph.returnPriority)
                        self.pause()
                    # print(self.graph.nodes)
                    #print('Doing stuff.')
                    # self.executeGraphStep()
                    # self.executeGraphStepPar()
                    self._executeGraphStep()
                    self.master.updateRunningNodes(self.graph.runningNodes)
                else:
                    time.sleep(self.framerate)
            print('That\'s it. I\'m dead.')
            logger.info('ExecutionThread terminating')
        except:
            import traceback
            traceback.print_exc()
            print("for now failing execution thread")
            raise

    def pause(self):
        logger.info('Pausing')
        self.paused = True

    def unpause(self):
        logger.info('Unpausing')
        self.paused = False

    def kill(self):
        logger.info('Exiting')
        self.alive = False

    def step(self):
        print('Stepping up.')
        logger.debug('Performing single step')
        if self.executeGraphStep():
            self.master.updateRunningNodes(self.graph.runningNodes)
        # self.executeGraphStepPar()

    def loadGraph(self):
        from floppy.graph import Graph
        logger.debug('Attempting to load graph instance.')
        self.graph = Graph()
        # print(type(self.master.graph))
        self.graph.loadState(self.master.graphData, reuseIDs=True)
        logger.info('Successfully loaded graph instance.')
        #self.resetPointers()

    def updateGraph(self):
        from floppy.graph import Graph
        # self.graph = Graph()
        # print(type(self.master.graph))
        logger.debug('Attempting to update graph instance.')
        self.graph.updateState(self.master.graphData, reuseIDs=True)
        logger.info('Successfully updated graph instance.')
        #self.resetPointers()

    def executeGraphStep(self):
        if not self.graph:
            return
        if self.master.nextNodePointer:
            print(self.master.nextNodePointer, self.graph.nodes.keys())
            nextNode = self.graph.nodes[self.master.nextNodePointer]
            self.master.nextNodePointer = None
            if nextNode.check():
                with nextNode.runLock:
                    nextNode.run()
                    nextNode.notify()
                    self.master.sendStatus(nextNode.ID)
        else:
            running = False
            for node in self.graph.nodes.values():
                checked = node.check()
                running = checked if not running else True
                if checked:
                    with node.runLock:
                        node.run()
                        # self.graph.runNodePar(node)
                        # raise RuntimeError('Uncaught exception while executing node {}.'.format(node))
                        node.notify()
                        # self.master.sendStatus(node.ID)
                        self.master.updateStatus(node.ID)
                    break
            if not running:
                # print('Nothing to do here @ {}'.format(time.time()))
                time.sleep(self.framerate)
        return True

    def executeGraphStepPar(self):
        if self.master.nextNodePointer:
            # print(self.master.nextNodePointer, self.graph.nodes.keys())
            nextNode = self.graph.nodes[self.master.nextNodePointer]
            self.master.nextNodePointer = None
            if nextNode.check():
                with nextNode.runLock:
                    nextNode.run()
                    nextNode.notify()
                self.master.sendStatus(nextNode.ID)
        else:
            running = False
            readyNodes = []
            for node in self.graph.nodes.values():
                checked = node.check()
                running = checked if not running else True
                if checked and not node.locked:
                    node.lock()
                    readyNodes.append(node)
            # print([str(node) for node in readyNodes])
            for node in readyNodes:
                self.graph.runNodePar(node, cb=self.master.updateStatus, arg=node.ID)
            if not running:
                # print('Nothing to do here @ {}'.format(time.time()))
                time.sleep(self.framerate)



class Listener(Thread):
    def __init__(self, master):
        Thread.__init__(self)
        self.alive = True
        self.listenSocket = socket(AF_INET, SOCK_STREAM)
        self.listenSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.listenSocket.settimeout(1)
        self.listenSocket.bind((host, port))
        self.listenSocket.listen(1)
        logger.info('Interpreter listening on {}:{}'.format(host, port))
        self.master = master
        self.daemon = True
        self.start()

    def kill(self):
        self.alive = False
        time.sleep(.1)
        # self.listenSocket.shutdown(SHUT_RDWR)
        self.listenSocket.close()

    def run(self):
        try:
            while self.alive:
                # print('++++++++++Waiting for client.')
                try:
                    cSocket, address = self.listenSocket.accept()
                    print('++++++++++client accepted.')
                    logger.info('Client Connection from {} accepted'.format(address))
                except OSError as x:
                    continue
                # if str(address[0]) == '127.0.0.1':
                else:
                    CommandProcessor(cSocket, address, self.master, self)
        except:
            import traceback
            traceback.print_exc()
            print("for now failing in Listener")
            raise


class CommandProcessor(Thread):
    def __init__(self, cSocket, Adress, master, listener):
        super(CommandProcessor, self).__init__()
        self.master = master
        self.cSocket = cSocket
        self.listener = listener
        self.daemon = True
        self.start()

    def send(self, message):
        msg = struct.pack('>I', len(message)) + message.encode('utf-8')
        self.cSocket.sendall(msg)

    def run(self):
        try:
            while True:
                # message = self.cSocket.recv(1024).decode()
                message = self.receive()
                if message:
                    # logger.debug('Received command: {}...'.format(message[:10]))
                    if message == 'KILL':
                        # print('Killing myself')
                        self.send('Runner is terminating.')
                        self.listener.kill()
                        self.master.kill()
                        return
                    elif message == 'READY?':
                        self.send('READY')
                    elif message == 'PAUSE':
                        self.send('Runner is pausing.')
                        self.master.pause()
                    elif message == 'UNPAUSE':
                        self.send('Runner is unpausing.')
                        self.master.unpause()
                    elif message.startswith('UPDATE'):
                        self.send('Runner is updating.')
                        self.master.updateGraph(message[6:])
                    elif message.startswith('PUSH'):
                        self.send('Accepted pushed Graph. Runner is updating.')
                        self.master.loadGraph(message[4:])
                    elif message.startswith('DROP'):
                        self.send('Runner is dropping current graph.')
                        self.master.drop()
                    elif message.startswith('GOTO'):
                        nextID = int(message[4:])
                        self.send('Runner jumping to node {}.'.format(nextID))
                        self.master.goto(nextID)
                    elif message.startswith('CONFIGURE'):
                        msg = message[9:]
                        self.send('Configuration accepted.')
                        self.master.configure(json.loads(msg))
                    elif message == 'STEP':
                        self.send('Runner is performing one step.')
                        self.master.step()
                    elif message.startswith('STATUS'):
                        if self.master.executionThread.graph:
                            if not self.master.executionThread.graph.returnValue == -1:
    
                                self.send(json.dumps({'STATUS': 'RETURN', 'REPORT': (self.master.executionThread.graph.returnValue, self.master.executionThread.graph.returningNode)}))
                                continue
                        reportNode = message.split('***')[-1]
                        report = ''
                        if reportNode:
                            report = self.master.getReport(int(reportNode))
                        status = self.master.getStatus()
                        self.send(json.dumps({'STATUS': status, 'REPORT': report}))
                    else:
                        self.send('Command \'{}...\' not understood.'.format(message[:50]))
        except:
            import traceback
            traceback.print_exc()
            print("For now failing in commandprocessor")
            raise

    def recvall(self, sock, n,):
        # Helper function to recv n bytes or return None if EOF is hit
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return False
            data += packet
        return data

    def receive(self):
        data = None
        raw_msglen = self.recvall(self.cSocket, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        try:
            data = self.recvall(self.cSocket, msglen).decode('utf-8')
        except AttributeError:
            print('[ERROR] No data received.')
        return data


class RGIConnection(Thread):
    def __init__(self, verbose=True):
        super(RGIConnection, self).__init__()
        self.daemon = True
        self.cmdQueue = []
        self.socket = None
        self.host = None
        self.port = None
        self.alive = True
        self.start()
        
    def run(self):
        try:
            super(RGIConnection, self).run()
            while self.alive:
                try:
                    cmd = self.cmdQueue.pop(0)
                except IndexError:
                    time.sleep(.1)
                else:
                    answer = self._send(cmd[0])
                    cmd[1](answer)
        except:
            import traceback
            traceback.print_exc()
            print("for now failing in RGIConnection")
            raise

    def connect(self, host, port, validate=True):
        self.host = host
        self.port = port
        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.settimeout(5.)
        self.socket.connect((host, port))
        if validate:
            self.send('READY?', print)

    def disconnect(self):
        self.socket.close()

    def reconnect(self):
        self.disconnect()
        time.sleep(.5)
        self.socket.connect((self.host, self.port))

    def send(self, message, target):
        self.cmdQueue.append((message, target))

    def _send(self, message):
        # print('[REQUEST] ' + message)
        msg = struct.pack('>I', len(message)) + message.encode('utf-8')
        self.socket.sendall(msg)
        try:
            answer = '[ANSWER]  '+self._receive()
        except TypeError:
            answer = ''
        return answer

    def _recvall(self, sock, n,):
        """
        Helper function to recv n bytes or return None if EOF is hit
        :param sock:
        :param n:
        :return:
        """
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return False
            data += packet
        return data

    def _receive(self):
        data = None
        raw_msglen = self._recvall(self.socket, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        try:
            data = self._recvall(self.socket, msglen).decode('utf-8')
        except AttributeError:
            print('[ERROR] No data received.')
        return data


def terminate(clientSocket):
    message = 'Kill'
    clientSocket.send(message.encode())
    print('Kill command sent.')

    answer = clientSocket.recv(1024).decode()

    print(answer)


def sendCommand(cmd, host, port):
    port -= 1
    # global clientSocket
    clientSocket = socket(AF_INET, SOCK_STREAM)
    clientSocket.settimeout(5.)
    print(host,port)
    # host = '127.0.0.1'
    # port = 7236

    clientSocket.connect((host, port))
    clientSocket.send(cmd.encode())
    print('Sent {} command'.format(cmd))
    # terminate(clientSocket)
    try:
        answer = clientSocket.recv(1024).decode()
        print(answer)
    except timeout:
        print('Runner did not answer command \'{}\''.format(cmd))

    clientSocket.close()


def spawnRunner(listenPort):
    global port
    port = listenPort
    import os
    from importlib.machinery import SourceFileLoader
    customNodesPath = os.path.join(os.path.realpath(__file__)[:-10], 'CustomNodes')
    for i, path in enumerate(os.listdir(customNodesPath)):
        if path.endswith('py'):
            try:
                SourceFileLoader(str(i), os.path.join(customNodesPath, path)).load_module()
            except Exception as e:
                print('Warning: error in custom node:\n{}'.format(str(e)))
    r = Runner()
    print('Remote Graph Interpreter Initialized.'
          'Listening on port {}'.format(port))
    r.join()

if __name__ == '__main__':
    spawnRunner(port)
