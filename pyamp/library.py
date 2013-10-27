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
    _metadata_sql_spec = [
        (name, _format_to_sql_spec[format_]) for name, format_ in
        _metadata_format.iteritems()]

    def __init__(self, database_file):
        super(Library, self).__init__()
        self.database_file = os.path.expanduser(database_file)
        from gst import pbutils
        self.discoverer = pbutils.Discoverer(gst.SECOND)

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
        file_stats = os.stat(file_path)
        tag_dict['modified_time'] = file_stats.st_mtime
        return self.Metadata(**tag_dict)

    def _do_discover(self, file_path):
        info = self.discoverer.discover_uri('file://' + file_path)
        metadata = self._make_metadata(file_path, info.get_tags())
        self.log.debug('Found file {}'.format(metadata))
        return metadata

    def _create_table_if_required(self, cursor, table_name, spec):
        cursor.execute('PRAGMA table_info({})'.format(table_name))
        table_schema = cursor.fetchall()
        if table_schema:
            self.log.debug('Found existing {} table...'.format(table_name))
            existing_spec = []
            for column in table_schema:
                id_, name, type_, _, _, _ = column
                existing_spec.append((name, type_))
            if existing_spec == spec:
                self.log.debug(
                    '{} table conforms to schema'.format(table_name))
                return
            else:
                self.log.warning(
                    '{} table does not conform to schema, dropping'.format(
                        table_name))
                cursor.execute('DROP TABLE {}'.format(table_name))
        self.log.debug('Creating new {} table'.format(table_name))
        spec_string = ', '.join(
            '{} {}'.format(name, type_) for name, type_ in spec)
        cursor.execute('CREATE TABLE {}({})'.format(table_name, spec_string))

    @blocking
    @with_database_cursor
    def discover_on_path(self, cursor, dir_path):
        dir_path = os.path.expanduser(dir_path)
        self.log.info('Discovering tracks on {}'.format(dir_path))
        self._create_table_if_required(
            cursor, 'Dirs',
            [('dir_path', 'TEXT'), ('modified_time', 'SINGLE')])
        self._create_table_if_required(
            cursor, 'Tracks', self._metadata_sql_spec)
        for cur_dir_path, sub_dir_names, file_names in os.walk(dir_path):
            dir_stats = os.stat(cur_dir_path)
            cursor.execute(
                'INSERT INTO Dirs VALUES(?, ?)',
                (cur_dir_path, dir_stats.st_mtime))
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
        query = 'SELECT file_path FROM Tracks WHERE '
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
