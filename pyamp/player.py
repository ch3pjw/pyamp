import os
import logging

from gi.repository import Gst, GstController

from .base import PyampBase
from .keyboard import bindable
from .util import clamp, moving_window


class SweepingInterpolationControlSource(
        GstController.InterpolationControlSource):
    '''This class extends the normal InterpolationControlSource to include the
    concept of a target value, and is intended to smooth transitions to desired
    user values. We maintain an in initial control point at t=0 with the users
    desired value, add control points as required to execute their transition
    on demand, and add a facility to remove those extra control points on
    events such as track seeks, so that we don't replay their control events,
    but instead keep to their target value.
    '''
    def __init__(self, target_value, scaling_factor=1, min_=0, max_=1, *args,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.scaling_factor = scaling_factor
        self.min = min_
        self.max = max_
        self._target_value = None
        self._additional_control_point_times = []
        self._last_set_time = 0
        self.set_target(target_value)
        self.log = logging.getLogger(self.__class__.__name__)

    def set_target(self, target_value):
        self._target_value = target_value
        self.set(0, self._target_value * self.scaling_factor)

    def set_sweep(self, current_time, delta_time, future_value):
        if future_value != self._target_value:
            if current_time > self._last_set_time:
                self._set(current_time, self._target_value)
            self._set(current_time + delta_time, future_value)
            self.set_target(future_value)

    def set_sweep_delta(self, current_time, delta_time, delta_value):
        future_value = clamp(
            self._target_value + delta_value, self.min, self.max)
        self.set_sweep(current_time, delta_time, future_value)

    def _set(self, time, value):
        result = super().set(time, value * self.scaling_factor)
        if result:
            self._additional_control_point_times.append(time)
            self._last_set_time = time
        return result

    def reset(self):
        '''Removes all but the initial control point with the target value.
        This should be called when one performs an operation such as a seek
        that would otherwise replay a user's control inputs.
        '''
        for time in self._additional_control_point_times:
            self.unset(time)
        self._additional_control_point_times[:] = []


class Player(PyampBase):
    # Gstreamer volume goes from 0 - 1000%, so we need to scale our controller
    # output values:
    volume_scaling_factor = 0.1

    def __init__(self, initial_volume=1):
        super().__init__()
        self._setup_gstreamer_pipeline(initial_volume)
        self.tags = {'title': ''}

    def _setup_gstreamer_pipeline(self, initial_volume):
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

        self.volume_controller = SweepingInterpolationControlSource(
            target_value=initial_volume,
            scaling_factor=self.volume_scaling_factor)
        self.volume_controller.set_property(
            'mode', GstController.InterpolationMode.LINEAR)
        binding = GstController.DirectControlBinding.new(
            self.volume, 'volume', self.volume_controller)
        self.volume.add_control_binding(binding)

        self.fade_controller = SweepingInterpolationControlSource(
            target_value=1, scaling_factor=self.volume_scaling_factor)
        self.fade_controller.set_property(
            'mode', GstController.InterpolationMode.CUBIC)
        binding = GstController.DirectControlBinding.new(
            self.master_fade, 'volume', self.fade_controller)
        self.master_fade.add_control_binding(binding)

    def _handle_messages(self):
        bus = self.pipeline.get_bus()
        while True:
            message = bus.poll(
                Gst.MessageType.EOS | Gst.MessageType.TAG,
                timeout=0.01)
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
        self.log.info('Playing...')
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

    def fade(self, duration, level):
        self.fade_controller.set_sweep(
            self.get_position(), duration * Gst.SECOND, level)

    @bindable
    def fade_out(self, duration=0.5):
        self.fade(duration, 0)

    @bindable
    def fade_in(self, duration=0.5):
        self.fade(duration, 1)

    def change_volume(self, delta):
        self.volume_controller.set_sweep_delta(
            self.get_position(), 0.33 * Gst.SECOND, delta)

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
        self.volume_controller.reset()
        self.fade_controller.reset()

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
