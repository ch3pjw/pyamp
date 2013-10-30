import os
from functools import wraps

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

from base import PyampBase
from keyboard import bindable
from util import clamp, moving_window


def gst_log_calls(func):
    '''Decorator to make `func` log it's calls and arguments to the gstreamer
    log file.
    '''
    @wraps(func)
    def logging_func(*args, **kwargs):
        gst.info(' {} '.format(func.__name__).center(35, '-'))
        gst.info('called with args: {}, kwargs: {}'.format(args, kwargs))
        result = func(*args, **kwargs)
        gst.info('{} result: {}'.format(func.__name__, result))
        gst.info('-' * 35)
        return result
    return logging_func


class Player(PyampBase):
    def __init__(self, initial_volume=1):
        super(Player, self).__init__()
        # Because someone else may be responsible for setting up the
        # environment before gst import, we do the import here, which is as
        # late as possible, and pretend to the rest of the world like gst was
        # here all along :-s
        import gst as gstreamer
        gst.module = gstreamer
        self.target_volume = initial_volume
        self._setup_gstreamer_pipeline()
        self.tags = {'title': ''}

    @gst_log_calls
    def _setup_gstreamer_pipeline(self):
        Gst.init(None)
        element_factory = Gst.ElementFactory()
        self.pipeline = element_factory.make('playbin', 'pyamp_playbin')

        self.volume = element_factory.make('volume', 'pyamp_volume')
        self.master_fade = element_factory.make(
            'volume', 'pyamp_master_fade')
        self.audiosink = element_factory.make(
            'autoaudiosink', 'pyamp_audiosink')

        self.sink_bin = Gst.Bin()
        self.sink_bin.set_name('pyamp_audio_sink_bin')
        for element in (self.volume, self.master_fade, self.audiosink):
            self.sink_bin.add(element)
        for source, destination in moving_window(
                (self.volume, self.master_fade, self.audiosink)):
            source.link(destination)
        pad = self.volume.get_static_pad('sink')
        ghost_pad = Gst.GhostPad()
        ghost_pad.set_target(pad)
        ghost_pad.set_active(True)
        self.sink_bin.add_pad(ghost_pad)

        self.pipeline.set_property('audio-sink', self.sink_bin)

        self.volume_controller = gst.Controller(self.volume, 'volume')
        self.volume_controller.set_interpolation_mode(
            'volume', gst.INTERPOLATE_LINEAR)
        self.volume.set_property('volume', self.target_volume)
        self.fade_controller = gst.Controller(self.master_fade, 'volume')
        self.fade_controller.set_interpolation_mode(
            'volume', gst.INTERPOLATE_LINEAR)

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

    @gst_log_calls
    def set_file(self, filepath):
        filepath = os.path.abspath(filepath)
        self.pipeline.set_property('uri', 'file://{}'.format(filepath))

    @bindable
    @gst_log_calls
    def play(self):
        self.state = gst.STATE_PLAYING

    @bindable
    @gst_log_calls
    def pause(self):
        self.state = gst.STATE_PAUSED

    @bindable
    @gst_log_calls
    def play_pause(self):
        if self.playing:
            self.pause()
        else:
            self.play()

    @bindable
    @gst_log_calls
    def stop(self):
        self.state = gst.STATE_NULL

    @gst_log_calls
    def fade(self, level, duration):
        position = self.get_position() + (duration * gst.SECOND)
        self.fade_controller.set('volume', position, level)

    @bindable
    def fade_out(self, duration=0.5):
        self.fade(0, duration)

    @bindable
    def fade_in(self, duration=0.5):
        self.fade(1, duration)

    @gst_log_calls
    def change_volume(self, delta):
        position = self.get_position() + (0.33 * gst.SECOND)
        self.target_volume = clamp(self.target_volume + delta, 0, 1)
        self.volume_controller.set('volume', position, self.target_volume)

    @bindable
    def volume_down(self):
        self.change_volume(delta=-0.1)

    @bindable
    def volume_up(self):
        self.change_volume(delta=0.1)

    @gst_log_calls
    def seek(self, step):
        '''
        :parameter step: the time, in nanoseconds, to move in the currently
            playing track. Negative values seek backwards.
        '''
        seek_to_pos = self.get_position() + step
        seek_to_pos = clamp(seek_to_pos, 0, self.get_duration())
        self.pipeline.seek_simple(
            gst.FORMAT_TIME, gst.SEEK_FLAG_FLUSH, seek_to_pos)

    @bindable
    def seek_forward(self, step=None):
        '''
        :parameter step: the time, in nanoseconds, to move forward in the
            currently playing track.
        '''
        step = step or gst.SECOND
        self.seek(step)

    @bindable
    def seek_backward(self, step=None):
        '''
        :parameter step: the time, in nanoseconds, to move backward in the
            currently playing track.
        '''
        step = step or gst.SECOND
        self.seek(-step)
