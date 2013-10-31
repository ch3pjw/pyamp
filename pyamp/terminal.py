import blessings
import termios
import tty
import signal
import os
import logging
from contextlib import contextmanager


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

    @contextmanager
    def fullscreen(self):
        # Monkey patching this was harder and more verbose than rewriting it,
        # plus, we have to know how to set fullscreen manually anyway, so tha
        # API is fine.
        self.stream.write(self.enter_fullscreen)
        self._is_fullscreen = True
        try:
            yield
        finally:
            self.stream.write(self.exit_fullscreen)
            self._is_fullscreen = False

    @contextmanager
    def hidden_cursor(self):
        # Monkey patching this was also harder and more error prone than
        # re-writing it!
        self.stream.write(self.hide_cursor)
        self._has_hidden_cursor = True
        try:
            yield
        finally:
            self.stream.write(self.normal_cursor)
            self._has_hidden_cursor = False

    def handle_sigtstp(self, sig_num, stack_frame):
        self.log.info('Handling SIGTSTP for suspend...')
        if self.is_a_tty:
            cur_tty_attrs = termios.tcgetattr(self.stream)
            termios.tcsetattr(
                self.stream, termios.TCSADRAIN, self._orig_tty_attrs)
        if self._is_fullscreen:
            self.stream.write(self.exit_fullscreen)
        if self._has_hidden_cursor:
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
            if self._is_fullscreen:
                self.stream.write(self.enter_fullscreen)
            if self._has_hidden_cursor:
                self.stream.write(self.hide_cursor)
        signal.signal(signal.SIGCONT, restore_on_sigcont)
        os.kill(os.getpid(), signal.SIGTSTP)
