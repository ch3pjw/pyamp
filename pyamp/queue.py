import asyncio
from enum import Enum, unique


class StopPlaying(Exception):
    pass


@unique
class PlayMode(Enum):
    queue_only = 0
    album_shuffle = 1
    artist_shuffle = 2
    track_shuffle = 3


class Queue:
    '''Class to represent a queue of tracks that pyamp is playing though.
    '''
    def __init__(self, library, play_mode=PlayMode.album_shuffle):
        self._library = library
        self._play_mode = play_mode
        self._playing_track = None
        self._scheduled_tracks = []
        self._dynamic_tracks = []
        self._played_tracks = []

    @property
    def play_mode(self):
        return self._play_mode

    @play_mode.setter
    def play_mode(self, play_mode):
        self._dynamic_tracks[:] = []
        self._play_mode = play_mode

    @asyncio.coroutine
    def next(self):
        if self._playing_track:
            self._played_tracks.append(self._playing_track)
        if self._scheduled_tracks:
            self._playing_track = self._scheduled_tracks.pop(0)
        else:
            self._playing_track = yield from self.get_next_dynamic_track()
        return self._playing_track

    def prev(self):
        if self._played_tracks:
            self._scheduled_tracks.insert(0, self._playing_track)
            self._playing_track = self._played_tracks.pop()
        return self._playing_track

    def append(self, track_metadata):
        '''Appends a single track_metadata item to the predefined queue.
        '''
        self._scheduled_tracks.append(track_metadata)

    def extend(self, track_metadata_iterable):
        '''Extends the existing predefined queue of tracks with those from the
        provided iterable.
        '''
        self._scheduled_tracks.extend(track_metadata_iterable)

    @asyncio.coroutine
    def get_next_dynamic_track(self):
        if self._play_mode is PlayMode.queue_only:
            raise StopPlaying('Play queue finished')
        else:
            if not self._dynamic_tracks:
                yield from self._populate_dynamic_tracks()
            return self._dynamic_tracks.pop(0)

    @asyncio.coroutine
    def _populate_dynamic_tracks(self):
        if self._play_mode == PlayMode.album_shuffle:
            album_name = yield from self._library.get_random_album()
            new_tracks = yield from self._library.get_album_tracks(
                album_name)
        elif self._play_mode == PlayMode.artist_shuffle:
            artist_name = yield from self._library.get_random_artist()
            new_tracks = yield from self._library.get_artist_tracks(
                artist_name)
        elif self._play_mode == PlayMode.track_shuffle:
            track = yield from self._library.get_random_track()
            new_tracks = [track]
        self._dynamic_tracks.extend(new_tracks)
