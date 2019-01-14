from floppy.node import setNodesPath
from floppy.graph import Graph
from floppy.floppyUi import Painter2D, MainWindow
import sys
from PyQt5.QtWidgets import QApplication
import argparse
import logging

logger = logging.getLogger('Floppy')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('floppy.log')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)



def run():
    """ call only if floppy should create application window and run your application within floppy
        application.

        To select which nodes to be loaded from which pathes use the following code

        setNodesPath(...) 
        painter = initializePainter() 
        startUI(app,painter) 

        To embedd floppy within your application use

        setNodesPath(...) 
        painter = initializePainter() 
        win = MainWindow(painter=painter,parent=<immediateparentwidget>)
        
        and add to the layout defined on the <immediateparentwidget> if any to embedd
        the floppy window within the window of your application.

    """
    setNodesPath()
    logger.info('Starting Floppy Application with '+' '.join(sys.argv))
    app = QApplication(sys.argv)
    painter = initializePainter()

    import PyQt5.QtCore 

    startUI(app, painter)


def initializePainter():
    painter = Painter2D()
    Graph(painter=painter)

    return painter


def startUI(app, painter):
    win = MainWindow(painter=painter)
    win.setArgs(parseArgv())
    win.show()
    logger.debug('Startup successful. Handing main thread control to Qt main loop.')
    qtReturnValue = app.exec_()
    override, value = win.getFloppyReturnValue()
    if override:
        sys.exit(value)
    sys.exit(qtReturnValue)
    # try:
    #     sys.exit(app.exec_())
    # except KeyboardInterrupt:
    #     print('Keyboard Interrupt. Shutting down gracefully.')
    #     win.killRunner()

def parseArgv():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', action='store_true', required=False)
    parser.add_argument('--test', nargs=1, required=False, default=False)
    args = parser.parse_args()
    return args


