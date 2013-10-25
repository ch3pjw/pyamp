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
# The gst module needs to be imported after we've set up some environment
gst = None

from twisted.internet import reactor, task, protocol, stdio

from config import load_config
from keyboard import Keyboard, bindable, is_bindable
from ui import HorizontalContainer, ProgressBar, TimeCheck
from util import clamp


class Player(object):
    def __init__(self):
        # We're the only class that should be using gst, so we'll be
        # responsible for importing it after the environment is set up
        global gst
        import gst
        self.pipeline = gst.Pipeline('pyamp_player')
        self.playbin = gst.element_factory_make('playbin2', 'pyamp_playbin')
        self.audiosink = gst.element_factory_make(
            'autoaudiosink', 'pyamp_audiosink')
        self.playbin.set_property('audio-sink', self.audiosink)
        self.pipeline.add(self.playbin)
        self.tags = {'title': ''}
        self.volume = 0.01

    def _handle_messages(self):
        bus = self.pipeline.get_bus()
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
        nanoseconds, or None if the duration could not be retrieved.
        '''
        try:
            duration, format_ = self.pipeline.query_duration(
                gst.FORMAT_TIME, None)
            return duration
        except gst.QueryError:
            pass

    def get_position(self):
        '''
        :returns: The playback position of the currently playing track, in
        nanoseconds, or None if the position could not be retrieved.
        '''
        try:
            position, format_ = self.pipeline.query_position(
                gst.FORMAT_TIME, None)
            return position
        except gst.QueryError:
            pass

    @property
    def playing(self):
        return self.state == gst.STATE_PLAYING

    @property
    def state(self):
        '''We define our own getter for state because we don't continually want
        to be doing index lookups or tuple unpacking on the result of the one
        provided by gst-python.
        '''
        success, state, pending = self.pipeline.get_state()
        return state

    @state.setter
    def state(self, state):
        '''We define a 'state' setter for symmetry with the getter.
        '''
        self.pipeline.set_state(state)

    def update(self):
        self._handle_messages()

    def set_file(self, filepath):
        filepath = os.path.abspath(filepath)
        self.playbin.set_property('uri', 'file://{}'.format(filepath))

    @bindable
    def play(self):
        self.playbin.set_property('volume', self.volume)
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
        self.state = gst.STATE_NULL

    def fade_out(self, duration=0.33):
        # FIXME: this shouldn't block!
        steps = 66
        step_time = duration / steps
        for i in range(steps, -1, -1):
            self.playbin.set_property('volume', self.volume * (i / steps))
            time.sleep(step_time)

    @bindable
    def volume_down(self):
        self.volume = self.volume - 0.001
        self.playbin.set_property('volume', self.volume)

    @bindable
    def volume_up(self):
        self.volume = self.volume + 0.001
        self.playbin.set_property('volume', self.volume)

    def seek(self, step):
        '''
        :parameter step: the time, in nanoseconds, to move in the currently
            playing track. Negative values seek backwards.
        '''
        seek_to_pos = self.get_position() + step
        seek_to_pos = clamp(seek_to_pos, 0, self.get_duration())
        self.playbin.seek_simple(
            gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, seek_to_pos)

    @bindable
    def seek_forward(self, step=1e9):
        '''
        :parameter step: the time, in nanoseconds, to move forward in the
            currently playing track.
        '''
        self.seek(step)

    @bindable
    def seek_backward(self, step=1e9):
        '''
        :parameter step: the time, in nanoseconds, to move backward in the
            currently playing track.
        '''
        self.seek(-step)


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
            position = (self.player.get_position() or 0) / 1e9
            duration = (self.player.get_duration() or 0) / 1e9
            if duration:
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
    if user_config.system.GST_DEBUG:
        os.environ['GST_DEBUG'] = user_config.system.GST_DEBUG
        os.environ['GST_DEBUG_FILE'] = user_config.system.GST_DEBUG_FILE
    interface = UI(user_config)
    interface.player.set_file(sys.argv[1])
    interface.player.play()
    interface.run()

if __name__ == '__main__':
    main()
