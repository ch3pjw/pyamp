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

from jcn import (
    Root, VerticalSplitContainer, HorizontalSplitContainer, ProgressBar, Fill,
    Label, Zebra, LineInput)
from jcn.util import LoopingCall

from .base import PyampBase
from .player import Player
from .library import Library
from .queue import Queue, PlayMode, StopPlaying
from .config import load_config
from .keyboard import bindable, is_bindable
from .ui import TimeCheck


class UI(PyampBase):
    def __init__(self, user_config, stdin=None, event_loop=None):
        super(UI, self).__init__()
        self.user_config = user_config
        self.infile = stdin or sys.stdin
        self.loop = event_loop or asyncio.get_event_loop()

        self.player = Player(initial_volume=user_config.persistent.volume)
        self.player.tags.on_update_callback = self._on_tag_update
        self.library = Library(user_config.library.database_path)
        play_mode = PlayMode.__members__.get(
            user_config.persistent.play_mode, PlayMode.album_shuffle)
        self.queue = Queue(self.library, play_mode=play_mode)
        self.player.track_end_callback = (
            lambda: self.next_track(quit_on_finished=True))

        self._make_ui_elements()
        self.key_bindings = self._create_key_bindings()

        self.searching = False
        self.latest_search_results = []

    def _make_ui_elements(self):
        self.search_results = Zebra()
        self.search_results.even_format = Root.format.on_color(234)

        self.track_info = Label()
        self.track_info.halign = 'center'

        self.progress_bar = ProgressBar(
            self.user_config.appearance.progress_bar)
        self.time_check = TimeCheck()
        fill = Fill(' ')
        fill.min_width = fill.max_width = 1
        self.track_status_bar = VerticalSplitContainer(
            self.progress_bar, fill, self.time_check)
        self.track_status_bar.min_height = self.track_status_bar.max_height = 1

        self.input = LineInput('Enter search')
        self.message_bar = Label()
        self.message_bar.min_height = self.message_bar.max_height = 1

        self.hsplit = HorizontalSplitContainer(
            self.search_results, self.track_info, self.track_status_bar,
            self.message_bar)

        self.root = Root(self.hsplit, loop=self.loop)
        self.root.handle_input = self.handle_input

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

    def _on_tag_update(self, name, value):
        if name == 'title':
            self.track_info.content = value

    def _on_search_key(self):
        if not self.searching:
            self.input.content_updated_callback = self._on_search_update
            self.input.line_received_callback = self._on_search_finalise
            self.hsplit.replace_element(self.message_bar, self.input)
            self.hsplit.active_element = self.input
            self.searching = True

    def _on_search_update(self, query):
        future = asyncio.async(self._async_search(query))
        return future

    @asyncio.coroutine
    def _async_search(self, query):
        if query:
            self.latest_search_results = yield from self.library.search_tracks(
                query)
        else:
            self.latest_search_results = []
        self.search_results.content = [
            Label(r.title) for r in self.latest_search_results]

    def _on_search_finalise(self, query):
        if self.searching:
            self.hsplit.replace_element(self.input, self.message_bar)
            self.input.content_updated_callback = None
            self.input.line_received_callback = None
            self.search_results.content = []
            self.searching = False
            self.queue.extend(self.latest_search_results)
            self.message_bar.content = (
                'Added {:d} tracks to play queue'.format(
                    len(self.latest_search_results)))

    def update(self):
        self.player.update()
        if self.player.playing:
            position = (self.player.get_position() or 0) / Gst.SECOND
            duration = (self.player.get_duration() or 0) / Gst.SECOND
            if duration:
                self.progress_bar.fraction = position / duration
            self.time_check.position = position
            self.time_check.duration = duration

    def _handle_sigint(self, signal, frame):
        self.quit()

    def handle_input(self, key):
        if key == '/':
            self._on_search_key()
        action = self.key_bindings.get(key, lambda: None)
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

    @bindable
    def next_track(self, quit_on_finished=False):
        @asyncio.coroutine
        def change_track():
            try:
                next_track = yield from self.queue.next()
            except StopPlaying:
                if quit_on_finished:
                    self.quit()
                else:
                    raise
            self.log.info('Changing to next track: {!r}'.format(
                next_track.title))
            self.player.stop()
            self.player.set_file(next_track.file_path)
            self.player.play()
        task = asyncio.Task(change_track())

    @bindable
    def previous_track(self):
        new_track = self.queue.prev()
        self.log.info('Changing to previous track: {}'.format(new_track.title))
        self.player.stop()
        self.player.set_file(new_track.file_path)
        self.player.play()

    def run(self):
        self.looping_call = LoopingCall(self.update)
        self.looping_call.start(1 / 20)
        self.root.run()


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
    if os.path.exists(sys.argv[1]):
        interface.player.set_file(sys.argv[1])
        interface.player.play()
    else:
        # Oh no! There's no file, let's do a search!
        @asyncio.coroutine
        def search_track():
            result = yield from interface.library.discover_on_path(
                user_config.library.index_paths)
            result = yield from interface.library.search_tracks(sys.argv[1])
            if result:
                interface.queue.extend(result)
                interface.next_track()
        task = asyncio.Task(search_track())
    interface.run()

if __name__ == '__main__':
    main()
