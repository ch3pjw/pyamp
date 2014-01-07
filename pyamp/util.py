import asyncio
import threading
from itertools import islice, chain


def clamp(value, min_=None, max_=None):
    if min_ is None and max_ is None:
        return value
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


def parse_gst_tag_list(gst_tag_list):
    '''Takes a GstTagList object and returns a dict containting tag_name-value
    pairs.
    '''
    parsed_tags = {}
    def parse_tag(gst_tag_list, tag_name, parsed_tags):
        safe_tag_name = tag_name.replace('-', '_')
        parsed_tags[safe_tag_name] = gst_tag_list.get_value_index(tag_name, 0)
    gst_tag_list.foreach(parse_tag, parsed_tags)
    return parsed_tags


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


def future_with_result(result):
    future = asyncio.Future()
    future.set_result(result)
    return future


class DictWithUpdateCallback(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_update_callback = None

    def __setitem__(self, name, value):
        super().__setitem__(name, value)
        if self.on_update_callback:
            self.on_update_callback(name, value)

    def update(self, update_dict, **kwargs):
        super().update(update_dict, **kwargs)
        for k, v in chain(update_dict.items(), kwargs.items()):
            self.on_update_callback(k, v)
