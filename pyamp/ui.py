from abc import ABCMeta, abstractmethod, abstractproperty


def clamp(value, min_=None, max_=None):
    min_ = min_ or min(value, max_)
    max_ = max_ or max(value, min_)
    return sorted((value, min_, max_))[1]


class ABCUIElement(object):
    __metaclass__ = ABCMeta

    min_width = abstractproperty()
    max_width = abstractproperty()
    min_height = abstractproperty()
    max_height = abstractproperty()

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


class HorizontalContainer(ABCUIElement):
    min_height = 1
    max_height = 1

    def __init__(self, elements):
        self._contents = []
        for element in elements:
            self.add_element(element)

    def __iter__(self):
        for item in self._contents:
            yield item.element

    @property
    def min_width(self):
        return sum(e.min_width for e in self) + len(self._contents) - 1

    @property
    def max_width(self):
        if any(e.max_width is None for e in self):
            return
        else:
            return sum(i.element.max_width for i in self._items_with_max_width)

    @property
    def _items_with_max_width(self):
        for item in self._contents:
            if item.element.max_width is not None:
                yield item

    @property
    def _items_without_max_width(self):
        for item in self._contents:
            if item.element.max_width is None:
                yield item

    def add_element(self, element, weight=1):
        item = ContainerItem(element, weight)
        self._contents.append(item)

    def remove_element(self, element):
        for i, item in enumerate(self._contents):
            if item.element is element:
                del self._contents[i]
                break

    def draw(self, width, height):
        allocated_width = len(self._contents) - 1
        for item in self._items_with_max_width:
            item.size = clamp(
                width,
                item.element.min_width,
                item.element.max_width)
            allocated_width += item.size
        total_weight = sum(i.weight for i in self._items_without_max_width)
        for i in self._items_without_max_width:
            weighted_width = (
                (width - allocated_width) * i.weight / total_weight)
            i.size = weighted_width
        return ' '.join(i.element.draw(i.size, height) for i in self._contents)


class ProgressBar(ABCUIElement):
    min_width = 3
    max_width = None
    min_height = 1
    max_height = 1

    def __init__(self):
        self.fraction = 0
        self._prog_chars = ['-', '=']

    def draw(self, width, height):
        width -= 2
        chars = [' '] * width
        filled = self.fraction * width
        over = filled - int(filled)
        filled = int(filled)
        chars[:filled] = self._prog_chars[-1] * filled
        final_char = self._prog_chars[int(over * len(self._prog_chars))]
        chars[filled] = final_char
        return '[{}]'.format(''.join(chars))


class TimeCheck(ABCUIElement):
    min_height = 1
    max_height = 1

    def __init__(self):
        self.position = 0
        self.duration = 0

    @property
    def width(self):
        return len(self.draw(0, 0))

    @property
    def min_width(self):
        return self.width

    @property
    def max_width(self):
        return self.width

    def draw(self, width, height):
        return '{:.1f}/{:.1f}'.format(self.position, self.duration)
