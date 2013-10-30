from unittest import TestCase

import logging
from abc import abstractmethod

from pyamp.base import PyampBaseMeta


class TestPyampBaseMeta(TestCase):
    def test_logger_added(self):
        class Foo(object):
            __metaclass__ = PyampBaseMeta
        self.assertTrue(hasattr(Foo, 'log'))
        self.assertIsInstance(Foo.log, logging.Logger)
        foo = Foo()
        self.assertTrue(hasattr(foo, 'log'))
        self.assertIs(foo.log, Foo.log)
        self.assertEqual(foo.log.name, Foo.__name__)

    def test_abstract_base_class(self):
        class Bar(object):
            __metaclass__ = PyampBaseMeta

            @abstractmethod
            def f(self):
                pass
        self.assertRaises(TypeError, Bar)
