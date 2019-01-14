import json
import re
import os
import os.path
from collections import OrderedDict
from copy import copy
from threading import Lock
from importlib.machinery import SourceFileLoader
import functools as ft
import warnings
import logging
from types import MappingProxyType
from copy import copy
#import types
from floppy.FloppyTypes import Type, MetaType, FLOPPYTYPEMAP
import traceback
from pprint import pprint

logger = logging.getLogger("Floppy")


class InputNotAvailable(Exception):
    pass


class InputAlreadySet(Exception):
    pass

class SaveNodesError(Exception):
    pass

class LoadNodesError(Exception):
    pass

class NodeError(Exception):
    pass

class ManagedNodeError(NodeError):
    pass

class NodeUpdateError(ManagedNodeError):
    def __init__(self,message,run = None,setup = None):
        super(NodeUpdateError,self,).__init__(message)
        self.runerror = run
        self.setuperror = setup
        

_customNodesPath = []
_customNodesSavePath = ''

_nodeclasses = OrderedDict()
_STATIC_NODE_COUNTS = [0,0]
_node_methods = ['run','setup','check']

validatenodename = re.compile( r"^(?:\w|_)+$").match

def abstractNode(cls: type):
    """
    Removes a Node class from the NODECLASSES dictionary and then returns the class object.
    Use this as a decorator to stop a not fully implemented Node class from being available in the editor.
    :param cls: Node class object.
    :return: Unmodified node class object.
    :rtype: Node
    """
    _STATIC_NODE_COUNTS[0] += 1
    _nodeclasses[cls.__name__].__abstract__ = True
    return cls


class Pin(object):
    """
    Class for storing all information required to represent a input/output pin.
    """
    def __init__(self, pinID, info, node):
        self.ID = pinID
        self.ID = pinID
        self.name = info.name
        self.info = info
        info.ID = pinID
        self.node = node


class Info(object):
    """
    Class for handling all information related to both inputs and outputs.
    """

    _property_prefix = '_'
    __pintype__ = Pin

    def __init__(self, name, varType, hints=None, default='', select=None, owner=False, list=False, optional=False,iotype = None):
        self.multiConn = 0
        self.multiCounter = 0
        self.name = name
        self.connected = False
        self.varType = varType
        self.optional = optional
        if not hints:
            self.hints = [varType.__name__]
        else:
            self.hints = [varType.__name__] + hints
        self.default = default
        self.valueSet = False
        self.value = None
        self.select = select
        self.owner = owner
        self.list = list
        self.loopLevel = 0
        self.usedDefault = False
        self.pure = 0

    def setOwner(self, owner):
        self.owner = owner

    def setDefault(self, value):
        if not self.varType == object and not issubclass(self.varType, Type):
            try:
                self.default = self.varType(value)
            except ValueError:
                self.default = ''
            if self.varType == bool:
                try:
                    if value.upper() == 'TRUE':
                        self.default = True
                    else:
                        self.default = False
                except:
                    self.default = value
        else:
            self.default = value

    def __str__(self):
        return 'INFO'

    def toDict(self):
        return dict(
            name = self.name,
            varType = self.varType,
            hints = self.hints[1:] if self.hints[0] == self.varType.__name__ else self.hints,
            default = self.default,
            select = self.select,
            list = self.list,
        )
        #def __init__(self, name, varType, hints=None, default='', select=None, owner=False, list=False, optional=False,iotype = None):
        

    def reset(self, nodeLoopLevel=0, force=False):
        if nodeLoopLevel > self.loopLevel and not force:
            # print('Not resetting Input {} because owing node has higher node\n'
            #       'level than the node setting the Input: {}vs.{}'.format(self.name, nodeLoopLevel, self.loopLevel))
            return
        self.default = None
        self.valueSet = False
        self.value = None
        self.multiCounter = 0


class InputInfo(Info):
    _property_prefix = 'i_'
    @property
    def PropertyName(self):
        return self.__class__._property_prefix + self.name

    def __get__(self,instance,objtype = None):
        try:
            return instance.inputs[self.name]
        except KeyError:
            raise AttributeError("'{}' type object has not Attribute '{}{}'".format(instance.__class__,self.__class__._property_prefix,self.name))

    def __set__(self,instance,value):
        try:
            with instance.inputLock:
                instance.inputs[self.name].set(value, loopLevel=instance.loopLevel)
        except KeyError:
            raise AttributeError("'{}' type object has not Attribute '{}{}'".format(instance.__class__,self.__class__._property_prefix,self.name))

    def __getattribute__(self,name):
        if name != 'value':
            if name == 'r_value':
                return self.__dict__['value']
            return super(InputInfo,self).__getattribute__(name)
        if self.valueSet:
            if not self.varType == object:
                if isinstance(self.varType, MetaType):
                    if self.list:
                        return [self.varType.checkType(i) for i in self.__dict__[name]]
                    return self.varType.checkType(self.__dict[name])
                if self.list:
                    return [self.varType(i) for i in self.__dict[name]]
                return self.varType(self.__dict[name])
            return self.__dict__[name]
        elif self.default != None and not self.connected:
            self.usedDefault = True if self.loopLevel > 0 else False
            if not self.varType == object and self.default:
                return self.varType(self.default)
            return self.default
        raise InputNotAvailable('Input not set for node.')

    def __call__(self, noException=False):
        try:
            return self.value
        except Exception:
            if noException:
                return None
            raise

    def set(self, value, override=False, loopLevel=0):
        if self.valueSet and not override:
            raise InputAlreadySet('Input \'{}\' of node \'{}\' is already set.'.format(self.name, str(self.owner)))
        self.value = value
        self.valueSet = True
        if not self.name == 'Control':
            self.loopLevel = loopLevel
        else:
            self.multiCounter += 1

    def setPure(self):
        self.pure = 1

    def setConnected(self, value: bool):
        self.connected = value

    def setMultiConn(self, value):
        self.multiConn = value

    def isAvailable(self, info=False):
        # if self.owner.__class__.__name__.startswith('GetValue'):
        #     print()
        #     print(self.name)
        #     print(self.default, self.connected, self.usedDefault, self.pure, self.loopLevel)
        #     print(self.loopLevel)
        if self.name == 'Control':
            return self._isAvailableControl(info)
        if info:
            if self.valueSet:
                return True
            elif self.default != None and not self.connected and not self.usedDefault and self.pure < 2:
                return True
            return False
        # print(1)
        if self.valueSet:
            # print(2)
            # print('^^^^^^^^^^^^^^^^^^', self.name, self.r_value, self.valueSet)
            return True
        elif self.default != None and not self.connected and not self.usedDefault and self.pure < 2:
            # print(3)
            if self.pure == 1 and self.connected:
                self.pure = 2
            # print(4)
            # self.usedDefault = True
            # print('+++++++++++++++++', self.name, self.r_value, self.valueSet, self.owner, self.usedDefault, self.pure)
            return True
        # print(self.default, self.connected, self.usedDefault, self.pure, self.loopLevel)
        return False

    def _isAvailableControl(self, info):
        if self.multiCounter < self.multiConn:
            return False
        if info:

            if self.valueSet:
                return True
            elif self.default != None and not self.connected and not self.usedDefault and self.pure < 2:
                return True
            return False
        if self.valueSet:
            # print('^^^^^^^^^^^^^^^^^^', self.name, self.r_value, self.valueSet)
            return True
        elif self.default != None and not self.connected and not self.usedDefault and self.pure < 2:
            if self.pure == 1:
                self.pure = 2
            # self.usedDefault = True
            # print('+++++++++++++++++', self.name, self.r_value, self.valueSet, self.owner, self.usedDefault, self.pure)
            return True
        return False

    def toDict(self):
        _dict = super(InputInfo,self).toDict()
        _dict['optional'] = self.optional
        return _dict

class OutputInfo(Info):
    _property_prefix = 'o_'
    @property
    def PropertyName(self):
        return self.__class__._property_prefix + self.name

    
    def __call__(self, value):
        try:
            value.__FloppyType__ = self.varType
        except AttributeError:
            pass
        self.value = value
        self.valueSet = True

    def __get__(self,instance,objtype = None):
        try:
            return instance.outputs[self.name]
        except KeyError:
            raise AttributeError("'{}' type object has no Attribute '{}{}'".format(instance.__class__,self.__class__._property_prefix,self.name))
        
    def __set__(self,instance,value):
        try:
            _output = instance.outputs[self.name]
        except KeyError:
            raise AttributeError("'{}' type object has not Attribute '{}{}'".format(instance.__class__,self.__class__._property_prefix,self.name))
        try:
            value.__FloppyType__ = _output.varType
        except AttributeError:
            pass
        _output.value = value
        _output.valueSet = True


class _NodeClassIOProxy(object):
    @classmethod
    def __getio__(cls,nodecls):
        return dict()

    __iokind__ = ''
    __slots__ = ("_nodecls",)

    def __init__(self,nodecls):
        self._nodecls = nodecls

    def __contains__(self,ioname):
        for _found in (
            ioname in self.__class__.__getio__(_cls)
            for _cls in self._nodecls.__mro__
        ):
            return True
        return False

    def __getitem__(self,ioname):

        for _item in (
            self.__class__.__getio__(_cls).get(ioname)
            for _cls  in self._nodecls.__mro__
        ):
            if _item is not None:
                return _item
        raise KeyError("'{}' {} type unknown or abstract".format(ioname,self.__class__.__iokind__))

    def __iter__(self):
        yield from ( 
            _item
            for _cls in self._nodecls.__mro__
            for _item in self.__class__.__getio__(_cls)
        )

    def __len__(self):
        return sum((
            len(self.__class__.__getio__(_cls))
            for _cls in self._nodecls.__mro__
        ))

    def __repr__(self):
        return "<{}: {}>".format(self.__class__.__name__,self.__str__())

    def __str__(self):
        return str({
            _clsname:_cls
            for _clsname,_cls in self._get_iterator('items')
        })

    def __eq__(self,other):
        if not isinstance(other,_NodeClassIOProxy):
            return False
        for _a,_b in zip(self._get_iterator('keys'),other._get_iterator('keys')):
            if _a != _b:
                return False
        return True

    def __ne__(self,other):
        if not isinstance(other,_NodeClassIOProxy):
            return True
        for _a,_b in zip(iter(self),iter(other)):
            if _a != _b:
                return True
        return False

    def __hash__(self):
        return hash(frozenset({_key:_io for _key,_io in self._get_iterator('items')}))

    def copy(self):
        return {
            _key : _io
            for _cls in self._nodecls.__mro__
            for _key,_io in self.__class__.__getio__(_cls)
        }

    def get(self,key,default = None):
        for _item in (
            self.__class__.__getio__(_cls).get(key)
            for _cls  in self._nodecls.__mro__
        ):
            if _item is not None:
                return _item
        return default

    def _get_iterator(self,kind):
        if kind == 'keys' :
            return (
                _ioname
                for _cls in self._nodecls.__mro__
                for _ioname in self.__class__.__getio__(_cls).keys()
            )
        if kind == 'perclasskeys' :
            return (
                (_ioname,_cls)
                for _cls in self._nodecls.__mro__
                for _ioname in self.__class__.__getio__(_cls).keys()
            )
        if kind == 'values':
            return (
                _ioitem
                for _cls in self._nodecls.__mro__
                for _ioitem in self.__class__.__getio__(_cls).values()
            )
        if kind == 'perclassvalues':
            return (
                (_ioitem,_cls)
                for _cls in self._nodecls.__mro__
                for _ioitem in self.__class__.__getio__(_cls).values()
            )
        if kind == 'perclassitems':
            return (
                (_ioname,_ioitem,_cls)
                for _cls in self._nodecls.__mro__
                for _ioname,_ioitem in self.__class__.__getio__(_cls).items()
            )
        return (
            (_ioname,_ioitem)
            for _cls in self._nodecls.__mro__
            for _ioname,_ioitem in self.__class__.__getio__(_cls).items()
        )

    class _ProxyView(object):
        def __init__(self,proxy,kind):
            self.__proxy = proxy
            self.__kind = kind

        def __len__(self):
            return len(self.__proxy)

        def __iter__(self):
            yield from self.__proxy._get_iterator(self.__kind)  

        def __contains__(self,value):
            if self.__kind == 'keys':
                return value in self.__proxy
            if self.__kind == 'items':
                return value[0] in self.__proxy
            try:
                return value.__name__ in self.__proxy 
            except AttributeError:
                return False

    def values(self,perclass=False):
        if perclass:
            return self.__class__._ProxyView(self,'perclassvalues')
        return self.__class__._ProxyView(self,'values')

    def keys(self,perclass = False):
        if perclass:
            return self.__class__._ProxyView(self,'perclasskeys')
        return self.__class__._ProxyView(self,'keys')

    def items(self,perclass = False):
        if perclass:
            return self.__class__._ProxyView(self,'perclassitems')
        return self.__class__._ProxyView(self,'items')

# needed below to ensure that any edit of managedNodeClasses will cause 
# their __edit_of__ special to be set to the original edited class in case
# managed it self
def _managed_addInput(cls, *args,**kwargs):
    print(cls)
    if cls.__edit_of__ is None:
        cls.__edit_of__ = copy(cls)
    super(cls,cls)._addInput(*args,**kwargs)
    
def _managed_addOutput(cls, *args,**kwargs):
    print(cls)
    if cls.__edit_of__ is None:
        cls.__edit_of__ = copy(cls)
    super(cls,cls)._addOutput(*args,**kwargs)

def _managed_removeInput(cls,name):
    print(cls)
    _lastedit = cls.__edit_of__
    if _lastedit is None:
        cls.__edit_of__ = copy(cls)
    _numinputs = len(cls.__classinputs__)
    super(cls,cls)._removeInput(name)

    if len(cls.__classinputs__) == _numinputs:
        cls.__edit_of__ = _lastedit 

def _managed_removeOutput(cls,name):
    print(cls)
    _lastedit = cls.__edit_of__
    if _lastedit is None:
        cls.__edit_of__ = copy(cls)
    _numoutputs = len(cls.__classoutputs__)
    super(cls,cls)._removeOutput(name)
    if len(cls.__classoutputs__) == _numoutputs:
        cls.__edit_of__ = _lastedit


class MetaNode(type):
    """
    Meta class for the Node class. Makes node declaration objects available in the class's scope and registers each
    Node object to have a convenient way of accessing all subclasses of Node.
    """

    class _NodeInputsProxy(_NodeClassIOProxy):
        __slots__ = tuple()

        @classmethod
        def __getio__(cls,nodecls):
            return nodecls.__classinputs__ if isinstance(nodecls,MetaNode) else dict()

        __iokind__ = 'input'


    class _NodeOutputsProxy(_NodeClassIOProxy):
        __slots__ = tuple()

        @classmethod
        def __getio__(cls,nodecls):
            return nodecls.__classoutputs__ if isinstance(nodecls,MetaNode) else dict()

        __iokind__ = 'output'

    
    inputs = []
    outputs = []

    _ignore_super_passon = re.compile(
        r"^\s*(?:super\(\s*(?:type\(\s*self\s*\)|self\.__class__|(?P<subclass>\w+))\s*,\s*self\s*\)|(?P<baseclass>\w+))\.(?P<method>{})\(\s*(?:(?P<superself>self)\s*)?\)\s*$".format(
            "|".join(_node_methods)
        )
    )

    @classmethod
    def __prepare__(metacls, name, bases):
        MetaNode.inputs = []
        MetaNode.outputs = []
        MetaNode.tags = []
        return {
            'Input': MetaNode.addInput,
            'input': MetaNode.addInput,
            'Output': MetaNode.addOutput,
            'output': MetaNode.addOutput,
            'Tag': MetaNode.addTag,
            'tag': MetaNode.addTag
        }

    @classmethod
    def addTag(cls,*args):
        for arg in args:
            cls.tags.append(arg)


    @classmethod
    def addInput(
        cls,
        name: str,
        varType: object,
        hints=None,
        default='',
        select=None,
        list=False,
        optional=False,
        iotype = InputInfo
    ):
        assert(issubclass(iotype,InputInfo),"iotype must be subclass of InputInfo")
        assert(issubclass(iotype.__pintype__,Pin),"'{}.__pintype__' must be subclass of Pin".format(iotype.__name__))
        cls.inputs.append({
            'name': name,
            'varType': varType,
            'hints': hints,
            'default': default,
            'select': select,
            'list': list,
            'optional': optional,
            'iotype': iotype
        })

    @classmethod
    def addOutput(
        cls,
        name: str,
        varType: object,
        hints=None,
        default='',
        select=None,
        list=False,
        iotype = OutputInfo
    ):
        assert(issubclass(iotype,OutputInfo),"iotype must be subclass of OutputInfo")
        assert(issubclass(iotype.__pintype__,Pin),"'{}.__pintype__' must be subclass of Pin".format(iotype.__name__))
        cls.outputs.append({
            'name': name,
            'varType': varType,
            'hints': hints,
            'default': default,
            'select': select,
            'list': list,
            'iotype': iotype
        })

    def __new__(cls, name, bases, classdict):
        #from pprint import pprint
        #pprint(('cls:',cls,'n:',name,'b:',bases,'r:',[],'cd:',classdict))
        result = type.__new__(cls, name, bases, classdict)
        # result.__dict__['Input'] = result._addInput
        #NODECLASSES[name] = result
        _nodeclasses[name] = result
        #try:
        #    result.__inputs__ = result.__bases__[0].__inputs__.copy()
        #except AttributeError:
        
        result.__classinputs__ = OrderedDict()
        result.__inputs__ = cls._NodeInputsProxy(result)
        #try:
        #    result.__outputs__ = result.__bases__[0].__outputs__.copy()
        #except AttributeError:
        
        result.__classoutputs__ = OrderedDict()
        result.__outputs__ = cls._NodeOutputsProxy(result)
        result.__abstract__ = False
        result.__managed__ = False
        result.__edit_of__ = None
        if '__run_source__' not in result.__dict__:
            result.__run_source__ = None
        if '__setup_source__' not in result.__dict__:
            result.__setup_source__ = None

        try:
            result.__tags__ = result.__bases__[0].__tags__.copy()
        except AttributeError:
            result.__tags__ = []

        for inp in MetaNode.inputs:
            result._addInput(**inp)

        for out in MetaNode.outputs:
            result._addOutput(**out)

        for tag in MetaNode.tags:
            result._addTag(tag)
        #pprint(('cls:',cls,'n:',name,'b:',bases,'r:',dir(result),'cd:',classdict))
        _STATIC_NODE_COUNTS[1] += 1
        return result

    @classmethod
    def isabstract(cls,nodecls):
        return isinstance(nodecls,cls) and nodecls.__abstract__

    @classmethod
    def isnotabstract(cls,nodecls):
        #print(cls,nodecls,nodecls.__abstract__)
        return isinstance(nodecls,cls) and not nodecls.__abstract__
        

    @classmethod
    def ismanaged(cls,nodecls):
        return isinstance(nodecls,cls) and nodecls.__managed__

    @classmethod
    def isnotmanaged(cls,nodecls):
        return isinstance(nodecls,cls) and not nodecls.__managed__

    @classmethod
    def hasedits(cls,nodecls):
        return isinstance(nodecls,cls) and nodecls.__managed__ and nodecls.__edit_of__ is not None

    @classmethod
    def issaved(cls,nodecls):
        return isinstance(nodecls,cls) and nodecls.__managed__ and nodecls.__edit_of__ is None

    @classmethod
    def loadFromString(cls,string,rename = None):
        _name,_bodystring =  string.strip().split(':::')
        try:
            _body = json.loads(_bodystring)
        except json.decoder.JSONDecodeError as _reason:
            logger.error("Cannot load managed node class '{}'. String <{}> is invalid JSON. ({})".format(_name,_bodystring,_reason))
            return None
        else:
            if _name != _body["name"]:
                logger.error("body '{}' does not describe managed node class '{}'".format(_bodystring,_name))
            logger.debug('Creating managed node class <{}>. Base class is <{}>.'.format(_body['name'], _body['baseClass']))
            
        return cls.loadManaged(
            _name if rename is None else rename,
            (_body['baseClass'],),
            _body
        )

    @classmethod
    def updateManaged(cls,nodecls,bodyparts):
        if not isinstance(nodecls,cls) or cls.isnotmanaged(nodecls) or nodecls.__name__ not in _nodeclasses:
            raise ManagedNodeError("node '{}' is not a valid managed node class".format(nodecls.__name__))
        _errors = {}
        _updated = {}
        for _method,_methodbody in (
            (
                _meth,
                bodyparts[_meth]
            )
            for _meth in _node_methods
            if _meth in bodyparts
        ):
            _isdefault = cls._ignore_super_passon.match(_methodbody)
            if (
                _isdefault is not None and
                _isdefault.group('subclass') in (cls.__name__,None) and
                _isdefault.group('baseclass') in (cls.__bases__[0].__name__,None) and
                _isdefault.group('method') == _method and
                _isdefault.group('superself') in ('self',None)
            ):
                continue
    #_ignore_super_passon = re.compile(
    #    r"^\s*(?:super\((?(?:type\(self\)|self\.__class__|(?P<subclass>\w+)),self)?:\)|(?P<baseclass>\w+))\.(?P<method>{})\((?P<superself>self)\)\s*$".format(
    #        "|".join(_node_methods)
    #    )
    #)
            _context = {}
            try:
                exec("""
def {} (self):\n
    {}
""".format(
                        _method,
                        "\n    ".join(
                        _methodbody.split('\n')
                        )
                    ),
                    _context
                )
                _updated[_method] = _context[_method]
            except:
                _errors[_method] = traceback.format_exc()
        if len(_errors) > 0:
            raise NodeUpdateError("Failed to update '{}' method".format("' and '".join(_errors.keys())),**_errors)
        for _methodname,_callable in _updated.items():
            setattr(nodecls,'_meth',_callable.__get__(None,nodecls))
            setattr(nodecls,'__{}_source__'.format(_methodname),bodyparts[_methodname])
        if nodecls.__edit_of__ is None:
            #from PyQt5.QtCore import pyqtRemoveInputHook
            #import pdb
            #pyqtRemoveInputHook()
            #pdb.set_trace()

            nodecls.__edit_of__ = copy(nodecls)
        return nodecls
        

    @classmethod
    def makeManaged(cls,name,baseClass,inputs = None,outputs = None,nodemethods = {},rename = None,nosafe = False):
        if not isinstance(baseClass,cls):
            if not isinstance(baseClass,str) or baseClass not in _nodeclasses:
                raise ManagedNodeError("base class '{}' invalid ".format(baseClass))
            baseClass = _nodeclasses[baseClass]
        _nodeclass = _nodeclasses.get(name,None)
        if _nodeclass is not None and cls.isnotmanaged(_nodeclass):
            raise ManagedNodeError("can not edit builtin {}node '{}'".format('abstract ' if cls.isabstract(_nodeclasses[name]) else '',name))
        if rename != name and rename is not None:
            _renamenodeclass = _nodeclasses.get(rename,None)
            if _renamenodeclass is None:
                raise ManagedNodeError("Can't rename node class'{}' to '{}': not found".format(rename,name))
            if _renamenodeclass != baseClass:
                if _nodeclass is not None:
                    raise ManagedNodeError("Can't rename node class'{}' to '{}': target node exists".format(rename,name))
                if _renamenodeclass.__bases__[0] != baseClass:
                    raise ManagedNodeError("Can't rename node class'{}' to '{}': baseclasses do not match ('{}' != '{}')".format(rename,name,baseClass.__name__,_renamenodeclass.__bases__[0]))
                if cls.isnotmanaged(_renamenodeclass):
                    raise ManagedNodeError("can not delete builtin {}node '{}'".format('abstract ' if cls.isabstract(_renamenodeclass) else '',name))
            else:
                logger.debug("Renaming basenodeclass '{}' to '{}' is equal to creating new node class: ignoring rename".format(rename,name))
                _renamenodeclass = None
                rename = None
        else:
            _renamenodeclass = None
            rename = None
        _body = dict(
            name = name,
            baseClass = baseClass.__name__
        )
        if inputs is not None:
            _body['inputs'] = inputs if isinstance(inputs,list) else list(inputs)
        if outputs is not None:
            _body['outputs'] = outputs if isinstance(outputs,list) else list(outputs)
        for _methodname,_methodstring in (
            (_method,_string)
            for _method,_string in (
                (_meth,nodemethods.get(_meth))
                for _meth in _node_methods
            )
            if _string is not None
        ):
            _body[_methodname] = _methodstring
        _result = cls.loadManaged(name,(baseClass,),_body)
        if _renamenodeclass is not None:
            if _renamenodeclass.__edit_of__ is not None:
                _result.__edit_of__ = _renamenodeclass.__edit_of__
                if _renamenodeclass.__name__ not in [_result.__name__,_result.__edit_of__.__name__]:
                    _nodeclasses.pop(_renamenodeclass.__name__)
            else:
                _result.__edit_of__ = _renamenodeclass
        elif _nodeclass is not None:
            if _nodeclass.__edit_of__ is not None:
                _result.__edit_of__ = _nodeclass.__edit_of__
            else:
                _result.__edit_of__ = _nodeclass
        else:
            _result.__edit_of__ = baseClass    
        if nosafe or _customNodesSavePath is None:
            return _result

        #from PyQt5.QtCore import pyqtRemoveInputHook
        #import pdb
        #pyqtRemoveInputHook()
        #pdb.set_trace()

        if _result.__edit_of__ is not None:
            rename = _result.__edit_of__.__name__
            if rename != _result.__name__ and _result.__edit_of__ != _result.__bases__[0] and cls.ismanaged(_result.__edit_of__):
                _nodeclasses.pop(rename)
            _result.__edit_of__ = None
        else:
            rename = None
        _inputs = _body.get('inputs',None)
        if _inputs is not None:
            for _inp in _inputs:
                _inp['varType'] = _inp['varType'].__name__
            _body['inputs'] = list(_inputs)
        _outputs = _body.get('outputs',None)
        if _outputs is not None:
            for _out in _outputs:
                _out['varType'] = _out['varType'].__name__
            _body['outputs'] = list(_outputs)
        with open(_customNodesSavePath,'r') as _cnfread,open(_customNodesSavePath,'r+' if os.path.isfile(_customNodesSavePath) else 'w+') as _cnfwrite:
            _loaded = 0
            if _cnfread.seekable():
                _seek = _cnfwrite.seek
                _tell = _cnfread.tell
            else:
                def _fake_seek_tell():
                    _lastread = 0
                    _lastseeked = 0
                    def _dotell():
                        nonlocal _lastread
                        _lastread += len(_nextline) if _nextline is not None else 0
                        return _lastread
                    def _doseek(to,whence=0):
                        _ammount = to - _lastseeked 
                        if _ammount < 1:
                          return
                        _cnfwrite.read(_ammount)
                    return _dotell,_doseek
                _tell,_seek = _fake_seek_tell()
            _namepos = -1
            _linecount = 0
            _nextline = None
            while True:
                _typepos = _tell()
                _nextline = _cnfread.readline()
                if _nextline == '':
                    break
                _linecount += 1
                _storedname,_text = (_nextline.split(':::',maxsplit = 1) + [None])[:2]
                if _text is None:
                    # TODO log or throw exception about badly formated managed node description
                    #      or check for comment if allowed
                    logger.error("File '{}'({}): Malformed node description encoutered. Ignored ".format(_customNodesSavePath,_linecount))
                    continue
                if _storedname == name:
                    if rename is not None:
                        _tail = _cnfread.readlines()
                        _seek(_typepos,0)
                        _lineindex = 0
                        for _lineindex,_renameline in enumerate(_tail):
                            _renameline = ( _renameline.split(':::',maxsplit = 1) + [None] )[:2]
                            if _renameline[0] == rename:
                                if _renameline[1] is not None:
                                    break
                                # TODO log or throw exception about badly formated managed node description
                                #      or check for comment if allowed
                                logger.error("File '{}'({}): Malformed node description encoutered. Ignored ".format(_customNodesSavePath,_linecount + _lineindex))
                            _cnfwrite.write(_renameline)
                        _tail = ''.join(_tail[_lineindex+1:])
                    else:
                        _tail = _cnfread.read(size=-1)
                        _seek(_typepos,0)
                    _cnfwrite.write('{}:::{}\n'.format(name,json.dumps(_body)))
                    _cnfwrite.write(_tail)
                    break
                if _storedname != rename:
                    continue
                _seek(_typepos,0)
                _tail = _cnfread.readlines()
                _cnfwrite.write('{}:::{}\n'.format(name,json.dumps(_body)))
                _lineindex = 0
                for _lineindex,_renameline in enumerate(_tail):
                    _renameline = ( _renameline.split(':::',maxsplit = 1) + [None] )[:2]
                    if _renameline[0] == name:
                        if _renameline[1] is not None:
                            break
                        logger.error("File '{}'({}): Malformed node description encoutered. Ignored ".format(_customNodesSavePath,_linecount + _lineindex))
                        # TODO log or throw exception about badly formated managed node description
                        #      or check for comment if allowed
                    _cnfwrite.write(_renameline)
                _cnfwrite.write(''.join(_tail[_lineindex+1:]))
            if _nextline == '':
                _cnfwrite.write('{}:::{}\n'.format(name,json.dumps(_body)))
        return _result

    @classmethod
    def revertUnsavedManaged(cls,nodecls):

        assert(nodecls in _nodeclasses, "Node class '{}' unknown".format(nodecls.__name__))
        if cls.issaved(nodecls):
            return nodecls
        _revertto = nodecls.__edit_of__
        if _revertto is None:
            if nodecls in _nodeclasses and cls.ismanaged(nodecls):
                _nodeclasses.pop(nodecls.__name__)
            return None
        if cls.ismanaged(_revertto):
            _nodeclasses[_revertto.__name__] = _revertto
        if nodecls.__name__ != _revertto.__name__:
            _nodeclasses.pop(nodecls.__name__)
        nodecls.__edit_of__ = None
        return _revertto
        

    @classmethod
    def loadManagedNodes(cls):

        #from PyQt5.QtCore import pyqtRemoveInputHook
        #import pdb
        #pyqtRemoveInputHook()
        #pdb.set_trace()

        if _customNodesSavePath is None:
            return 
        with open(_customNodesSavePath,"r") as _cnfread:
            _linecount = 0
            for _nodename,_nodedict in (
                (_name,json.loads(_description) if _description is not None else None)
                for _name,_description in (
                    ( _line.split(':::',maxsplit=1) + [None] )[:2]
                    for _line in _cnfread
                )
            ):
                _linecount += 1
                if _nodedict is None:
                    # TODO log or throw exception about badly formated managed node description
                    #      or check for comment if allowed
                    logger.error("File '{}'({}): Malformed node description encoutered: No node description ".format(_customNodesSavePath,_linecount))
                    continue
                if 'name' not in _nodedict:
                    logger.error("File '{}'({}): Malformed node description encoutered: 'name' key is mandatory".format(_customNodesSavePath,_linecount))
                    # TODO log or throw exception about badly formated managed node description
                    #      or check for comment if allowed
                    continue
                if _nodename != _nodedict['name']:
                    logger.error("File '{}'({}): Malformed node description encoutered: Nodename '{}' and value ('{}') of 'name' key differ".format(_customNodesSavePath,_linecount,_nodename,_nodedict.get('name','<undefined>')))
                    # TODO log or throw exception about badly formated managed node description
                    #      or check for comment if allowed
                    continue
                _basename = _nodedict.get('baseClass',None)
                if _basename is None:
                    logger.error("File '{}'({}): Malformed node description encoutered: 'baseClass' key is mandatory".format(_customNodesSavePath,_linecount))
                    # TODO log or throw exception about badly formated managed node description
                    #      or check for comment if allowed
                    continue
                _baseclass = _nodeclasses.get(_basename,None)
                if _baseclass is None:
                    logger.error("File '{}'({}): Malformed node description encoutered (Baseclass '{}' invalid) ".format(_customNodesSavePath,_linecount,_basename))
                cls.loadManaged(_nodename,(_baseclass,),_nodedict)
                

    @classmethod
    def loadManaged(cls,name,bases,body):
        _classdict = cls.__prepare__(name,bases)
        _addinput = _classdict['Input']
        for _inp in body.get('inputs',tuple()):
            _inp["varType"] = FLOPPYTYPEMAP.get(_inp["varType"],_inp["varType"])
            _addinput(**_inp)
        _addoutput = _classdict['Output']
        for _out in body.get('outputs',tuple()):
            _out["varType"] = FLOPPYTYPEMAP.get(_out["varType"],_out["varType"])
            _addoutput(**_out)
        _errors = {}
        _createdmethods = {}
        for _method,_methodbody in (
            (
                _meth,
                body[_meth]
            )
            for _meth in _node_methods
            if _meth in body
        ):

            #from PyQt5.QtCore import pyqtRemoveInputHook
            #import pdb
            #pyqtRemoveInputHook()
            #pdb.set_trace()

            _isdefault = cls._ignore_super_passon.match(_methodbody)
            
            if (
                _isdefault is not None and
                _isdefault.group('subclass') in (cls.__name__,None) and
                _isdefault.group('baseclass') in (cls.__bases__[0].__name__,None) and
                _isdefault.group('method') == _method and
                _isdefault.group('superself') in ('self',None)
            ):
                continue
            _context= {}
            try:
                exec("""
def {} (self):\n
    {}
""".format(
                        _method,
                        "\n    ".join(
                        _methodbody.split('\n')
                        )
                    ),
                    _context
                )
                _createdmethods[_method] = _context[_method]
                _classdict["__{}_source__".format(_method)] = _methodbody
            except:
                _errors[_method] = traceback.format_exc()
        if len(_errors) > 0:
            raise NodeUpdateError("Failed to initialize '{}' method".format("' and '".join(_errors.keys())),**_errors)

        
        # MetaMode allways increments counter for non abstract classes
        # remember its current value to restore it after node was marked 
        # managed
        _resetcounts = _STATIC_NODE_COUNTS[1]
        result = MetaNode(name,bases,_classdict)
        for _name,_method in _createdmethods.items():
            result.__dict__[_name] = _method.__get__(None,result)
        if cls.isnotmanaged(result.__bases__[0]):
            result._addInput = ft.partial(_managed_addInput,result)
            result._addOutput = ft.partial(_managed_addOutput,result)
            result._removeInput = ft.partial(_managed_removeInput,result)
            result._removeOutput = ft.partial(_managed_removeOutput,result)
        result.__managed__ = True
        _STATIC_NODE_COUNTS[1] = _resetcounts
        return result


class NodeListProxyType(object):
    __show__ = MetaNode.isnotabstract
    __which__ = 0
    __slots__ = ("__dict__",)

    def __init__(self,dictionary):
        assert isinstance(dictionary,dict)
        self.__dict__ = dictionary

    def __contains__(self,classname):
        try:
            return self.__show__(self.__dict__[classname])
        except KeyError:
            return False

    def __getitem__(self,classname):
        try:
            _cls = self.__dict__[classname] 
        except KeyError as notfound:
            #print(self.__dict__)
            raise KeyError("'{}' node type unknown or abstract".format(classname)) from notfound
        if self.__show__(_cls):
            return _cls
        #print(self.__show__(_cls),'\n',_cls,_cls.__abstract__,_cls.__managed__,'\n',self.__show__)
        raise KeyError("'{}' node type unknown or abstract".format(classname)) from notfound

    def __iter__(self):
        yield from ( 
            _clsname
            for _clsname,_cls in self.__dict__.items()
            if self.__show__(_cls) 
        )

    def __len__(self):
        return len(self.__dict__) - _STATIC_NODE_COUNTS[self.__which__]

    def __repr__(self):
        return "<{}: {}>".format(self.__class__.__name__,self.__str__())

    def __str__(self):
        return str({
            _clsname:_cls
            for _clsname,_cls in self._get_iterator('items')
        })

    def __eq__(self,other):
        if not isinstance(other,NodeListProxyType):
            return False
        return self.__dict__ == other.__dict__

    def __ne__(self,other):
        if not isinstance(other,NodeListProxyType):
            return True
        return self.__dict__ != other.__dict__

    def __hash__(self):
        return hash(self.__dict__)

    

    def copy(self):
        return {
            _key : _value 
            for _key,_value in self.__dict__.items()
            if self.__show__(_value)
        }

    def get(self,key,default = None):
        try:
            _cls = self.__dict__[key] 
        except KeyError:
            return default
        return _cls if self.__show__(_cls) else default

    def _get_iterator(self,kind):
        if kind == 'keys' :
            return (
                _clsname
                for _clsname,_cls in self.__dict__.items()
                if self.__show__(_cls)
            )
        if kind == 'values':
            return (
                _cls
                for _cls in self.__dict__.values()
                if self.__show__(_cls)
            )
        return (
            (_clsname,_cls)
            for _clsname,_cls in self.__dict__.items()
            if self.__show__(_cls)
        )

    class _ProxyView(object):
        def __init__(self,proxy,kind):
            self.__proxy = proxy
            self.__kind = kind

        def __len__(self):
            return len(self.__proxy)

        def __iter__(self):
            yield from self.__proxy._get_iterator(self.__kind)  

        def __contains__(self,value):
            if self.__kind == 'keys':
                return value in self.__proxy
            if self.__kind == 'items':
                return value[0] in self.__proxy
            try:
                return value.__name__ in self.__proxy 
            except AttributeError:
                return False

    def values(self):
        return self.__class__._ProxyView(self,'values')

    def keys(self):
        return self.__class__._ProxyView(self,'keys')

    def items(self):
        return self.__class__._ProxyView(self,'items')

class ManagedNodeListProxyType(NodeListProxyType):
    __show__ = MetaNode.ismanaged
    __which__ = 1


def _defineSetNodesPathsFunction():

    _requirednodes = len(_nodeclasses)

    import sys

    # TODO move to epdb.py and combine with the intended enhancements of set_trace from
    # other projects
    # full python post mortem debugger interception in case python was started with
    # pyton[3] -mpdb <main>.py
    # this ensures that _nodeclasses dict is reset again to the required nodes defined
    # above and thus _setNodesPath defined below will not complain about already established
    # node list remove or reduce as soon as pdb offers the possibility to register
    # startup/cleanup hooks natively.
    if 'pdb' in sys.modules:
        _pdb = sys.modules['pdb']

        import inspect as _inspect

        _activepdb = None
        for _activepdb in (
            _info.frame.f_locals['self']
            for _info in _inspect.stack()                
            if 'self' in _info.frame.f_locals and isinstance(_info.frame.f_locals['self'],sys.modules['pdb'].Pdb)
        ):

            if "__cleanuphooks__" not in _activepdb.__class__.__dict__:
                setattr(_activepdb.__class__,'__cleanuphooks__',list())
                def _add_cleanup_hook(cls,hook):
                    if hook not in cls.__cleanuphooks__:
                        cls.__cleanuphooks__.append(hook)
                setattr(_activepdb.__class__,'add_cleanup_hook',_add_cleanup_hook)
                def _remove_cleanup_hook(cls,hook):
                    try:
                        cls.__cleanuphooks__.pop(cls.__cleanuphooks__.index(hook))
                    except ValueError:
                        pass
                setattr(_activepdb.__class__,'remove_cleanup_hook',_remove_cleanup_hook)
            if "__runscript__" not in _activepdb.__class__.__dict__:
                setattr(_activepdb.__class__,'__runscript__',_activepdb.__class__.__dict__.get('_runscript'))
                def _run_script(self,runname):
                    for _hook in self.__cleanuphooks__: _hook()
                    self.__runscript__(runname)
                setattr(_activepdb.__class__,'_runscript',_run_script)
            if "__runmodule__" not in _activepdb.__class__.__dict__:
                setattr(_activepdb.__class__,'__runmodule__',_activepdb.__class__.__dict__.get('_runmodule'))
                def _run_module(self,runname):
                    for _hook in self.__cleanuphooks__: _hook()
                    self.__runmodule__(runname)
                setattr(_activepdb.__class__,'_runmodule',_run_module)
            def _reset_nodelist():
                _required = [None] * _requirednodes
                for _index,_item in enumerate(_nodeclasses.items()):
                    if _index >= _requirednodes:
                        break
                    _required[_index] = _item
                _nodeclasses.clear()
                _nodeclasses.update(_required)
            _activepdb.add_cleanup_hook(_reset_nodelist)
            if 'PyQt5' in sys.modules:
                _lasthook = sys.excepthook
                def _catch_background_exception(et,ev,eb):
                    import traceback
                    print("except hook touched")

                    traceback.print_exception(et,ev,eb)
                    if issubclass(et,sys.modules['pdb'].Restart) or issubclass(et,SystemExit) or issubclass(et,SyntaxError):
                        if _lasthook is not None:
                            _lasthook(et,ev,eb)
                            return
                        raise ev.with_traceback(eb)


                    traceback
                    _activepdb.interaction(None,ev)
                sys.excepthook = _catch_background_exception
                    
                

    def _setNodesPath(nodespath = None,savepath = None,loadstd = True,loadcustom = True):
        if len(_nodeclasses) > _requirednodes:
            raise LoadNodesError("List of nodes already established")
        
        _floppypath = os.path.abspath(os.path.dirname(__file__))
        if isinstance(nodespath,str):
            if not os.path.isdir(nodespath):
                if len(nodespath) > 1:
                    raise LoadNodesError("Node path '{}' not found".format(nodespath))
            else:
                nodespath = (os.path.abspath(nodespath),)
            _cwdpath = os.path.abspath(os.getcwd())
        elif nodespath is None or ( type(nodespath) in [list,tuple] and len(nodespath) < 1 ):
            nodespath = ('<:floppy:>',)
            _cwdpath = _floppypath
    
        import sys
    
        _mainfile = getattr(sys.modules['__main__'],'__file__',None)
        _mainpath = os.path.abspath(os.path.dirname(_mainfile))
        if loadcustom:
            if savepath is None:
                _savepath = os.path.join(_cwdpath,'CustomNodes')
            else:
                _savepath = os.path.abspath(savepath)
            if not os.path.isdir(_savepath):
                try:
                    os.makedirs(savepath)
                    _savepath = os.path.join(_savepath,'managedNodes.dat')
                except OSError as patherror:
                    if savepath is not None or _cwdpath == _floppypath:
                        raise SaveNodesError("Failed to initialize managed nodes save path '{}'".format(savepath)) from patherror
                    _savepath = None
            else:
                _savepath = os.path.join(_savepath,'managedNodes.dat')
            if _savepath is not None:
                try:
                    open(_savepath,'r+').close()
                    savepath = _savepath
                except FileNotFoundError:
                    try:
                        open(_savepath,'w+').close()
                        savepath = _savepath
                    except PermissionError as permissionerror:
                        if savepath is not None or _cwdpath == _floppypath:
                            raise SaveNodesError("Failed to initialize managed nodes save path '{}'".format(savepath)) from permissionerror
                except PermissionError as permissionerror:
                    if savepath is not None or _cwdpath == _floppypath:
                        raise SaveNodesError("Failed to initialize managed nodes save path '{}'".format(savepath)) from permissionerror
                if loadstd:
                    _loadlist = ('Nodes','CustomNodes')
                else:
                    _loadlist = ('CustomNodes',)
        elif loadstd:
            _loadlist = ('Nodes',)
        else:
            _loadlist = tuple()
        _autopathes = {
            '<:cwd:>': (os.path.join(os.path.abspath(_cwdpath),'CustomNodes') ,) if loadcustom and _cwdpath not in (_mainpath,_floppypath) else tuple(),
            '<:main:>': tuple(( _path for _path in ( os.path.join(_mainpath,_p) for _p in _loadlist ) if os.path.isdir(_path))) if len(_loadlist) > 0 and _mainpath != _floppypath else tuple(),
            '<:floppy:>': tuple(( _path for _path in ( os.path.join(_floppypath,_p) for _p in _loadlist ) if os.path.isdir(_path))) if len(_loadlist) > 0 else tuple()
        }
        
        _loadedpath = []
        for _nextload,_basepath in (
            (_nodepath,_origpath)
            for _path,_origpath in (
                (_autopathes.get(_p,(_p,)),_p if loadcustom and savepath is None else None)
                for _p in nodespath 
                if type(_p) == str and len(_p) > 0
            )
            for _nodepath in _path
            if len(_path) > 0 and ( os.path.isdir(_path[0]) or _origpath == '<:cwd:>')
        ):
            if _basepath is not None and _basepath not in ['<:main:>','<:floppy:>']:
                _savepath = os.path.join(_nextload,'managedNodes.dat')
                try:
                    open(_savepath,'r+').close()
                    savepath = _savepath
                except FileNotFoundError:
                    try:
                        open(_savepath,'w+').close()
                        savepath = _savepath
                    except PermissionError as permissionerror:
                        pass
                except PermissionError as permissionerror:
                    pass
            _loaded = 0
            for i, path in enumerate((
                os.path.join(_nextload,_path)
                for _path in os.listdir(_nextload)
                if _path[-3:] in ['.py','.Py','.PY','.pY']
            )):
                try:
                    SourceFileLoader(str(i), path).load_module()
                    _loaded += 1
                except Exception as e:
                    print('Warning: error in custom node:\n{}'.format(str(e)))
            if _loaded > 0:
                _loadedpath.append(_nextload)
        if len(_loadedpath) < 1:
            raise LoadNodesError("Failed to load any nodes from:\n\t'{}'".format("'\n\t'".join(nodespath)))

        global _customNodesSavePath

        _customNodesSavePath = savepath
        MetaNode.loadManagedNodes()
        return _loadedpath

    return _setNodesPath


_NODECLASSES = MappingProxyType(_nodeclasses)
NODECLASSES = NodeListProxyType(_nodeclasses)
createNode = ft.partial(MetaNode.makeManaged,nosafe = True)
        

isabstract = MetaNode.isabstract

ismanaged = MetaNode.ismanaged

isnotmanaged = MetaNode.isnotmanaged

isnotabstract = MetaNode.isnotabstract

MANAGEDNODECLASSES = ManagedNodeListProxyType(_nodeclasses)

def Input(*args, **kwargs):
    pass


def Output(*args, **kwargs):
    pass


def Tag(*args, **kwargs):
    pass


@abstractNode
class Node(object, metaclass=MetaNode):
    """
    Base class for Nodes.

    To add Inputs to a custom Node class call 'Input(name, varType, hints, list)' in the class's
    body e.g.:

        class MyNode(Node):
            Input('myStringInput', str, list=True)

    To access the value of an input during the Node's 'run' method or 'check' method use
    'myNodeInstance.i_myStringInput'. An 'InputNotAvailable' Exception is raised is the input is not set yet.
    """
    Input('TRIGGER', object, optional=True)
    Tag('Node')

    @classmethod
    def toDict(cls):

        #from PyQt5.QtCore import pyqtRemoveInputHook,pyqtRestoreInputHook
        #pyqtRemoveInputHook()
        #import pdb
        #pdb.set_trace()

        _nodeclassdict = dict(
            name = cls.__name__,
            baseClass = cls.__bases__[0]
        )
        if len(cls.__classinputs__) > 0:
            _nodeclassdict["inputs"] = [ _inp.toDict() for _inp in cls.__classinputs__.values() ]
        if len(cls.__outputs__) > 0:
            _nodeclassdict["outputs"] = [ _out.toDict() for _out in cls.__classoutputs__.values() ]
        for _method,_source in (
            (_methname,_methsrc)
            for _methname,_methsrc in (
                (_meth,cls.__dict__.get('__{}_source__'.format(_meth),None))
                for _meth in _node_methods
            )
            if _methsrc is not None
        ):
            _nodeclassdict[_method] = _source
        return _nodeclassdict

    def __init__(self, nodeID, graph):
        self.waitForAllControlls = False
        self.inputLock = Lock()
        self.runLock = Lock()
        self.loopLevel = 0
        self.__pos__ = (0, 0)
        self.graph = graph
        self.locked = False
        self.subgraph = 'main'
        self.ID = nodeID
        self.buffered = False
        self.inputs = OrderedDict()
        self.outputs = OrderedDict()
        self.outputBuffer = {}
        self.inputPins = OrderedDict()
        self.outputPins = OrderedDict()
        
        
        for i, inp in enumerate(self.__inputs__.values()):
            inp = copy(inp)
            inp.setOwner(self)
            inpID = '{}:I{}'.format(self.ID, inp.name)
            newPin = inp.__pintype__(inpID, inp, self)
            self.inputPins[inp.name] = newPin
            self.inputs[inp.name] = inp

        for i, out in enumerate(self.__outputs__.values()):
            out = copy(out)
            out.setOwner(self)
            outID = '{}:O{}'.format(self.ID, out.name)
            newPin = out.__pintype__(outID, out, self)
            self.outputPins[out.name] = newPin
            self.outputs[out.name] = out
            self.outputBuffer[out.name] = None
        if not self.inputs.keys():
            raise AttributeError('Nodes without any input are not valid.')
        if len(self.inputs.keys()) == 2:
            self.inputs[list(self.inputs.keys())[1]].setPure()
        self.setup()

    def setup(self):
        """
        This method will be called after a node instance is initialized.
        Override this to initialize attributes required for custom node behavior.
        This way the annoying calls of super(Node, self).__init__(*args, **kwargs) calls can be avoided.
        :return:
        """
        pass

    def _return(self, value=0, priority=0):
        self.graph.setReturnValue(value, priority, str(self))

    def __str__(self):
        return '{}-{}'.format(self.__class__.__name__, self.ID)

    def __hash__(self):
        return hash(str(self))

    def lock(self):
        self.locked = True

    def unlock(self):
        self.locked = False
        self.graph.runningNodes.remove(self.ID)

    def iterOutputs(self):
        for out in self.outputPins.values():
            yield out

    def iterInputs(self):
        for inp in self.inputPins.values():
            yield inp

    def run(self) -> None:
        """
        Execute the node. Override this to implement logic.
        :rtype: None
        """
        print('Executing node {}'.format(self))
        # print('===============\nExecuting node {}'.format(self))
        # print('{} is loopLevel ='.format(str(self)), self.loopLevel,'\n================')

    def notify(self):
        """
        Manage the node's state after execution and set input values of subsequent nodes.
        :return: None
        :rtype: None
        """
        for con in self.graph.getConnectionsFrom(self):
            self.buffered = False
            _output = self.outputs[con['outputName']]
            if _output.valueSet:
                con['inputNode'].setInput(con['inputName'], _output.value, override=True, loopLevel=self.loopLevel)
            else:
                con['inputNode'].setInput(con['inputName'], _output.default, override=True, loopLevel=self.loopLevel)
        if not self.graph.getConnectionsFrom(self):
            self.buffered = True
            for out in self.outputs.values():
                self.outputBuffer[out.name] = out.value
        for _inp in self.input.values(): Info.reset(_inp, self.loopLevel)
        # print(self, [inp.name for inp in self.inputs.values()])

    def setInput(self, inputName, value, override=False, loopLevel=False):
        """
        Sets the value of an input.
        :param inputName: str representing the name of the input.
        :param value: object of the appropriate type for that input.
        :param override: boolean specifying whether the input should be overridden if it was set already.
        :param looped: boolean. Set to True if the input is set by a looped node. If True, the node becomes a looped
        node itself. Defaults to False.
        :return: None
        """
        with self.inputLock:
            self.loopLevel = max([self.loopLevel, loopLevel])
            self.inputs[inputName].set(value, override=override, loopLevel=loopLevel)
        # print('%%%%%%%%%%%%%%%%', str(self), inputName, value)

    def check(self) -> bool:
        """
        Checks whether all prerequisites for executing the node instance are met.
        Override this to implement custom behavior.
        By default the methods returns True if all inputs have been set. False otherwise.
        :return: Boolean; True if ready, False if not ready.
        :rtype: bool
        """
        # print(self)
        if self.locked:
            return False
        if self.buffered and self.outputs.keys():
            # print('Node {} has buffered output. Trying to notify outgoing connections.'.format(self))
            return self.notify()
        return any ((
            _inp
            for _inp in self.inputs.values()
            if not _inp.isAvailable() and ( not _inp.optional or _inp.connected )
        ))
        #for inp in (
        #    _inp
        #    for _inp in self.inputs.values()
        #    if not _inp.isAvailable() and ( not _inp.optional or _inp.connected )
        #):
        #    # print('        {}: Prerequisites not met.'.format(str(self)))
        #    return False
        ## print('        {}: ready.'.format(str(self)))
        #return True

    def report(self):
        """
        Creates and returns a dictionary encoding the current state of the Node instance.
        Override this method to implement custom reporting behavior. Check the ReportWidget documentation for details
        on how to implement custom templates.

        The 'keep' key can be used to cache data by the editor. The value assigned to 'keep' must be another key of
        the report dictionary or 'CLEAR'. If it is a key, the value assigned to that key will be cached. If it is
        'CLEAR' the editors cache will be purged. This can be useful for plotting an ongoing stream of data points
        in the editor.

        The 'ready' item is set to True when all inputs are available. This is mainly useful for debugging graph
        applications.
        """
        ready = all([inp.isAvailable(info=True) for inp in self.inputs.values()])
        return {'template': 'DefaultTemplate',
            'class': self.__class__.__name__,
            'ID': self.ID,
            'inputs': [
                (i, v.varType.__name__, _valstr if len(_valstr) < 10 else _valstr[:10]+'...')
                for i, v,_valstr in (
                    (_i, _v, str(_v.r_value))
                    for _i, _v in  self.inputs.items()
                )
            ],
            'outputs': [
                (i, v.varType.__name__, _valstr if len(_valstr) < 10 else _valstr[:10]+'...')
                for i, v,_valstr in (
                    (_i,_v,str(_v.value))
                    for _i,_v in self.outputs.items()
                )
            ],
            'keep': None,
            'ready': 'Ready' if ready else 'Waiting'
        }


    @classmethod
    def classReport(cls):
        return {'template': 'ClassTemplate',
            'class': cls.__name__,
            'ID': '',
            'inputs': [
                (i, v.varType.__name__, _valstr if len(_valstr) < 10 else _valstr[:10] + '...')
                for i, v, _valstr in (
                    (_i, _v, str(_v.r_value))
                    for _i, _v in  cls.__inputs__.items()
                )
            ],
            'outputs': [
                (i, v.varType.__name__, _valstr if len(_valstr) < 10 else _valstr[:10] + '...')
                for i, v, _valstr in (
                    ( _i, _v, str(_v.value))
                    for _i, _v in cls.__outputs__.items()
                )
            ],
            'keep': None,
            'ready': 'Waiting',
            'doc': cls.__doc__
        }

    # def prepare(self):
    #     """
    #     Method for preparing a node for execution.
    #     This method is called on each node before the main execution loop of the owning graph instance is started.
    #     The methods makes sure that artifacts from previous execution are reset to their original states and default
    #     values of inputs that are connected to other nodes' outputs are removed.
    #     :return:
    #     """
    #     return
    #     [InputInfo.reset(inp) for inp in self.inputs.values()]

    @classmethod
    def _addInput(cls, *args,**kwargs):
        """
        This should be a classmethod.
        :param cls: iplicitly inserted by pyhton
        :param args:
        :param kwargs:
        :return:
        """
        _inputInfoClass = kwargs.get('iotype',InputInfo)
        assert(issubclass(_inputInfoClass,InputInfo),"iotype must be subclass of InputInfo")
        assert(issubclass(_inputInfoClass.__pintype__,Pin),"'{}.__pintype__' must be subclass of Pin".format(_inputInfoClass.__name__))
        inputInfo = _inputInfoClass(*args,**kwargs)
        cls.__classinputs__[kwargs['name'] if len(args) < 1 else args[0]] = inputInfo
        # register inputInfo as descriptor for input property named i_<inputname>
        setattr(cls,inputInfo.PropertyName,inputInfo)

    @classmethod
    def _addOutput(cls, *args,**kwargs):
        """
        This should be a classmethod.
        :param cls: implicitly inserted by python
        :param args:
        :param kwargs:
        :return:
        """
        _outputInfoClass = kwargs.get('iotype',OutputInfo)
        assert(issubclass(_outputInfoClass,OutputInfo),"iotype must be subclass of OutputInfo")
        assert(issubclass(_outputInfoClass.__pintype__,Pin),"'{}.__pintype__' must be subclass of Pin".format(_outputInfoClass.__name__))
        outputInfo = _outputInfoClass(*args,**kwargs)
        cls.__classoutputs__[kwargs['name'] if len(args) < 1 else args[0]] = outputInfo
        # register outputInfo as descriptor for output property o_<outputname>
        setattr(cls,outputInfo.PropertyName,outputInfo)

    @classmethod
    def _removeInput(cls,name):
        if name not in cls.__classinputs__:
            return
        _removed_inp = cls.__classinputs__.pop(name,None)
        delattr(cls,_removed_inp.PropertyName)
        

    @classmethod
    def _removeOutput(cls,name):
        if name not in cls.__classoutputs__:
            return
        _removed_out = cls.__classoutputs__.pop(name,None)
        delattr(cls,_removed_out.PropertyName)

    @classmethod
    def _addTag(cls, tag='Node'):
        """
        Adds a Tag to a Node class object.
        :param tag:
        :return:
        """
        cls.__tags__.append(tag)

    def __getattr__(self, item):
        """
        Catches self._<Input/Ouptput> accesses and calls the appropriate methods.
        :param item: str; Attribute name.
        :return: object; Attribute
        :rtype: object
        """
        #if item[:2] == 'i_':
        #    try:
        #        return self.inputs[item[2:]]
        #    except KeyError:
        #        raise AttributeError('No input with name {} defined.'.format(item[2:]))
        #if item[:2] == 'o_':
        #    try:
        #        return self.outputs[item[2:]]
        #    except KeyError:
        #        raise AttributeError('No output with name {} defined.'.format(item[2:]))
        if item[:1] == '_':
            if item[1:2] == '_':
                # this is possible as any attribute or member marked as privated with leading
                # '__' is renamed by the python inpterpreter to _<classname>_<item>[2:]
                raise AttributeError('No output with name {} defined.'.format(item[2:]))
            _msg = "accessing I/O via protedted attribute '{}' is deprecated use category prefixes 'i_', 'o_' instead of unspecific '_' prefix".format(item)
            if item[1:] in self.inputs:
                warnings.filterwarnings('module',_msg,DeprecationWarning)
                warnings.warn(_msg,DeprecationWarning,stacklevel=2)
                return self.inputs[item[1:]].value
            if item[1:] in self.outputs:
                warnings.filterwarnings('module',_msg,DeprecationWarning)
                warnings.warn(_msg,DeprecationWarning,stacklevel=2)
                return self.outputs[item[1:]]
        raise AttributeError("'{}' type object has no attribute '{}'".format(self.__class__,item))

    def getInputPin(self, inputName):
        """
        Returns a reference to the Pin instance associated with the input with the given name.
        :param inputName: str; Name of the input.
        :return: Pin instance
        :rtype: Pin
        """
        return self.inputPins[inputName]

    def getOutputPin(self, outputName):
        return self.outputPins[outputName]

    def getInputInfo(self, inputName):
        return self.inputs[inputName]

    def getOutputInfo(self, outputName):
        return self.outputs[outputName]

    def getInputID(self, inputName):
        return '{}:I{}'.format(self.ID, inputName)

    def getOutputID(self, outputName):
        return '{}:O{}'.format(self.ID, outputName)

    def getInputofType(self, varType):
        for inp in self.inputs.values():
            if issubclass(varType, inp.varType) or issubclass(inp.varType, varType):
                return inp

    def getOutputofType(self, varType):
        for out in self.outputs.values():
            if issubclass(varType, out.varType) or issubclass(out.varType, varType):
                return out

    def save(self):
        """
        Returns a dictionary containing all data necessary to reinstanciate the Node instance with the same properties
        it currently has. A list of the dictionaries of each node instance in a graph is all the data necessary to
        reinstanciate the whole graph.
        :return:
        """
        # print()
        # for key, value in self.inputs.items():
        #     print(key, value.name)
        inputConns = [self.graph.getConnectionOfInput(inp) for inp in self.inputs.values()]
        # print(inputConns)
        inputConns = {inputConn['inputName']: inputConn['outputNode'].getOutputID(inputConn['outputName']) for inputConn in inputConns if inputConn}
        outputConns = {out.name: self.graph.getConnectionsOfOutput(out) for out in self.outputs.values()}
        # print(outputConns)
        for key, conns in outputConns.items():
            conns = [outputConn['inputNode'].getInputID(outputConn['inputName']) for outputConn in conns]
            outputConns[key] = conns
        return {'class': self.__class__.__name__,
                'position': self.__pos__,
                'inputs': [(inputName, inp.varType.__name__, inp(True), inp.default)
                           for inputName, inp in self.inputs.items()],
                'inputConnections': inputConns,
                'outputs': [(outputName, out.varType.__name__, out.value, out.default)
                            for outputName, out in self.outputs.items()],
                'outputConnections': outputConns,
                'subgraph': self.subgraph}

    @classmethod
    def matchHint(cls, text: str):
        return cls.matchInputHint(text) or cls.matchOutputHint(text) or cls.matchClassTag(text)

    @classmethod
    def matchClassTag(cls, text: str):
        return any([tag.lower().startswith(text) for tag in cls.__tags__])

    @classmethod
    def matchInputHint(cls, text: str):
        if text == 'object':
            return True
        if any((any((hint.startswith(text) for hint in inp.hints)) for inp in cls.__inputs__.values())):
            return True

    @classmethod
    def matchOutputHint(cls, text: str):
        if text == 'object':
            return True
        if any((any((hint.startswith(text) for hint in out.hints)) for out in cls.__outputs__.values())):
            return True

############ NOTE: insert any nodes required by floppy below ###########

@abstractNode
class ProxyNode(Node):
    """
    A dummy node without any functionality used as a place holder for subgraphs.
    """

    def __init__(self, *args, **kwargs):
        super(ProxyNode, self).__init__(*args, **kwargs)
        self.__proxies__ = {}
        self.__ready__ = {inp: False for inp in self.inputs.keys()}

    def setInput(self, inputName, value, override=False, loopLevel=False):
        self.loopLevel = max([self.loopLevel, loopLevel])
        proxy = self.__proxies__[inputName]
        proxy.setInput(inputName, value, override, loopLevel)
        self.__ready__[inputName] = True

    def addProxyInput(self, name, output, input, varType):
        pass

    def addProxyOutput(self, name, output, input, varType):
        pass


@abstractNode
class ControlNode(Node):
    """
    Base class for nodes controlling the program flow e.g. If/Else constructs and loops.
    Control nodes have an additional control input and a finalize output.

    The control input is a special input that supports multiple input connections. For example a loop node gets
    notified of a finished iteration over its body by setting the input of the control input. If all iterations are
    completed, the last set input is passed to the finalize output.
    An If/Else construct uses the control input to notify the node that the selected branch terminated. When that
    happens, the value of the control input is set to the finalize output.

    Restricting the option to have multiple connections to ControlNodes only makes sure that the node responsible for
    branches in the execution tree is also the node responsible for putting the pieces back together.
    """
    Input('Start', object)
    Input('Control', object)
    Output('Final', object)

    def __init__(self, *args, **kwargs):
        super(ControlNode, self).__init__(*args, **kwargs)
        self.waiting = False


@abstractNode
class DynamicNode(Node):
    pass

class SubGraph(DynamicNode):
    """
    Node for executing a graph within another graph.
    The node takes the file name of a stored graph as input. It will then load and execute
    the graph once its execution is triggered and will return the sub graph's return
    value to its corresponding output.
    
    The execution of the sub graph is NOT controlled by the graph interpreter. It instead relies on
    a simple loop that will run until all nodes of the sub graph are executed or are un-reachable.
    This means that commands send to the interpreter will not affect the execution of the sub graph.
    From the point of view of the interpreter, the graph is just a node like any other.
    """
    Input('GraphName', str)
    Output('ReturnValue', object)

    def setup(self):
        self.probed = ''
        self.INNERINPUTS = []
        self.innerNames = []

        import floppy.graph

        self.subGraph = floppy.graph.Graph()
        # TODO check if inputs and outpus could be directly mapped into subgraph without copying below
        #      or input and output nodes of subgraph could be made implicit inputs and outputs of this node

    def run(self):
        fileName = self.i_GraphName.value
        self.subGraph.load(fileName)
        for inp in (
            _inp
            for _inp in self.iterInputs()
            if inp.name != 'TRIGGER'
        ):
            self.subGraph.INPUTVALUES[inp.name] = inp.info()
        self.subGraph.selfExecute()
        self.o_ReturnValue = (self.subGraph.returnValue, self.subGraph.returningNode)
        
    def iterInputs(self):
        yield from super(SubGraph, self).iterInputs()
        # for inp in self.INNERINPUTS:
        #     yield inp

    def probeGraph(self):
        """
        Probes the currently selected sub graph for input nodes.
        :return: 
        """
        fileName = self._GraphName
        if self.probed == fileName:
            return
        self.probed = fileName
        self.INNERINPUTS = []
        for name in self.innerNames:
            del self.inputPins[name]
            del self.inputs[name]
            delattr(self,'i_{}'.format(name))
        self.innerNames = []
        if not os.path.isfile(fileName):
            return
        self.subGraph.load(fileName)
        for node in self.subGraph.INPUTNODES:
            for inp in (
                _inp
                for _inp in node.iterInputs()
                if inp.name != 'Trigger'
            ):
                self.INNERINPUTS.append(inp)
                name = inp.info.default
                inpID = '{}:I{}'.format(self.ID, name)
                inp.info.varType = object
                inp.info.name = name
                self.inputPins[name] = Pin(inpID, inp.info, self)
                self.inputs[name] = inp.info
                self.innerNames.append(name)
                setattr(self,'i_{}'.format(name))

        import floppy.graph

        self.subGraph = floppy.graph.Graph()


############ NOTE: insert any nodes required by floppy above ###########
setNodesPath = _defineSetNodesPathsFunction()
