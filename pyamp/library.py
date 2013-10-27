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


class Library(PyampBase):
    _metadata_format = {
        'album': str,
        'artist': str,
        'audio_codec': str,
        'bitrate': long,
        'container_format': str,
        'date': str,
        'encoder': str,
        'encoder_version': str,
        'file_path': str,
        'genre': str,
        'modified_time': float,
        'nominal_bitrate': str,
        'title': str,
        'track_number': int}
    _format_to_sql_spec = {
        str: 'TEXT',
        int: 'INTEGER',
        long: 'LONG',
        float: 'SINGLE'}
    Metadata = namedtuple('Metadata', _metadata_format.keys())
    _metadata_placeholder = ', '.join('?' * len(_metadata_format))

    def __init__(self, database_file):
        super(Library, self).__init__()
        self.database_file = os.path.expanduser(database_file)
        from gst import pbutils
        self.discoverer = pbutils.Discoverer(gst.SECOND)

    @property
    def _metadata_sql_spec(self):
        '''We want this to be a class variable, but we can't easily calculate
        it in the class definition because of name scoping. So, lets make a
        property that replaces itself on first call.
        '''
        metadata_sql_spec = ', '.join('{name} {type_}'.format(
            name=name, type_=self._format_to_sql_spec[format_]) for
            name, format_ in self._metadata_format.iteritems())
        self.__class__._metadata_sql_spec = metadata_sql_spec
        return metadata_sql_spec

    def _make_metadata(self, file_path, gst_tags):
        tag_dict = {}
        for tag_name in self._metadata_format.iterkeys():
            gst_tag_name = tag_name.replace('_', '-')
            if gst_tag_name in gst_tags:
                formatter = self._metadata_format[tag_name]
                tag_dict[tag_name] = formatter(gst_tags[gst_tag_name])
            else:
                tag_dict[tag_name] = None
        tag_dict['file_path'] = file_path
        return self.Metadata(**tag_dict)

    def _do_discover(self, file_path):
        info = self.discoverer.discover_uri('file://' + file_path)
        metadata = self._make_metadata(file_path, info.get_tags())
        self.log.debug('Found file {}'.format(metadata))
        return metadata

    @blocking
    @with_database_cursor
    def discover_on_path(self, cursor, dir_path):
        dir_path = os.path.expanduser(dir_path)
        self.log.info('Discovering tracks on {}'.format(dir_path))
        # FIXME: eventually, of course, we'll want data to persist
        cursor.execute('DROP TABLE IF EXISTS Tracks')
        cursor.execute('CREATE TABLE Tracks({})'.format(
            self._metadata_sql_spec))
        for cur_dir_path, sub_dir_names, file_names in os.walk(dir_path):
            for file_name in file_names:
                file_path = os.path.join(cur_dir_path, file_name)
                try:
                    metadata = self._do_discover(file_path)
                    cursor.execute(
                        'INSERT INTO Tracks VALUES({})'.format(
                            self._metadata_placeholder),
                        metadata)
                except Exception:
                    self.log.exception(
                        'Error whilst discovering track {}'.format(file_path))

    def _get_search_query(self, search_string):
        searchable_fields = 'artist', 'album', 'title'
        query = 'SELECT DISTINCT file_path FROM Tracks WHERE '
        search_portion = "{field} LIKE '%{search_string}%'"
        search_portions = ' OR '.join(search_portion.format(
            field=field, search_string=search_string) for field in
            searchable_fields)
        query += search_portions
        return query

    @blocking
    @with_database_cursor
    def search_tracks(self, cursor, search_string):
        search_query = self._get_search_query(search_string)
        self.log.debug(
            'Performing track search with query: {}'.format(search_query))
        cursor.execute(search_query)
        return cursor.fetchall()

    @blocking
    @with_database_cursor
    def list_tracks(self, cursor):
        cursor.execute('SELECT * FROM Tracks')
        return cursor.fetchall()
