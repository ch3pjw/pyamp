import asyncio
import threading


class ModuleProxy(object):
    def __init__(self, module=None):
        self.module = module

    def __getattr__(self, name):
        return getattr(self.module, name)


def clamp(value, min_=None, max_=None):
    if min_ is None and max_ is None:
        return value
    if min_ is None:
        min_ = min(value, max_)
    if max_ is None:
        max_ = max(value, min_)
    return sorted((value, min_, max_))[1]


class LoopingCall:
    def __init__(self, func, *args, loop=None, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.loop = loop or asyncio.get_event_loop()
        self.interval = 0
        self.running = False

    def start(self, interval):
        self.interval = interval
        self.running = True
        self._execute()

    def _execute(self):
        self.func(*self.args, **self.kwargs)
        if self.running:
            self.loop.call_later(self.interval, self._execute)

    def stop(self):
        self.running = False


def threaded_future(blocking_func, *args, **kwargs):
    future = asyncio.Future()
    def call_in_thread():
        try:
            result = blocking_func(*args, **kwargs)
        except Exception as e:
            future.set_exception(e)
        else:
            future.set_result(result)
    thread = threading.Thread(target=call_in_thread)
    @future.add_done_callback
    def join_thread(future):
        thread.join()
    thread.start()
    return future
