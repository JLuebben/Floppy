# import lauescript
# from lauescript.laueio import loader
# from lauescript.cryst.iterators import iter_atom_pairs
from lauescript.cryst.transformations import frac2cart
from lauescript.types.adp import ADPDataError
from floppy.node import Node, abstractNode, Input, Output, Tag
from floppy.Nodes.floppyBaseNodes import ForLoop
from floppy.FloppyTypes import Atom
import subprocess
import os

@abstractNode
class CrystNode(Node):
    Tag('Crystallography')


class ReadAtoms(CrystNode):
    Input('FileName', str)
    Output('Atoms', Atom, list=True)

    def run(self):
        super(ReadAtoms, self).run()
        from lauescript.laueio.loader import Loader
        loader = Loader()
        loader.create(self.i_FileName.value)
        print('1')
        mol = loader.load('quickloadedMolecule')
        print('2')
        self.o_Atoms = mol.atoms


class BreakAtom(CrystNode):
    Input('Atom', Atom)
    Output('Name', str)
    Output('Element', str)
    Output('frac', float, list=True)
    Output('cart', float, list=True)
    Output('ADP',float, list=True)
    Output('ADP_Flag', str)
    Output('Cell',float, list=True)

    def run(self):
        super(BreakAtom, self).run()
        atom = self.i_Atom.value
        # print(atom, atom.molecule.get_cell(degree=True))
        self.o_Name = atom.get_name()
        self.o_Element = atom.get_element()
        self.o_frac = atom.get_frac()
        self.o_cart = atom.get_cart()
        try:
            adp = atom.adp['cart_meas']
        except ADPDataError:
            adp = [0, 0, 0, 0, 0, 0]
        self.o_ADP = adp
        self.o_ADP_Flag = atom.adp['flag']
        self.o_Cell = atom.molecule.get_cell(degree=True)

    # def check(self):
    #     for inp in self.inputs.values():
    #         print(inp.value)
    #     return super(BreakAtom, self).check()


class Frac2Cart(CrystNode):
    Input('Position', float, list=True)
    Input('Cell', float, list=True)
    Output('Cart', float, list=True)

    def run(self):
        super(Frac2Cart, self).run()
        self.o_Cart = frac2cart(self.i_Position.value, self.i_Cell.value)


class SelectAtom(CrystNode):
    Input('AtomList', Atom, list=True)
    Input('AtomName', str)
    Output('Atom', Atom)

    def run(self):
        super(SelectAtom, self).run()
        name = self.i_AtomName.value
        self.o_Atom([atom for atom in self.i_AtomList.value if atom.get_name() == name][0])


class PDB2INS(CrystNode):
    Input('FileName', str)
    Input('Wavelength', float)
    Input('HKLF', int)
    Input('CELL', str)
    Input('SpaceGroup', str)
    Input('ANIS', bool)
    Input('MakeHKL', bool)
    Input('REDO', bool)
    Input('Z', int)
    Output('INS', str)
    Output('HKL', str)
    Output('PDB', str)

    def __init__(self, *args, **kwargs):
        super(PDB2INS, self).__init__(*args, **kwargs)
        self.stdout = ''

    def check(self):
        x = self.inputs['FileName'].isAvailable()
        return x

    def run(self):
        super(PDB2INS, self).run()
        opt =  ('pdb2ins',
                self._FileName,
                '-i',
                '-o __pdb2ins__.ins',
                ' -w '+str(self.i_Wavelength.value) if self.i_Wavelength.value else '',
                ' -h '+str(self.i_HKLF.value) if self.i_HKLF.value else '',
                ' -c '+str(self.i_CELL.value) if self.i_CELL.value else '',
                ' -s '+str(self.i_SpaceGroup.value) if self.i_SpaceGroup.value else '',
                ' -a ' if self.i_ANIS.value else '-a',
                ' -b ' if self.i_MakeHKL.value else '-b',
                ' -r ' if self.i_REDO.value else '',
                ' -z ' + str(self.i_Z.value) if self.i_Z.value else '',
                (' -d '+ self.i_FileName.value+'.sf') if not '@' in self.i_FileName.value else '')
        opt = ' '.join(opt)
        print(opt)
        # opt = [o for o in ' '.join(opt).split(' ') if o]
        # print(opt)
        self.p = subprocess.Popen(opt, shell=True, stdout=subprocess.PIPE)
        self.stdout = ''
        while True:
            line = self.p.stdout.readline()
            if not line:
                break
            self.stdout += str(line)[1:]
        # print('ran')
        self.o_INS(open('__pdb2ins__.ins', 'r').read())
        try:
            self.o_HKL(open('__pdb2ins__.hkl', 'r').read())
        except IOError:
            try:
                self.o_HKL(open('{}.hkl'.format(self._FileName), 'r').read())
            except IOError:
                self.o_HKL('')
        try:
            self.o_PDB(open('__pdb2ins__.pdb', 'r').read())
        except IOError:
            self.o_PDB(open('{}.pdb'.format(self._FileName), 'r').read())
        for file in os.listdir():
            if file.startswith('__pdb2ins__'):
                os.remove(file)

    def report(self):
        r = super(PDB2INS, self).report()
        r['stdout'] = self.stdout
        r['template'] = 'ProgramTemplate'
        return r


class BreakPDB(CrystNode):
    Input('PDB', str)
    Output('Code', str)
    Output('R1', float)

    def run(self):
        for line in self.i_PDB.value.splitlines():
            if line.startswith('REMARK   3   R VALUE') and '(WORKING SET)' in line:
                line = [i for i in line[:-1].split() if i]
                r1 = line[-1]
            elif line.startswith('HEADER'):
                line = [i for i in line[:-1].split() if i]
                code = line[-1]
        self.o_Code(code)
        self.o_R1(r1)


class ForEachAtomPair(ForLoop):
    Input('Start', Atom, list=True)
    Output('Atom1', Atom)
    Output('Atom2', Atom)

    # def __init__(self, *args, **kwargs):
    #     super(ForEachAtomPair, self).__init__(*args, **kwargs)

    def run(self):
        atoms = self.i_Start.value
        if self.fresh:
            self.x = 0
            self.y = 1
            self.end = len(atoms)-1
        self.fresh = False
        self.o_Atom1(atoms[self.x])
        self.o_Atom2(atoms[self.y])
        self.y += 1
        if self.y >= self.end:
            self.x += 1
            self.y = self.x+1
        if self.x >= self.end:
            self.o_Final(self.i_Start.value)
            self.done = True
