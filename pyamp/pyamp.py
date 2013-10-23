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

from ui import HorizontalContainer, ProgressBar, TimeCheck


class Player(object):
    def __init__(self):
        self.gst_player = gst.element_factory_make('playbin2', 'player')
        self.tags = {'title': ''}

    def _handle_messages(self):
        bus = self.gst_player.get_bus()
        while True:
            message = bus.poll(gst.MESSAGE_ANY, timeout=0.01)
            if message:
                if message.type == gst.MESSAGE_EOS:
                    self.stop()
                    raise StopIteration('Track finished successfully!')
                if message.type == gst.MESSAGE_TAG:
                    self.tags.update(message.parse_tag())
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
    def playing(self):
        return self.state == gst.STATE_PLAYING

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

    def fade_out(self, duration=0.33):
        # FIXME: this shouldn't block!
        steps = 66
        step_time = duration / steps
        for i in range(steps, -1, -1):
            self.gst_player.set_property('volume', i / steps)
            time.sleep(step_time)


class UI(object):
    def __init__(self, reactor=reactor):
        self.reactor = reactor
        self.player = Player()
        self.progress_bar = ProgressBar()
        self.time_check = TimeCheck()
        self.status_bar = HorizontalContainer(
            (self.progress_bar, self.time_check))
        self.terminal = Terminal()
        self.key_map = {
            'q': self.quit,
            ' ': self.player.pause}

    def update(self):
        try:
            self.player.update()
        except StopIteration:
            self.quit()
        self.draw()

    def draw(self):
        print self.terminal.clear()
        if self.player.playing:
            position = self.player.get_position()
            duration = self.player.get_duration()
            self.progress_bar.fraction = position / duration
            self.time_check.position = position
            self.time_check.duration = duration
        total_width = self.terminal.width - 2
        with self.terminal.location(0, self.terminal.height - 2):
            print self.player.tags['title'].center(self.terminal.width)
            print self.status_bar.draw(total_width, 1).center(
                self.terminal.width),
        sys.stdout.flush()

    def _handle_sigint(self, signal, frame):
        self.quit()

    def handle_input(self, char):
        action = self.key_map.get(char, lambda: None)
        action()

    def quit(self):
        if self.player.playing:
            self.player.fade_out()
            self.player.stop()
        self.reactor.stop()

    def run(self):
        with self.terminal.fullscreen():
            with self.terminal.hidden_cursor():
                with self.terminal.unbuffered_input():
                    signal.signal(signal.SIGINT, self._handle_sigint)
                    self.looping_call = task.LoopingCall(self.update)
                    self.looping_call.start(0.1)
                    stdio.StandardIO(InputReader(self))
                    self.reactor.run()


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
    interface = UI()
    interface.player.set_file(sys.argv[1])
    interface.player.play()
    interface.run()
