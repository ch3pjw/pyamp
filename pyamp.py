#! /usr/bin/env python
from __future__ import division

import sys
import os
import signal
import time
from contextlib import contextmanager

import blessings
import termios
import tty

import pygst
pygst.require('0.10')
import gst

from twisted.internet import reactor, task, protocol, stdio


class Player(object):
    def __init__(self, reactor=reactor):
        self.reactor = reactor
        self.gst_player = gst.element_factory_make('playbin2', 'player')

        self.progress_bar = ProgressBar()
        self.terminal = Terminal()

        self.key_map = {
            'q': self.quit,
            ' ': self.pause}

    def _handle_messages(self):
        bus = self.gst_player.get_bus()
        while True:
            message = bus.poll(gst.MESSAGE_EOS, timeout=0.01)
            if message:
                self.stop()
            else:
                break

    def get_duration(self):
        '''
        :returns: The total duration of the currently playing track, in
        seconds, or None if the duration could not be retrieved
        '''
        try:
            duration, format_ = self.gst_player.query_duration(
                gst.FORMAT_TIME, None)
        except gst.QueryError:
            return
        return duration / 1e9

    def get_position(self):
        try:
            position, format_ = self.gst_player.query_position(
                gst.FORMAT_TIME, None)
        except gst.QueryError:
            return
        return position / 1e9

    @property
    def state(self):
        '''We define our own getter for state because we don't continually want
        to be doing index lookups or tuple unpacking on the result of the one
        provided by gst-python.
        '''
        success, state, pending = self.gst_player.get_state()
        return state

    @state.setter
    def state(self, state):
        '''We define a 'state' setter for symmetry with the getter.
        '''
        self.gst_player.set_state(state)

    def update(self):
        self._handle_messages()
        if self.state == gst.STATE_PLAYING:
            self.draw()

    def draw(self):
        self.progress_bar.fraction = (
            self.get_position() / self.get_duration())
        prog_bar_width = self.terminal.width - 2
        with self.terminal.location(1, self.terminal.height - 1):
            print self.progress_bar.draw(prog_bar_width),
        sys.stdout.flush()

    def set_file(self, filepath):
        filepath = os.path.abspath(filepath)
        self.gst_player.set_property('uri', 'file://{}'.format(filepath))

    def play(self):
        self.gst_player.set_property('volume', 1)
        self.state = gst.STATE_PLAYING

    def pause(self):
        if self.state == gst.STATE_PLAYING:
            self.state = gst.STATE_PAUSED
        else:
            self.state = gst.STATE_PLAYING

    def stop(self):
        self.gst_player.set_state(gst.STATE_NULL)
        self.reactor.stop()

    def fade_out(self, duration=0.33):
        # FIXME: this shouldn't block!
        steps = 66
        step_time = duration / steps
        for i in range(steps, -1, -1):
            self.gst_player.set_property('volume', i / steps)
            time.sleep(step_time)

    def _handle_sigint(self, signal, frame):
        self.quit()

    def handle_input(self, char):
        action = self.key_map.get(char, lambda: None)
        action()

    def quit(self):
        self.fade_out()
        self.stop()

    def run(self):
        with self.terminal.fullscreen():
            with self.terminal.hidden_cursor():
                with self.terminal.unbuffered_input():
                    signal.signal(signal.SIGINT, self._handle_sigint)
                    self.looping_call = task.LoopingCall(self.update)
                    self.looping_call.start(0.1)
                    stdio.StandardIO(InputReader(self))
                    self.reactor.run()


class ProgressBar(object):
    def __init__(self):
        self.fraction = 0
        self._prog_chars = ['-', '=']

    def draw(self, width):
        width -= 2
        chars = [' '] * width
        filled = self.fraction * width
        over = filled - int(filled)
        filled = int(filled)
        chars[:filled] = self._prog_chars[-1] * filled
        final_char = self._prog_chars[int(over * len(self._prog_chars))]
        chars[filled] = final_char
        return '[{}]'.format(''.join(chars))


class InputReader(protocol.Protocol):
    def __init__(self, player):
        self.player = player

    def dataReceived(self, data):
        for char in data:
            self.player.handle_input(char)


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


if __name__ == '__main__':
    p = Player()
    p.set_file(sys.argv[1])
    p.play()
    p.run()
