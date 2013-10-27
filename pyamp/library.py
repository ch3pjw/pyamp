import os
import sqlite3
from collections import namedtuple
from functools import wraps
from twisted.internet import threads

from base import PyampBase
from player import gst


def blocking(func):
    '''Decorator to defer a blocking method to a thread.
    '''
    @wraps(func)
    def deferred_to_thread(*args, **kwargs):
        return threads.deferToThread(func, *args, **kwargs)
    return deferred_to_thread


def with_database_cursor(func):
    '''Turns out we can't easily share sqlite database connections when we're
    deferring stuff to thread, because sqlite doesn't want to share
    connection/cursor objects between threads. This decorator sets up a new
    database connection for each method call.
    '''
    @wraps(func)
    def func_with_cursor(self, *args, **kwargs):
        with sqlite3.connect(self.database_file) as connection:
            cursor = connection.cursor()
            return func(self, cursor, *args, **kwargs)
    return func_with_cursor


Tags = namedtuple(
    'Tags', (
        'album', 'artist', 'audio_codec', 'bitrate', 'container_format',
        'date', 'encoder', 'encoder_version', 'file_path', 'genre',
        'nominal_bitrate', 'title', 'track_number'))


class Library(PyampBase):
    _tag_spec = ', '.join('{} TEXT'.format(name) for name in Tags._fields)
    _tag_placholder = ', '.join('?' * len(Tags._fields))

    def __init__(self, database_file):
        super(Library, self).__init__()
        self.database_file = os.path.expanduser(database_file)
        from gst import pbutils
        self.discoverer = pbutils.Discoverer(gst.SECOND)

    def _make_tags(self, file_path, gst_tags):
        tag_dict = {}
        for tag_name in Tags._fields:
            gst_tag_name = tag_name.replace('_', '-')
            if tag_name in gst_tags:
                tag_dict[tag_name] = str(gst_tags[gst_tag_name])
            else:
                tag_dict[tag_name] = None
        tag_dict['file_path'] = file_path
        return Tags(**tag_dict)

    def _do_discover(self, file_path):
        info = self.discoverer.discover_uri('file://' + file_path)
        tags = self._make_tags(file_path, info.get_tags())
        self.log.debug('Found file {}'.format(tags))
        return tags

    @blocking
    @with_database_cursor
    def discover_on_path(self, cursor, dir_path):
        dir_path = os.path.expanduser(dir_path)
        self.log.info('Discovering tracks on {}'.format(dir_path))
        # FIXME: eventually, of course, we'll want data to persist
        cursor.execute('DROP TABLE IF EXISTS Tracks')
        cursor.execute('CREATE TABLE Tracks({})'.format(self._tag_spec))
        for cur_dir_path, sub_dir_names, file_names in os.walk(dir_path):
            for file_name in file_names:
                file_path = os.path.join(dir_path, file_name)
                try:
                    tags = self._do_discover(file_path)
                    cursor.execute(
                        'INSERT INTO Tracks VALUES({})'.format(
                            self._tag_placholder),
                        tags)
                except Exception:
                    self.log.exception(
                        'Error whilst discovering track {}'.format(file_path))

