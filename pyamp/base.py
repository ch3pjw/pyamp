import logging
from abc import ABCMeta


class PyampBaseMeta(ABCMeta):
    def __init__(cls, name, bases, attrs):
        super(cls.__metaclass__, cls).__init__(name, bases, attrs)
        cls.log = logging.getLogger(cls.__name__)


class PyampBase(object):
    __metaclass__ = PyampBaseMeta
