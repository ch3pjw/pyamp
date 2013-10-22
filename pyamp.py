#! /usr/bin/env python
from __future__ import division

import sys
import os
import signal
import time

import blessings

import pygst
pygst.require('0.10')
import gst

from twisted.internet import reactor, task


class Player(object):
    def __init__(self, reactor=reactor):
        self.reactor = reactor
        self.gst_player = gst.element_factory_make('playbin2', 'player')

        self.progress_bar = ProgressBar()
        self.terminal = blessings.Terminal()

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

    def update(self):
        self._handle_messages()
        if self.gst_player.get_state()[1] == gst.STATE_PLAYING:
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
        self.gst_player.set_state(gst.STATE_PLAYING)

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
        self.fade_out()
        self.stop()

    def run(self):
        with self.terminal.fullscreen():
            with self.terminal.hidden_cursor():
                signal.signal(signal.SIGINT, self._handle_sigint)
                self.looping_call = task.LoopingCall(self.update)
                self.looping_call.start(0.1)
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


if __name__ == '__main__':
    p = Player()
    p.set_file(sys.argv[1])
    p.play()
    p.run()
