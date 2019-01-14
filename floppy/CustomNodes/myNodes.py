from floppy.node import Node, Input, Output, Tag, abstractNode
from floppy.FloppyTypes import StructureInfo, Atom
import time
import random
import subprocess

class AMyNode(Node):
    Input('Inta', int)
    Input('Intb', int)
    Input('Int1', int, select=[1,2,3,4])
    Input('Int3', int, select=[1,2,3,4])
    Output('Int2', int)

    def run(self):
        self.o_Int2 = self.i_Int1.value + 1




class FakeWorkNode(Node):
    Input('inp', object)
    Output('out', object)

    def run(self):
        print('Working @ {}'.format(str(self.i_inp.value)))
        time.sleep(random.randrange(1,5))
        print('Done')
        # self._return('Test Return Value')


class IncrementNode(Node):
    Output('Integer', int)

    def setup(self):
        self.i = 0

    def run(self):
        self.o_Integer = self.i
        self.i += 1


class RandomFloat(Node):
    Output('Float', float)

    def run(self):
        self.o_Float = random.random()


class RunProgram(Node):
    """
    Node for calling an external program of given name and given command line arguments.
    Returns the program's return value and its stdout output.
    """
    Input('ProgramName', str)
    Input('Arguments', str)
    Output('ReturnValue', int)
    Output('StdOut', str)

    def run(self):
        programName = self.i_ProgramName.value
        args = [programName] + self.i_Arguments.value.split()
        r = 0
        try:
            out = subprocess.check_output(args, shell=True,stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            out = e.output
            r = e.returncode
        self.o_ReturnValue = r
        self.o_StdOut = out




class Range(Node):
    Input('EndValue', int)
    Output('ValueList', int, list=True)
    def run(self):
        self.o_ValueList = list(range(self.i_EndValue.value))


class Int2Str(Node):
    Input('Int', int)
    Output('Str', str)
    def run(self):
        self.o_Str = str(self.i_Int.value)












class PlotNode2(Node):
    Input('XX', str)
    Output('YY', str)

    def __init__(self, *args, **kwargs):
        super(PlotNode2, self).__init__(*args, **kwargs)
        self.time = time.time()
        self.points = []
        self.counts = 0

    def check(self):
        t = time.time()
        if t - self.time > 3:
            self.time = t
            return True

    def run(self):
        super(PlotNode2, self).run()
        self.counts += 1
        self.points.append(
            (self.counts, (random.randint(5, 20), random.randint(5, 20), random.randint(5, 20), random.randint(5, 20))))

    def report(self):
        r = super(PlotNode2, self).report()
        r['template'] = 'PlotTemplate'
        r['points'] = self.points[:]
        r['keep'] = 'points'
        self.points = []
        return r

