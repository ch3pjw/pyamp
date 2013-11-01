from itertools import islice


class ModuleProxy(object):
    def __init__(self, module=None):
        self.module = module

    def __getattr__(self, name):
        return getattr(self.module, name)


def clamp(value, min_=None, max_=None):
    if min_ is None:
        min_ = min(value, max_)
    if max_ is None:
        max_ = max(value, min_)
    return sorted((value, min_, max_))[1]


def moving_window(iterable, window_size=2):
    '''Generator that moves over an iterable return a window of items each
    iteration. For example,
    >>> for i, j in moving_window([1, 2, 3, 4, 5]):
    ...     print i, j
    1 2
    2 3
    3 4
    4 5

    Code lifted from itertools examples :-)
    '''
    iterator = iter(iterable)
    result = tuple(islice(iterator, window_size))
    if len(result) == window_size:
        yield result
    for element in iterator:
        result = result[1:] + (element,)
        yield result
