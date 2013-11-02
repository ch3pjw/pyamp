import os

from gi.repository import Gst

from .base import PyampBase
from .keyboard import bindable
from .util import clamp, moving_window


class Player(PyampBase):
    def __init__(self, initial_volume=1):
        super(Player, self).__init__()
        self.target_volume = initial_volume
        self._setup_gstreamer_pipeline()
        self.tags = {'title': ''}

    def _setup_gstreamer_pipeline(self):
        Gst.init(None)
        self.pipeline = Gst.ElementFactory.make('playbin', 'pyamp_playbin')

        self.volume = Gst.ElementFactory.make('volume', 'pyamp_volume')
        self.master_fade = Gst.ElementFactory.make(
            'volume', 'pyamp_master_fade')
        self.audiosink = Gst.ElementFactory.make(
            'autoaudiosink', 'pyamp_audiosink')

        self.sink_bin = Gst.Bin()
        self.sink_bin.set_name('pyamp_audio_sink_bin')
        for element in (self.volume, self.master_fade, self.audiosink):
            self.sink_bin.add(element)
        for source, destination in moving_window(
                (self.volume, self.master_fade, self.audiosink)):
            source.link(destination)
        pad = self.volume.get_static_pad('sink')
        ghost_pad = Gst.GhostPad.new('sink', pad)
        ghost_pad.set_active(True)
        self.sink_bin.add_pad(ghost_pad)

        self.pipeline.set_property('audio-sink', self.sink_bin)

        # FIXME: The more advanced pipeline stuff does not currently work, so
        # skip it and set up a simpler, but working player:
        return

        # The controller code seems to have gone AWOL in gstreamer 1.0 :-(
        self.volume_controller = Gst.Controller(self.volume, 'volume')
        self.volume_controller.set_interpolation_mode(
            'volume', Gst.INTERPOLATE_LINEAR)
        self.volume.set_property('volume', self.target_volume)
        self.fade_controller = Gst.Controller(self.master_fade, 'volume')
        self.fade_controller.set_interpolation_mode(
            'volume', Gst.INTERPOLATE_LINEAR)

    def _handle_messages(self):
        bus = self.pipeline.get_bus()
        while True:
            message = bus.poll(Gst.MessageType.ANY, timeout=0.01)
            if message:
                if message.type == Gst.MessageType.EOS:
                    self.stop()
                    raise StopIteration('Track finished successfully!')
                if message.type == Gst.MessageType.TAG:
                    self.tags.update(self._parse_tags(message.parse_tag()))
            else:
                break

    def _parse_tags(self, gst_tag_list):
        parsed_tags = {}
        def parse_tag(gst_tag_list, tag_name, parsed_tags):
            parsed_tags[tag_name] = gst_tag_list.get_value_index(tag_name, 0)
        gst_tag_list.foreach(parse_tag, parsed_tags)
        return parsed_tags

    def get_duration(self):
        '''
        :returns: The total duration of the currently playing track, in
        nanoseconds, or None if the duration could not be retrieved.
        '''
        success, duration = self.pipeline.query_duration(Gst.Format.TIME)
        return duration

    def get_position(self):
        '''
        :returns: The playback position of the currently playing track, in
        nanoseconds, or None if the position could not be retrieved.
        '''
        success, position = self.pipeline.query_position(Gst.Format.TIME)
        return position

    @property
    def playing(self):
        return self.state == Gst.State.PLAYING

    @property
    def state(self):
        '''We define our own getter for state because we don't continually want
        to be doing index lookups or tuple unpacking on the result of the one
        provided by gst-python.
        '''
        timeout = 0
        success, state, pending = self.pipeline.get_state(timeout)
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
        self.pipeline.set_property('uri', 'file://{}'.format(filepath))

    @bindable
    def play(self):
        self.state = Gst.State.PLAYING

    @bindable
    def pause(self):
        self.state = Gst.State.PAUSED

    @bindable
    def play_pause(self):
        if self.playing:
            self.pause()
        else:
            self.play()

    @bindable
    def stop(self):
        self.state = Gst.State.NULL

    def fade(self, level, duration):
        position = self.get_position() + (duration * Gst.SECOND)
        self.fade_controller.set('volume', position, level)

    @bindable
    def fade_out(self, duration=0.5):
        self.fade(0, duration)

    @bindable
    def fade_in(self, duration=0.5):
        self.fade(1, duration)

    def change_volume(self, delta):
        position = self.get_position() + (0.33 * Gst.SECOND)
        self.target_volume = clamp(self.target_volume + delta, 0, 1)
        self.volume_controller.set('volume', position, self.target_volume)

    @bindable
    def volume_down(self):
        self.change_volume(delta=-0.1)

    @bindable
    def volume_up(self):
        self.change_volume(delta=0.1)

    def seek(self, step):
        '''
        :parameter step: the time, in nanoseconds, to move in the currently
            playing track. Negative values seek backwards.
        '''
        seek_to_pos = self.get_position() + step
        seek_to_pos = clamp(seek_to_pos, 0, self.get_duration())
        self.pipeline.seek_simple(
            Gst.Format.TIME, Gst.SeekFlags.FLUSH, seek_to_pos)

    @bindable
    def seek_forward(self, step=None):
        '''
        :parameter step: the time, in nanoseconds, to move forward in the
            currently playing track.
        '''
        step = step or Gst.SECOND
        self.seek(step)

    @bindable
    def seek_backward(self, step=None):
        '''
        :parameter step: the time, in nanoseconds, to move backward in the
            currently playing track.
        '''
        step = step or Gst.SECOND
        self.seek(-step)
