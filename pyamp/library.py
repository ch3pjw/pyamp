import os
import sqlite3
from collections import namedtuple
from twisted.internet import threads

from base import PyampBase
from player import gst


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
        self.connection = None
        self.cursor = None

    def connect(self):
        self.connection = sqlite3.connect(self.database_file)
        self.cursor = self.connection.cursor()

    def disconnect(self):
        self.connection.commit()
        self.connection.close()
        self.connection = None

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
        self.cursor.execute(
            'INSERT INTO Tracks VALUES({})'.format(self._tag_placholder), tags)

    def _discover_on_path(self, dir_path):
        dir_path = os.path.expanduser(dir_path)
        self.log.info('Discovering tracks on {}'.format(dir_path))
        self.connect()
        # FIXME: eventually, of course, we'll want data to persist
        self.cursor.execute('DROP TABLE IF EXISTS Tracks')
        self.cursor.execute('CREATE TABLE Tracks({})'.format(self._tag_spec))
        for cur_dir_path, sub_dir_names, file_names in os.walk(dir_path):
            for file_name in file_names:
                file_path = os.path.join(dir_path, file_name)
                try:
                    self._do_discover(file_path)
                except Exception:
                    self.log.exception(
                        'Error whilst discovering track {}'.format(file_path))
        self.disconnect()

    def discover_on_path(self, dir_path):
        return threads.deferToThread(self._discover_on_path, dir_path)
