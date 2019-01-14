from collections import OrderedDict
from types import MappingProxyType
FLOPPYTYPES = OrderedDict([
    (None.__class__.__name__, None.__class__),
    (str.__name__, str),
    (bool.__name__, bool),
    (int.__name__, int),
    (float.__name__, float),
    (object.__name__, object)
])

FLOPPYTYPEMAP = MappingProxyType(FLOPPYTYPES)


class MetaType(type):
    def __new__(cls, name, bases, classdict):
        result = type.__new__(cls, name, bases, classdict)
        # result.__dict__['Input'] = result._addInput
        FLOPPYTYPES[name] = result
        return result


class Type(object, metaclass=MetaType):
    color = (255, 255, 255)

    @staticmethod
    def debugInfoGetter(obj):
        raise AttributeError


class Atom(Type):
    color = (204, 0, 204)

    @staticmethod
    def checkType(instance):
        return instance

    @staticmethod
    def debugInfoGetter(obj):
        return obj.get_name


class StructureInfo(Type):
    color = (102, 0, 102)

    @staticmethod
    def checkType(instance):
        return instance

    @staticmethod
    def debugInfoGetter(obj):
        return obj.get_name


