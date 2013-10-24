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

from config import load_config
from keyboard import Keyboard, bindable, is_bindable
from ui import HorizontalContainer, ProgressBar, TimeCheck


class Player(object):
    def __init__(self):
        self.gst_player = gst.element_factory_make('playbin2', 'player')
        self.tags = {'title': ''}
        self.volume = 0.01

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

    @bindable
    def play(self):
        self.gst_player.set_property('volume', self.volume)
        self.state = gst.STATE_PLAYING

    @bindable
    def pause(self):
        self.state = gst.STATE_PAUSED

    @bindable
    def play_pause(self):
        if self.playing:
            self.pause()
        else:
            self.play()

    @bindable
    def stop(self):
        self.gst_player.set_state(gst.STATE_NULL)

    def fade_out(self, duration=0.33):
        # FIXME: this shouldn't block!
        steps = 66
        step_time = duration / steps
        for i in range(steps, -1, -1):
            self.gst_player.set_property('volume', self.volume * (i / steps))
            time.sleep(step_time)

    @bindable
    def volume_down(self):
        self.volume = self.volume - 0.001
        self.gst_player.set_property('volume', self.volume)

    @bindable
    def volume_up(self):
        self.volume = self.volume + 0.001
        self.gst_player.set_property('volume', self.volume)


class UI(object):
    def __init__(self, user_config, reactor=reactor):
        self.user_config = user_config
        self.reactor = reactor
        self.player = Player()
        self.progress_bar = ProgressBar(
            self.user_config.appearance.progress_bar)
        self.time_check = TimeCheck()
        self.status_bar = HorizontalContainer(
            (self.progress_bar, self.time_check))
        self.terminal = Terminal()
        self.key_bindings = self._create_key_bindings()

    def _create_bindable_funcs_map(self):
        bindable_funcs = {}
        for obj in self, self.player:
            for name in dir(obj):
                func = getattr(obj, name)
                if is_bindable(func):
                    bindable_funcs[name] = func
        return bindable_funcs

    def _create_key_bindings(self):
        bindable_funcs = self._create_bindable_funcs_map()
        key_bindings = {}
        for func_name, keys in self.user_config.key_bindings:
            if isinstance(keys, basestring):
                keys = [keys]
            for key in keys:
                key_bindings[key] = bindable_funcs[func_name]
        return key_bindings

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
        action = self.key_bindings.get(char, lambda: None)
        action()

    @bindable
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
                    self.looping_call.start(1 / 20)
                    stdio.StandardIO(InputReader(self))
                    self.reactor.run()


class InputReader(protocol.Protocol):
    def __init__(self, ui):
        self.ui = ui
        self.keyboard = Keyboard()

    def dataReceived(self, data):
        key_name = self.keyboard[data]
        self.ui.handle_input(key_name)


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


def main():
    user_config = load_config()
    interface = UI(user_config)
    interface.player.set_file(sys.argv[1])
    interface.player.play()
    interface.run()

if __name__ == '__main__':
    main()
