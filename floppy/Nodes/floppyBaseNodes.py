from os.path import isfile
from floppy.node import Node,Input,Output,Tag,Info,Pin,abstractNode,ControlNode
import floppy.graph



class Switch(ControlNode):
    """
    Node for creating a basic if/else construction.
    The input 'Switch' accepts a bool. Depending of the
    value of the input, the 'True' or 'False' outputs are set to
    the value of the 'Start' input.
    As soon as the 'Control' input is set by one of the code
    branches originating from the 'True' and 'False' outputs,
    the value of the 'Final' output is set to the value of
    the 'Control' input.
    """
    Input('Switch', bool)
    Output('True', object)
    Output('False', object)
    Tag('If')
    Tag('Else')

    def __init__(self, *args, **kwargs):
        super(Switch, self).__init__(*args, **kwargs)
        self.fresh = True

    def check(self):
        if self.fresh:
            return not any((
                _inp
                for _inp in self.inputs.values()
                if ( _inp.name not in ['Control','Trigger'] or ( _inp.name == 'Trigger' and _inp.connected ) ) and not _inp.isAvailable() 
            ))
        #    for inp in (
        #        _inp
        #        for _inp in self.inputs.values()
        #        if ( inp.name not in ['Control','Trigger'] or ( inp.name == 'Trigger' and inp.connected ) ) and not inp.isAvailable() 
        #    ):
        #        # print('        {}: Prerequisites not met.'.format(str(self)))
        #        return False
        #    return True
        return self.inputs['Control'].isAvailable()

    def run(self):
        print('Executing node {}'.format(self))
        if self.fresh:
            if self.i_Switch:
                self.o_True = self.i_Start.value

            else:
                self.o_False = self.i_Start.value
        else:
            self.o_Final = self.i_Control.value

    def notify(self):
        if self.fresh:
            output = self.o_True if self.i_Switch.value else self.o_False
            for con in self.graph.getConnectionsOfOutput(output):
                con['inputNode'].setInput(con['inputName'], self.outputs[con['outputName']].value, loopLevel=self.loopLevel)
            self.fresh = False
            self.inputs['Start'].reset(self.loopLevel)
            self.inputs['Switch'].reset(self.loopLevel)
        else:
            output = self.o_Final
            for con in self.graph.getConnectionsOfOutput(output):
                con['inputNode'].setInput(con['inputName'], self.outputs[con['outputName']].value, loopLevel=self.loopLevel)
            self.fresh = True
        self.inputs['Control'].reset()
        for inp in self.inputs.values():
            Info.reset(inp,self.loopLevel)

#
# class Loop(ControlNode):
#     """
#     Generic loop node that iterates over a range(x: int)-like expression.
#     """
#     Input('Iterations', int)
#     Output('LoopBody', object)
#
#     def __init__(self, *args, **kwargs):
#         super(ControlNode, self).__init__(*args, **kwargs)
#         self.fresh = True
#         self.counter = 0
#         self.loopLevel = 0
#
#     # def prepare(self):
#     #     pass
#
#     def check(self):
#         if self.fresh:
#             for inp in self.inputs.values():
#                 if inp.name == 'Control':
#                     continue
#                 if not inp.isAvailable():
#                     # print('        {}: Prerequisites not met.'.format(str(self)))
#                     return False
#             return True
#         if self.counter > 0:
#             if self.inputs['Control'].isAvailable():
#                 return True
#
#     def run(self):
#         print('Executing node {}'.format(self))
#         if self.fresh:
#             self.counter = self._Iterations
#             self._LoopBody(self._Start)
#             self.fresh = False
#         elif self.counter == 0:
#             self._Final(self._Control)
#         else:
#             self.counter -= 1
#             self._LoopBody(self._Control)
#
#
#     def notify(self):
#         if self.counter > 0:
#             output = self.outputs['LoopBody']
#             for con in self.graph.getConnectionsOfOutput(output):
#                 outputName = con['outputName']
#                 nextNode = con['inputNode']
#                 nextInput = con['inputName']
#                 # nextNode.prepare()
#                 nextNode.setInput(nextInput, self.outputs[outputName].value, override=True, loopLevel=self.loopLevel+1)
#             self.inputs['Control'].reset()
#
#         else:
#             output = self.outputs['Final']
#             for con in self.graph.getConnectionsOfOutput(output):
#                 outputName = con['outputName']
#                 nextNode = con['inputNode']
#                 nextInput = con['inputName']
#                 nextNode.setInput(nextInput, self.outputs[outputName].value, loopLevel=self.loopLevel)
#             # self.prepare()
#             self.fresh = True
#             for inp in self.inputs.values():
#                 if not inp.name == 'Iterations':
#                     inp.reset()
#         # print(self.inProgress)
#         # exit()


class WaitAll(Node):
    """
    Watis for all inputs to be set before executing further nodes.
    """
    Input('Pass', object)
    Input('Wait', object)
    Output('Out', object)

    def run(self):
        self.o_Out = self.i_Pass.value

    def notify(self):
        super(WaitAll, self).notify()
        for inp in self.inputs.values():
            inp.reset(self.loopLevel)


class WaitAny(Node):
    """
    Waits for any inputs to be set. This doesn't make much sense, does it?
    """
    Input('Wait1', object)
    Input('Wait2', object)
    Output('Out', object)

    def setup(self):
        self.useInput = None

    def check(self):
        for inp in (
            _inp
            for _inp in self.inputs.values()
            if inp.valueSet
        ):
            # print('        {}: Prerequisites not met.'.format(str(self)))
            self.useInput = inp
            return True
        return False

    def run(self):
        super(WaitAny, self).run()
        self.o_Out = self.useInput.value


class Test(Node):
    Input('Test', bool)
    Output('T', bool)

    def run(self):
        super(Test, self).run()
        print(self.i_Test)
        self.o_T = self.i_Test.value


class TestNode(Node):
    Input('strInput', str)
    Output('strOutput', str)

    def run(self):
        super(TestNode, self).run()
        import time
        time.sleep(self.ID/2000.)
        self.o_strOutput = ''

    # def report(self):
    #     r = super(TestNode, self).report()
    #     r['template'] = 'plotTemplate'
    #     return r


class FinalTestNode(TestNode):
    def run(self):
        super(FinalTestNode, self).run()


class TestNode2(Node):
    Input('strInput', str)
    Input('floatInput', float, default=10.)
    Input('Input', str, default='TestNode')
    Output('strOutput', str)


class CreateBool(Node):
    """
    Creates a Boolean.
    """
    Input('Value', bool, select=(True, False))
    Output('Boolean', bool)

    def run(self):
        super(CreateBool, self).run()
        self.o_Boolean = self.i_Value.value


class CreateInt(Node):
    """
    Creates an Integer.
    """
    Input('Value', int, )
    Output('Integer', int)
    def run(self):
        super(CreateInt, self).run()
        self.o_Integer = self.i_Value.value


class CreateFloat(Node):
    """
    Creates a float.
    """
    Input('Value', float, )
    Output('Float', float)
    def run(self):
        self.o_Float = self.i_Value.value


class ReadFile(Node):
    """
    Node for reading a string from a file.
    """
    Input('Name', str)
    Output('Content', str)

    def run(self):
        super(ReadFile, self).run()
        fileName = self.i_Name.value
        try:
            with open(fileName, 'r') as fp:
                c = fp.read()
        except IOError:
            self.raiseError('IOError', 'No file named {}.'.format(fileName))
            return 1
        self.o_Content = c


class WriteFile(Node):
    Input('Name', str)
    Input('Content', str)
    Output('Trigger', object)

    def run(self):
        super(WriteFile, self).run()
        with open(self.i_Name.value, 'w') as fp:
            fp.write(self.i_Content.value)


@abstractNode
class ForLoop(ControlNode):
    """
    Generic loop node that iterates over all elements in a list.
    """
    # Input('Start', object, list=True)
    # Output('ListElement', object)

    def __init__(self, *args, **kwargs):
        super(ForLoop, self).__init__(*args, **kwargs)
        self.fresh = True
        self.waitForAllControlls = True
        self.counter = 0
        self.done = False
        self.loopLevel = 0

    def setInput(self, inputName, value, override=False, loopLevel=0):
        if inputName == 'Control':
            loopLevel = self.loopLevel
        super(ForLoop, self).setInput(inputName, value, override, loopLevel)
        # print('                                   XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')

    def check(self):
        if self.fresh:
            return not any((
                _inp
                for _inp in self.inputs.values()
                if ( _inp.name not in ['Control','Trigger'] or ( _inp.name == 'Trigger' and _inp.connected ) ) and not _inp.isAvailable
            ))
        #    for inp in (
        #        _inp
        #        for _inp in self.inputs.values()
        #        if ( _inp.name not in ['Control','Trigger'] or ( inp.name == 'Trigger' and inp.connected ) ) and not inp.isAvailable
        #    ):
        #        # print('        {}: Prerequisites not met.'.format(str(self)))
        #        return False
        #    return True
        return self.inputs['Control'].isAvailable()



    def notify(self):
        if not self.done:
            for output in ( 
                _value
                for _key,_value in self.outputs.items()
                if _key != 'Final'
            ):
                for con in self.graph.getConnectionsOfOutput(output):
                    con['inputNode'].setInput(con['inputName'], self.outputs[con['outputName']].value, override=True, loopLevel=self.loopLevel+1)
            self.inputs['Control'].reset(force=True)

        else:
            output = self.o_Final
            for con in self.graph.getConnectionsOfOutput(output):
                con['inputNode'].setInput(con['inputName'], self.outputs[con['outputName']].value, loopLevel=self.loopLevel)
            # self.prepare()
            self.fresh = True
            for inp in (
                _inp 
                for _inp in self.inputs.values()
                if inp.name != 'Iterations'
            ):
                inp.reset()
            self.counter = 0
            self.fresh = True
            self.done = False

    def report(self):
        r = super(ForLoop, self).report()
        ready = any((self.inputs['Control'].isAvailable(info=True), self.inputs['Start'].isAvailable(info=True)))
        r['ready'] = 'Ready' if ready else 'Waiting'
        return r


class ForEach(ForLoop):
    Input('Start', object, list=True)
    Output('ListElement', object)

    def run(self):
        super(ForEach, self).run()
        self.fresh = False
        try:
            self.o_ListElement = self.i_Start.value[self.counter]
        except IndexError:
            self.o_Final = self.i_Start.value
            self.done = True
        self.counter += 1


class IsEqual(Node):
    """
    Sets output to object1 == object2.
    """
    Input('object1', object)
    Input('object2', object)
    Output('Equal', bool)

    def run(self):
        super(IsEqual, self).run()
        self.o_Equal = (self.i_object1.value == self.i_object2.value)


class CreateString(Node):
    """
    Creates a string object.
    """
    Input('Str', str)
    Output('String', str)

    def run(self):
        super(CreateString, self).run()
        self.o_String = self.i_Str.value


@abstractNode
class DebugNode(Node):
    """
    Subclass this node for creating custom nodes related to debugging a graph.
    """
    Tag('Debug')

    def print(self, *args):
        string = ' '.join(args)
        print('[DEBUG]', string)


class DebugPrint(DebugNode):
    """
    Prints node instance specific debugging information to the cmd line. The input is than passed on straight to
    the output without manipulating the object.
    Custom debug information can be specified in an objects corresponding floppy.types.Type subclass.
    """
    Input('Object', object)
    Output('Out', object)

    def run(self):
        super(DebugPrint, self).run()
        obj = self.i_Object.value
        try:
            self.print(str(obj.__FloppyType__.debugInfoGetter(obj)()))
        except AttributeError:
            self.print(str(obj))
        self.o_Out = obj


class Join(Node):
    Input('Str1', str)
    Input('Str2', str)
    Output('Joined', str)

    def run(self):
        super(Join, self).run()
        self.o_Joined = ''.join([self.i_Str1.value, self.i_Str2.value])


class Break(Node):
    Input('Input', object)
    Output('Output', object)
    Tag('Loop')

    def run(self):
        super(Break, self).run()
        self.o_Output = self.i_Input.value

    def notify(self):
        output = self.outputs['Output']
        for con in self.graph.getConnectionsOfOutput(output):
            con['inputNode'].setInput(con['inputName'], self.outputs[con['outputName']].value, override=True, loopLevel=self.loopLevel-1)


class SetValue(Node):
    Input('Name', str)
    Input('Value', object)
    Output('Trigger', object)

    def __init__(self, *args, **kwargs):
        super(SetValue, self).__init__(*args, **kwargs)
        self.lastValue = (None, None)

    def run(self):
        super(SetValue, self).run()
        self.graph.STOREDVALUES[self.i_Name] = self.i_Value.value
        self.lastValue = (self.i_Name.value, self.i_Value.value)

    def report(self):
        r = super(SetValue, self).report()
        n, v = self.lastValue
        r['inputs'] = [(n, type(v).__name__, str(v))]
        return r


class GetValue(Node):
    """
    Node for accessing a parameter with a given name that was previously stored by a 'SetValue' node.
    
    Note that the 'TRIGGER' input is required if the parameter name is set as a default value with the graph editor.
    Otherwise, the node will be evaluated at an arbitrary time and not necessarily after a corresponding 'SetValue' node
    has been evaluated.
    
    If the name of the parameter is generated programmatically, the 'TRIGGER' input can be omitted.
    """
    # Input('Trigger', object)
    Input('Name', str)
    Output('Value', object)

    def run(self):
        self.o_Value = self.graph.STOREDVALUES[self.i_Name.value]


class Split(Node):
    Input('String', str)
    Input('Separator', str)
    Output('List', str, list=True)

    def run(self):
        super(Split, self).run()
        self.o_List = self.i_String.value.split(self.i_Separator.value)


class SplitLines(Node):
    Input('String', str)
    Output('List', str, list=True)

    def run(self):
        super(SplitLines, self).run()
        self.o_List = self.i_String.value.splitlines()


class ShowValues(Node):
    # Input('Trigger', object)
    Output('Output', object)

    def __init__(self, *args, **kwargs):
        super(ShowValues, self).__init__(*args, **kwargs)
        self.store = {}

    def run(self):
        super(ShowValues, self).run()
        self.o_Output = self.i_TRIGGER.value
        self.store = self.graph.STOREDVALUES.value

    def report(self):
        r = super(ShowValues, self).report()
        r['template'] = 'programTemplate'
        s = self.store
        keys = sorted(s.keys())
        r['stdout'] = '\\n'.join(['{}: {}'.format(key, str(s[key])) for key in keys])
        return r


class CreateList(Node):
    Input('Name', str)
    Output('List', object, list=True)

    def run(self):
        super(CreateList, self).run()
        l = []
        self.graph.STOREDVALUES[self.i_Name.value] = l
        self.o_List(l)


class AppendValue(Node):
    Input('Name', str)
    Input('Value', object)
    Output('List', object, list=True)

    def run(self):
        super(AppendValue, self).run()
        self.graph.STOREDVALUES[self.i_Name.value].append(self.i_Value.value)
        self.o_List = self.graph.STOREDVALUES[self.i_Name.value]


class ToString(Node):
    Input('Value', object)
    Output('String', str)

    def run(self):
        super(ToString, self).run()
        self.o_String = str(self.i_Value.value)


class MakeTable(Node):
    Input('Keys', str, list=True)
    # Input('Values', object, list=True)
    Output('Table', str)

    def run(self):
        super(MakeTable, self).run()
        for key, value in self.graph.STOREDVALUES.items():
            print(key, value)
        keys = self.i_Keys.value
        #data = [self.graph.STOREDVALUES[key] for key in keys]
        # cols = len(keys)
        table = ''
        for key in keys:
            table += '{} '.format(key)
        table += '\n'
        alive = True
        while alive:
            for col in (
                self.graph.STOREDVALUES[_key]
                for _key in keys
            ):
                try:
                    value = col.pop(0)
                except IndexError:
                    alive = False
                    break
                table += '{} '.format(value)
        print(table)
        self.o_Table = table


class TestReturn(Node):
    Input('Value', object)
    Input('Reference', object, optional=True)

    def run(self):
        super(TestReturn, self).run()
        val = 0 if self._Value == self.i_Reference else 1
        print(self.i_Value.value, self.i_Reference.value)
        self._return('Test Return Value')

class ReturnIsEqual(Node):
    Input('Value', object)
    Input('Reference', object, optional=True)

    def run(self):
        # super(ReturnIsEqual, self).run()
        val = 0 if self.i_Value.value == self.i_Reference else 1
        # print(self._Value, self._Reference)
        self._return(val)

class SimpleReturn(Node):
    def run(self):
        self._return()

# TODO Cleanup this mess. Prepare method and probably a lot of other stuff is no longer needed.

class Int2Float(Node):
    Input('Integer', int)
    Output('Float', float)

    def run(self):
        self.o_Float = float(self.i_Integer.value)


class String2Float(Node):
    Input('String', str)
    Output('Float', float)

    def run(self):
        self.o_Float = float(self.i_String.value)



class DynamicSubGraph(Node):
    """
    Node for executing a sub graph that is not specified before executing the owning graph.
    The value of GraphID is used as a reference for SetDynamicInput nodes.
    In contrast to SubGraph nodes, the value of GraphName can be set dynamically and does not need
    to be a default value.
    This means that it is not possible to determine the required inputs for the sub graph. Instead,
    SetDynamicInput nodes are used to set input values of the sub graph.
    """
    Input('GraphID', str)
    Input('GraphName', str)
    Output('ReturnValue', object)

    def setup(self):
        self.subGraph = floppy.graph.Graph()

    def run(self):
        fileName = self.i_GraphName.value
        self.subGraph.load(fileName)
        for name, value in self.graph.DYNAMICINPUTVALUES[self.i_GraphID.value].items():
            self.subGraph.INPUTVALUES[name] = value
        self.subGraph.selfExecute()
        self.o_ReturnValue = (self.subGraph.returnValue, self.subGraph.returningNode)


class InputNode(Node):
    """
    Special Node for accessing values that are remain constant during a graph's execution time but are set-up
    programmatically before the graph's execution.
    """
    Input('InputName', str)
    Output('InputValue', object)

    def setup(self):
        self.graph.INPUTNODES.append(self)

    def run(self):
        self.o_InputValue = self.graph.INPUTVALUES[self.i_InputName.value]
        
    def __del__(self):
        self.graph.INPUTNODES.remove(self)
        del self
        # super(InputNode, self).__del__()


class SetDynamicInput(Node):
    """
    Node for specifying the input values of DynamicSubGraph nodes.
    The value of GraphID determines to which DynamicSubGraph node the node
    corresponds.
    InputName must correspond to the name of one of the inputs in the sub graph
    called by the DynamicSubGraph node.
    InputValue is the corresponding value.
    """
    Input('GraphID', str)
    Input('InputName', str)
    Input('InputValue', object)
    Output('Trigger', object)

    def run(self):
        try:
            self.graph.DYNAMICINPUTVALUES[self.i_GraphID][self.i_InputName.value] = self.i_InputValue.value
        except KeyError:
            self.graph.DYNAMICINPUTVALUES[self.i_GraphID] = {self.i_InputName.value: self.i_InputValue.value}


