from unittest import TestCase

from pyamp.keyboard import bindable, is_bindable


class TestBindable(TestCase):
    def test_bindable(self):
        def f():
            return 'hello world'
        f_ = bindable(f)
        self.assertIs(f_, f)
        self.assertTrue(f.bindable)
        self.assertTrue(is_bindable(f))
        @bindable
        def f(a=1):
            pass
        self.assertTrue(is_bindable(f))
        class A(object):
            @bindable
            def f(self, a=1):
                pass
        self.assertTrue(is_bindable(A.f))
        a = A()
        self.assertTrue(is_bindable(a.f))

    def test_not_bindable(self):
        def f():
            return 'gooodbye world'
        self.assertFalse(is_bindable(f))

    def test_unbindable(self):
        def f(a, b=1):
            return 'Noooo!'
        self.assertRaises(ValueError, bindable, f)
