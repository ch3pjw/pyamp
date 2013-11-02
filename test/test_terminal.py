from unittest import TestCase
from mock import patch
from io import StringIO

import blessings
import signal
import os

from pyamp.terminal import Terminal


class TestTerminal(TestCase):
    def test_overridden_sugar(self):
        pyamp_terminal = Terminal()
        blessings_terminal = blessings.Terminal()
        for attr_name in (
                'enter_fullscreen', 'exit_fullscreen', 'hide_cursor',
                'normal_cursor'):
            # Check that we're actually behaving like a tty:
            self.assertTrue(bool(getattr(blessings_terminal, attr_name)))
            # Check normal retrieval
            self.assertEqual(
                getattr(pyamp_terminal, attr_name),
                getattr(blessings_terminal, attr_name))
            # We check retrieval a second time because we cache:
            self.assertEqual(
                getattr(pyamp_terminal, attr_name),
                getattr(blessings_terminal, attr_name))

    @patch('pyamp.terminal.termios', autospec=True)
    @patch('pyamp.terminal.signal.signal', autospec=True)
    @patch('pyamp.terminal.os.kill', autospec=True)
    def test_handle_sigtstp(self, mock_kill, mock_signal, mock_termios):
        # This is quite a poor unit test, in the sense that it basically
        # checks that the code I've written is the code I've written! Any
        # suggestions on how to test this in a less invasive way are welcome!
        mock_termios.tcgetattr.return_value = 'Wobble'
        mock_signal.return_value = 'current_handler'
        fake_tty = StringIO()
        term = Terminal(stream=fake_tty, force_styling=True)
        term._is_fullscreen = True
        term._has_hidden_cursor = True
        term.is_a_tty = True
        term.handle_sigtstp(None, None)
        mock_termios.tcgetattr.assert_called_once_with(fake_tty)
        self.assertTrue(bool(fake_tty.getvalue()))
        self.assertIn(term.exit_fullscreen, fake_tty.getvalue())
        self.assertIn(term.normal_cursor, fake_tty.getvalue())
        mock_signal.assert_any_call(signal.SIGTSTP, signal.SIG_DFL)
        signal_obj, cont_handler = mock_signal.call_args[0]
        self.assertEqual(signal_obj, signal.SIGCONT)
        mock_kill.assert_called_once_with(os.getpid(), signal.SIGTSTP)

        fake_tty.truncate(0)
        cont_handler(None, None)
        mock_signal.assert_any_call(signal.SIGTSTP, 'current_handler')
        mock_signal.assert_any_call(signal.SIGCONT, signal.SIG_DFL)
        self.assertIn(term.enter_fullscreen, fake_tty.getvalue())
        self.assertIn(term.hide_cursor, fake_tty.getvalue())
        mock_termios.tcsetattr.assert_called_with(
            fake_tty, mock_termios.TCSADRAIN, 'Wobble')

    @patch('pyamp.terminal.termios', autospec=True)
    @patch('pyamp.terminal.tty.setcbreak', autospec=True)
    def test_unbuffered_input(self, mock_setcbreak, mock_termios):
        mock_termios.tcgetattr.return_value = 'Wobble'
        term = Terminal()
        mock_termios.reset_mock()
        context_manager = term.unbuffered_input()
        context_manager.__enter__()
        mock_termios.tcgetattr.assert_called_once_with(term.stream)
        mock_setcbreak.assert_called_once_with(term.stream)
        self.assertEqual(mock_termios.tcsetattr.call_count, 0)
        context_manager.__exit__(None, None, None)  # exc_type, exc_value, tb
        mock_termios.tcsetattr.assert_called_once_with(
            term.stream, mock_termios.TCSADRAIN, 'Wobble')
