from floppy.node import Node, Input, Output, Tag, abstractNode
from floppy.CustomNodes.crystNodes import CrystNode
import subprocess
import os

@abstractNode
class ShelxNode(CrystNode):
    Tag('Shelx')


class RunShelxl(ShelxNode):
    Input('INS', str)
    Input('HKL', str)
    Input('List', int,  optional=True)
    Input('Cycles', int)
    Input('DAMP', int)
    Input('Type', str, select=('CGLS', 'L.S.'))
    Output('RES', str)
    Output('LST', str)
    Output('FCF', str)
    Output('R1', float)

    def __init__(self, *args, **kwargs):
        super(RunShelxl, self).__init__(*args, **kwargs)
        self.p = None
        self.stdout = ''

    def run(self):
        super(RunShelxl, self).run()
        with open('__tmp__.ins', 'w') as fp:
            fp.write(self.i_INS.value)
        with open('__tmp__.hkl', 'w') as fp:
            fp.write(self.i_HKL.value)

        self.p = subprocess.Popen('shelxl {}'.format('__tmp__'), shell=True, stdout=subprocess.PIPE)
        while True:
            line = self.p.stdout.readline()
            if not line:
                break
            self.stdout += str(line)[1:]
        #os.waitpid(self.p.pid, 0)
        with open('__tmp__.res', 'r') as fp:
            self.o_RES = fp.read()
        with open('__tmp__.lst', 'r') as fp:
            output = fp.read()
        for line in output.splitlines():
            if line.startswith(' R1 ='):
                line = [i for i in line.split() if i]
                R1 = float(line[2])
                break
        self.o_R1 = R1
        self.o_LST = output
        with open('__tmp__.fcf', 'r') as fp:
            output = fp.read()
        self.o_FCF = output


        for file in os.listdir():
            if file.startswith('__tmp__'):
                os.remove(file)

    def report(self):
        r = super(RunShelxl, self).report()
        r['template'] = 'ProgramTemplate'
        r['stdout'] = self.stdout
        return r



