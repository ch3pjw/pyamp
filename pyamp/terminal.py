import blessings
import termios
import tty
import signal
import os
import logging
from contextlib import contextmanager
from functools import wraps


def override_sugar(func):
    attr_name = func.__name__
    @property
    @wraps(func)
    def func_which_uses_terminal_sugar(self):
        func(self)
        return self.__getattr__(attr_name)
    return func_which_uses_terminal_sugar


class Terminal(blessings.Terminal):
    def __init__(self, *args, **kwargs):
        self.log = logging.getLogger(self.__class__.__name__)
        super(self.__class__, self).__init__(*args, **kwargs)
        if self.is_a_tty:
            self._orig_tty_attrs = termios.tcgetattr(self.stream)
        else:
            self._orig_tty_attrs = None
        self._is_fullscreen = False
        self._has_hidden_cursor = False
        self._resolved_sugar_cache = {}

    def __getattr__(self, attr):
        # We override ___getattr__ so that we don't do blessings' annoying
        # caching by attribute-setting side-effect! This means we can override
        # sugar without fear!
        try:
            return self._resolved_sugar_cache[attr]
        except KeyError:
            if self._does_styling:
                resolution = self._resolve_formatter(attr)
            else:
                resolution = blessings.NullCallableString()
            self._resolved_sugar_cache[attr] = resolution
            return resolution

    @contextmanager
    def unbuffered_input(self):
        '''Sets cbreak on the current tty so that input from the user isn't
        parcelled up and delivered with each press of return, but delivered on
        each keystroke.
        '''
        if self.is_a_tty:
            orig_tty_attrs = termios.tcgetattr(self.stream)
            tty.setcbreak(self.stream)
            try:
                yield
            finally:
                termios.tcsetattr(
                    self.stream, termios.TCSADRAIN, orig_tty_attrs)
        else:
            yield

    @override_sugar
    def enter_fullscreen(self):
        self._is_fullscreen = True

    @override_sugar
    def exit_fullscreen(self):
        self._is_fullscreen = False

    @override_sugar
    def hide_cursor(self):
        self._has_hidden_cursor = True

    @override_sugar
    def normal_cursor(self):
        self._has_hidden_cursor = False

    def handle_sigtstp(self, sig_num, stack_frame):
        self.log.info('Handling SIGTSTP for suspend...')
        # Store current state:
        if self.is_a_tty:
            cur_tty_attrs = termios.tcgetattr(self.stream)
            termios.tcsetattr(
                self.stream, termios.TCSADRAIN, self._orig_tty_attrs)
        is_fullscreen = self._is_fullscreen
        has_hidden_cursor = self._has_hidden_cursor
        # Restore normal terminal state:
        if is_fullscreen:
            self.stream.write(self.exit_fullscreen)
        if has_hidden_cursor:
            self.stream.write(self.normal_cursor)
        self.stream.flush()
        # Unfortunately, we have to remove our signal handler and
        # reinstantiate it after we're continued, because the only way we
        # can get python to sleep is if we send the signal to ourselves again
        # with no handler :-(
        current_handler = signal.signal(signal.SIGTSTP, signal.SIG_DFL)
        def restore_on_sigcont(sig_num, stack_frame):
            signal.signal(signal.SIGTSTP, current_handler)
            signal.signal(signal.SIGCONT, signal.SIG_DFL)
            if self.is_a_tty:
                termios.tcsetattr(
                    self.stream, termios.TCSADRAIN, cur_tty_attrs)
            if is_fullscreen:
                self.stream.write(self.enter_fullscreen)
            if has_hidden_cursor:
                self.stream.write(self.hide_cursor)
        signal.signal(signal.SIGCONT, restore_on_sigcont)
        os.kill(os.getpid(), signal.SIGTSTP)
