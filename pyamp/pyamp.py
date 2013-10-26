#! /usr/bin/env python
from __future__ import division

import sys
import os
import signal
import logging

from twisted.internet import reactor, task, protocol, stdio

from player import Player, gst, gst_log_calls
from config import load_config
from keyboard import Keyboard, bindable, is_bindable
from terminal import Terminal
from ui import HorizontalContainer, ProgressBar, TimeCheck


class UI(object):
    def __init__(self, user_config, reactor=reactor):
        self.user_config = user_config
        self.reactor = reactor
        self.player = Player(initial_volume=user_config.persistent.volume)
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
                if func_name in bindable_funcs:
                    key_bindings[key] = bindable_funcs[func_name]
                else:
                    print ('Warning: {} is not a bindable pyamp '
                           'function'.format(func_name))
        return key_bindings

    def update(self):
        try:
            self.player.update()
        except StopIteration:
            self.quit()
        self.draw()

    def draw(self):
        #print self.terminal.clear()
        if self.player.playing:
            position = (self.player.get_position() or 0) / gst.SECOND
            duration = (self.player.get_duration() or 0) / gst.SECOND
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
    @gst_log_calls
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


def main():
    user_config = load_config()
    if user_config.system.GST_DEBUG:
        os.environ['GST_DEBUG'] = user_config.system.GST_DEBUG
        os.environ['GST_DEBUG_FILE'] = user_config.system.GST_DEBUG_FILE
    logging.basicConfig(
        filename=user_config.system.log_file,
        level=getattr(logging, user_config.system.log_level.upper()))
    interface = UI(user_config)
    interface.player.set_file(sys.argv[1])
    interface.player.play()
    interface.run()

if __name__ == '__main__':
    main()
