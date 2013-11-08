#! /usr/bin/env python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import sys
import os
import signal
import logging
import asyncio
import fcntl
asyncio.log.logger.setLevel('INFO')

from .base import PyampBase
from .player import Player
from .library import Library
from .config import load_config
from .keyboard import Keyboard, bindable, is_bindable
from .terminal import Terminal
from .ui import HorizontalContainer, ProgressBar, TimeCheck
from .util import LoopingCall


class UI(PyampBase):
    def __init__(self, user_config, stdin=None, event_loop=None):
        super(UI, self).__init__()
        self.user_config = user_config
        self.infile = stdin or sys.stdin
        self.loop = event_loop or asyncio.get_event_loop()
        self.keyboard = Keyboard()

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
            if isinstance(keys, str):
                keys = [keys]
            for key in keys:
                key = ' '.join(key.split())
                if func_name in bindable_funcs:
                    key_bindings[key] = bindable_funcs[func_name]
                else:
                    self.log.warning(
                        'Warning: {} is not a bindable pyamp function'.format(
                            func_name))
        return key_bindings

    def update(self):
        try:
            self.player.update()
        except StopIteration:
            self.quit()
        self.draw()

    def draw(self):
        #print(self.terminal.clear())
        if self.player.playing:
            position = (self.player.get_position() or 0) / Gst.SECOND
            duration = (self.player.get_duration() or 0) / Gst.SECOND
            if duration:
                self.progress_bar.fraction = position / duration
            self.time_check.position = position
            self.time_check.duration = duration
        total_width = self.terminal.width - 2
        with self.terminal.location(0, self.terminal.height - 2):
            print(self.player.tags['title'].center(self.terminal.width))
            print(self.status_bar.draw(total_width, 1).center(
                self.terminal.width), end='')
        sys.stdout.flush()

    def _handle_sigint(self, signal, frame):
        self.quit()

    def handle_input(self, data):
        keystroke = self.keyboard[data]
        action = self.key_bindings.get(keystroke, lambda: None)
        action()

    @bindable
    def quit(self):
        def clean_up():
            self.player.stop()
            self.loop.stop()
        if self.player.playing:
            fade_out_time = 1
            self.player.fade_out(fade_out_time)
            self.loop.call_later(fade_out_time + 0.1, clean_up)
        else:
            clean_up()

    def _setup_terminal_input(self):
        if hasattr(self.infile, 'fileno'):
            # Use fcntl to set stdin to non-blocking. WARNING - this is not
            # particularly portable!
            flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
            flags = flags | os.O_NONBLOCK
            fcntl.fcntl(sys.stdin, fcntl.F_SETFL, flags)
        def read_stdin():
            data = self.infile.read()
            self.handle_input(data)
        self.loop.add_reader(sys.stdin, read_stdin)

    def run(self):
        with self.terminal.fullscreen():
            with self.terminal.hidden_cursor():
                with self.terminal.unbuffered_input():
                    signal.signal(signal.SIGINT, self._handle_sigint)
                    signal.signal(signal.SIGTSTP, self.terminal.handle_sigtstp)
                    self._setup_terminal_input()
                    self.looping_call = LoopingCall(self.update)
                    self.looping_call.start(1 / 20)
                    self.loop.run_forever()


def set_up_environment(user_config):
    '''Set up the environment for pyamp to run in - side effects galore!
    '''
    if user_config.system.GST_DEBUG:
        os.environ['GST_DEBUG'] = user_config.system.GST_DEBUG
        os.environ['GST_DEBUG_FILE'] = user_config.system.GST_DEBUG_FILE
    logging.basicConfig(
        filename=user_config.system.log_file,
        filemode='w',
        level=getattr(logging, user_config.system.log_level.upper()),
        format='[%(asctime)s %(name)s %(levelname)s] %(message)s',
        datefmt='%H:%M:%S')
    os.stat_float_times(True)


def main():
    user_config = load_config()
    set_up_environment(user_config)
    interface = UI(user_config)
    library = Library(user_config.library.database_path)
    if os.path.exists(sys.argv[1]):
        interface.player.set_file(sys.argv[1])
        interface.player.play()
    else:
        # Oh no! There's no file, let's do a search!
        @asyncio.coroutine
        def search_track():
            result = yield from library.discover_on_path(
                user_config.library.index_paths)
            result = yield from library.search_tracks(sys.argv[1])
            if result:
                interface.player.set_file(result[0].file_path)
                interface.player.play()
        task = asyncio.Task(search_track())
    interface.run()

if __name__ == '__main__':
    main()
