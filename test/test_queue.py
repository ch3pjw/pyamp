from unittest import TestCase
from mock import Mock

import asyncio
from itertools import chain
from functools import wraps

from pyamp.queue import Queue, StopPlaying, PlayMode
from pyamp.library import Library
from pyamp.util import future_with_result


def async_trial(func):
    # The name 'test' messes with nose :-(
    @wraps(func)
    def async_wrapper(self, *args, **kwargs):
        coroutine_generarator = func(self, *args, **kwargs)
        loop = asyncio.get_event_loop()
        task = asyncio.Task(coroutine_generarator, loop=loop)
        loop.run_until_complete(task)
    return async_wrapper


class TestQueue(TestCase):
    def setUp(self):
        self.library = Library('some_database.db', discoverer=Mock())
        self.queue = Queue(self.library)

    @async_trial
    def test_scheduled_queue_next_and_previous(self):
        self.queue.play_mode = PlayMode.queue_only
        self.queue.append('Track 1')
        self.queue.extend(['Track 2', 'Track 3'])
        @asyncio.coroutine
        def checks():
            result = yield from self.queue.next()
            self.assertEqual(result, 'Track 1')
            result = yield from self.queue.next()
            self.assertEqual(result, 'Track 2')
            self.assertEqual(self.queue.prev(), 'Track 1')
            self.assertEqual(self.queue.prev(), 'Track 1')
            result = yield from self.queue.next()
            self.assertEqual(result, 'Track 2')
            result = yield from self.queue.next()
            self.assertEqual(result, 'Track 3')
            try:
                yield from self.queue.next()
            except StopPlaying:
                pass
            else:
                raise AssertionError('next was supposed to raise StopPlaying')
        return checks()

    @async_trial
    def album_artist_shuffle_helper(self, type_):
        # This testing requires mocking out quite a bit of return data from the
        # library...
        mezzamorphis_tracks = [
            'Mezzanine Floor',
            'Heaven',
            'Follow',
            'Bliss',
            "It's OK",
            'Metamorphis',
            'See The Star',
            'Gravity',
            'Beautiful Sun',
            'Love Falls Down',
            'Blindfold',
            'Kiss Your Feet']
        all_about_everything_tracks = [
            'As I Am',
            'Everything',
            'Dress to Wear',
            'Hebrews Four',
            'Storm',
            'Newquay',
            'Hope of the World',
            'Eternity',
            'I Need You',
            "Lyndon's Song",
            'Promises',
            'Who is He?']
        data = {
            'artist': {
                'Delirious': mezzamorphis_tracks,
                'Becky Green': all_about_everything_tracks},
            'album': {
                'Mezzamorphis': mezzamorphis_tracks,
                'All About Everything': all_about_everything_tracks}}
        mock_get_random = Mock(side_effect=[
            future_with_result(k) for k in data[type_]])
        setattr(self.library, 'get_random_{}'.format(type_), mock_get_random)
        def mock_get_tracks(name):
            return future_with_result(data[type_][name])
        setattr(self.library, 'get_{}_tracks'.format(type_), mock_get_tracks)
        @asyncio.coroutine
        def checks(data):
            data = data[type_]
            for track_name in chain(*[data[name] for name in data]):
                result = yield from self.queue.next()
                self.assertEqual(result, track_name)
        return checks(data)

    def test_album_shuffle(self):
        self.album_artist_shuffle_helper('album')

    def test_artist_shuffle(self):
        self.queue.play_mode = PlayMode.artist_shuffle
        self.album_artist_shuffle_helper('artist')

    @async_trial
    def test_track_shuffle(self):
        tracks = ['Track1', 'Track2', 'Track3']
        self.queue.play_mode = PlayMode.track_shuffle
        self.library.get_random_track = Mock(side_effect=[
            future_with_result(track) for track in tracks])
        @asyncio.coroutine
        def checks():
            for track_name in tracks:
                result = yield from self.queue.next()
                self.assertEqual(result, track_name)
        return checks()
