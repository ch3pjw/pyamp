from jcn.display_elements import ABCDisplayElement


class TimeCheck(ABCDisplayElement):
    min_height = max_height = 1

    def __init__(self):
        super().__init__()
        self._position = 0
        self._duration = 0

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        self._position = value
        self.updated = True
        if self.root:
            self.root.update()

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, value):
        self._duration = value
        self.updated = True
        if self.root:
            self.root.update()

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

    def _get_lines(self, width, height):
        if width < self.max_width:
            return [self._get_short_string()]
        return [self._get_long_string()]
