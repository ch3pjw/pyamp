def bindable(func):
    '''Decorator used to label a function as bindable to a key (i.e. that a
    user can call it outright).
    '''
    func.bindable = True
    return func


def is_bindable(func):
    '''Determines if the given function has been decorated as bindable.
    '''
    return getattr(func, 'bindable', False)


class Keyboard(object):
    '''Utility class for turning key escape sequences into human parsable key
    names.
    '''
    def __init__(self):
        self._sequence_to_name = {
            '\x1b': 'esc',
            ' ': 'space',

            '\x1b[A': 'up',
            '\x1b[B': 'down',
            '\x1b[C': 'left',
            '\x1b[D': 'right',
            '\x1b[E': 'keypad5',
            '\x1b[F': 'end',
            '\x1b[G': 'keypad5',
            '\x1b[H': 'home',

            '\x1b[1~': 'home',
            '\x1b[2~': 'insert',
            '\x1b[3~': 'delete',
            '\x1b[4~': 'end',
            '\x1b[5~': 'pageup',
            '\x1b[6~': 'pagedown',
            '\x1b[7~': 'home',
            '\x1b[8~': 'end',

            '\x1b[11~': 'f1', '\x1b[[A': 'f1', '\x1bOP': 'f1',
            '\x1b[12~': 'f2', '\x1b[[B': 'f2', '\x1bOQ': 'f2',
            '\x1b[13~': 'f3', '\x1b[[C': 'f3', '\x1bOR': 'f3',
            '\x1b[14~': 'f4', '\x1b[[D': 'f4', '\x1bOS': 'f4',
            '\x1b[15~': 'f5', '\x1b[[E': 'f5',

            '\t': 'tab',
            '\x1b[Z': 'shift tab',
            '\x7f': 'backspace'}
        self._sequence_to_name.update(self._create_high_f_keys())
        self._sequence_to_name.update(self._create_ctrl_keys())
        self._sequence_to_name.update(self._create_alt_keys())

    def _create_high_f_keys(self):
        # make normal key range:
        high_f_seq_nums = (n for n in xrange(17, 35) if n not in (22, 27, 30))
        f_num_seq_num = enumerate(high_f_seq_nums, start=6)
        high_f_keys = {'\x1d[%d~' % n: 'f%d' % f for f, n in f_num_seq_num}
        return high_f_keys

    def _create_ctrl_keys(self):
        ctrl_keys = {}
        for i in xrange(26):
            name = 'ctrl ' + chr(ord('a') + i - 1)
            sequence = chr(i)
            ctrl_keys[sequence] = name
        return ctrl_keys

    def _create_alt_keys(self):
        alt_keys = {}
        for i in xrange(33, 127):
            name = 'alt ' + chr(i)
            sequence = '\x1b{}'.format(chr(i))
            alt_keys[sequence] = name
        return alt_keys

    def __getitem__(self, sequence):
        if sequence in self._sequence_to_name:
            return self._sequence_to_name[sequence]
        else:
            return sequence
