from unittest import TestCase

import asyncio
import threading

from pyamp.util import clamp, LoopingCall, threaded_future


class TestUtil(TestCase):
    def test_clamp_values(self):
        self.assertEqual(clamp(1, 2, 3), 2)
        self.assertEqual(clamp(4, 3, 5), 4)
        self.assertEqual(clamp(10, 8, 9), 9)
        self.assertEqual(clamp(-1, 0, 1), 0)
        self.assertEqual(clamp(1, -1, 0), 0)

    def test_clamp_unbounded(self):
        self.assertEqual(clamp(42), 42)
        self.assertEqual(clamp(-42), -42)
        self.assertEqual(clamp(121, min_=13), 121)
        self.assertEqual(clamp(-121, min_=13), 13)
        self.assertEqual(clamp(121, max_=13), 13)
        self.assertEqual(clamp(-121, max_=13), -121)

    def test_looping_call(self):
        result = []
        future = asyncio.Future()
        def loopable(n):
            for i in range(n):
                yield result.append(i)
            looping_call.stop()
            future.set_result('done')
            yield result.append(n)
        func = loopable(3).__next__
        looping_call = LoopingCall(func)
        looping_call.start(0.1)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)
        self.assertEqual(result, [0, 1, 2, 3])

    def test_threaded_future(self):
        result = ['']
        def blocky(*args, **kwargs):
            result[0] = 'Success', threading.current_thread(), args, kwargs
            return 'Paul rocks'
        future = threaded_future(blocky, 'hello', kwarg='world')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(future)
        success, thread, args, kwargs = result[0]
        self.assertEqual(success, 'Success')
        self.assertIsNot(thread, threading.current_thread())
        self.assertEqual(args, ('hello',))
        self.assertEqual(kwargs, {'kwarg': 'world'})
        self.assertEqual(future.result(), 'Paul rocks')

    def test_threaded_future_with_exception(self):
        def faily():
            raise KeyError('This exception is part of the test')
        future = threaded_future(faily)
        loop = asyncio.get_event_loop()
        self.assertRaises(KeyError, loop.run_until_complete, future)
