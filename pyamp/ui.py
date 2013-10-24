from __future__ import division

from abc import ABCMeta, abstractmethod, abstractproperty
from itertools import cycle


def clamp(value, min_=None, max_=None):
    min_ = min_ or min(value, max_)
    max_ = max_ or max(value, min_)
    return sorted((value, min_, max_))[1]


def weighted_round_robin(iterable):
    '''Takes an iterable of tuples of <item>, <weight> and cycles around them,
    returning heavier (integer) weighted items more frequently.
    '''
    cyclable_list = []
    assigned_weight = 0
    still_to_process = [
        (item, weight) for item, weight in
        sorted(iterable, key=lambda tup: tup[1], reverse=True)]
    while still_to_process:
        for i, (item, weight) in enumerate(still_to_process):
            if weight > assigned_weight:
                cyclable_list.append(item)
            else:
                del still_to_process[i]
        assigned_weight += 1
    return cycle(cyclable_list)


class ABCUIElement(object):
    __metaclass__ = ABCMeta

    min_width = abstractproperty()
    max_width = abstractproperty()
    min_height = abstractproperty()
    max_height = abstractproperty()

    @property
    def width_constrained(self):
        return any((self.min_width, self.max_width))

    @property
    def height_constrained(self):
        return any((self.min_height, self.max_height))

    @property
    def fixed_width(self):
        return (
            self.min_width is not None and
            self.max_width is not None and
            self.min_width == self.max_width)

    @abstractmethod
    def draw(self, width, height):
        '''Returns a string that can be output to the console to represent the
        UI element.
        '''


class Fill(ABCUIElement):
    min_width = None
    max_width = None
    min_height = None
    max_height = None

    def __init__(self, char='.'):
        self.char = char

    def draw(self, width, height):
        return '\n'.join([self.char * width] * height)


class ContainerItem(object):
    def __init__(self, element, weight, size=0):
        self.element = element
        self.weight = weight
        self.size = size
        # FIXME: This is a bit of a nasty hack to help draw the container:
        self._round_robin_additions_to_ignore = 0


class HorizontalContainer(ABCUIElement):
    min_height = 1
    max_height = 1

    def __init__(self, elements):
        self._contents = []
        for element in elements:
            self.add_element(element)
        self._prev_width = None
        self._elements_updated = False

    def __iter__(self):
        for item in self._contents:
            yield item.element

    @property
    def min_width(self):
        return (
            sum(e.min_width for e in self if e.min_width is not None) +
            len(self._contents) - 1)

    @property
    def max_width(self):
        if any(e.max_width is None for e in self):
            return
        else:
            return (
                sum(e.max_width for e in self if e.max_width is not None) +
                len(self._contents) - 1)

    def add_element(self, element, weight=1):
        item = ContainerItem(element, weight)
        self._contents.append(item)
        self._elements_updated = True

    def remove_element(self, element):
        for i, item in enumerate(self._contents):
            if item.element is element:
                del self._contents[i]
                break
        self._elements_updated = True

    def _recalculate_element_sizes(self, width):
        '''The basic approach to working out the sizes of our elements is to
        start with each element at its minimum size and then to round-robin
        between the expandable elements in a weighted fashion, expanding them
        until the space is full.
        '''
        allocated_width = len(self._contents) - 1
        for item in self._contents:
            item.size = item.element.min_width or 0
            item._round_robin_additions_to_ignore = item.size
            allocated_width += item.size
        weighted_items = [(item, item.weight) for item in self._contents]
        for item in weighted_round_robin(weighted_items):
            if (item.element.max_width is None or
                    item.size < item.element.max_width):
                if item._round_robin_additions_to_ignore:
                    item._round_robin_additions_to_ignore -= 1
                else:
                    item.size += 1
                    allocated_width += 1
            if allocated_width >= width:
                break
        self._elements_updated = False
        self._prev_width = width

    def draw(self, width, height):
        '''Draws all the elements in this container, recalculating all their
        sizes if necessary.
        '''
        if width != self._prev_width or self._elements_updated:
            self._recalculate_element_sizes(width)
        return ' '.join(i.element.draw(i.size, height) for i in self._contents)


class ProgressBar(ABCUIElement):
    min_width = 3
    max_width = None
    min_height = 1
    max_height = 1

    def __init__(self, prog_chars='-='):
        self.fraction = 0
        self._prog_chars = prog_chars

    def draw(self, width, height):
        width -= 2
        chars = [' '] * width
        filled = self.fraction * width
        over = filled - int(filled)
        filled = int(filled)
        chars[:filled] = self._prog_chars[-1] * filled
        if over:
            final_char = self._prog_chars[int(over * len(self._prog_chars))]
            chars[filled] = final_char
        return u'[{}]'.format(u''.join(chars))


class TimeCheck(ABCUIElement):
    min_height = 1
    max_height = 1

    def __init__(self):
        self.position = 0
        self.duration = 0

    @property
    def min_width(self):
        return len(self._get_short_string())

    @property
    def max_width(self):
        return len(self._get_long_string())

    def _get_short_string(self):
        return '{:.1f}'.format(self.position)

    def _get_long_string(self):
        return '{:.1f}/{:.1f}'.format(self.position, self.duration)

    def draw(self, width, height):
        if width < self.max_width:
            return self._get_short_string()
        return self._get_long_string()
