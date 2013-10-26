import blessings
import termios
import tty
from contextlib import contextmanager


class Terminal(blessings.Terminal):
    @contextmanager
    def unbuffered_input(self):
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
