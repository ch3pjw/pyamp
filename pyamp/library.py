import os
import sqlite3
from functools import wraps
from abc import abstractproperty
from gi.repository import Gst

from .base import PyampBase
from .util import threaded_future


class SqlRepresentableType(PyampBase):
    @abstractproperty
    def _col_types(self):
        '''`dict`-like object listing key-value pairs of all column names and
        their Python data type.
        '''

    @abstractproperty
    def _col_attrs(self):
        '''`dict`-like object listing string of attributes associated with a
        given column.
        '''

    _python_to_sql_type = {
        str: 'TEXT',
        int: 'LONG',
        float: 'SINGLE'}

    def __init__(self, *args):
        for col_name in self._col_types:
            self.__dict__[col_name] = None
        try:
            dict_like = args[0]
            # dict-like might be a gst.TagList object, which only has .keys()
            for attr_name in dict_like.keys():
                safe_attr_name = attr_name.replace('-', '_')
                setattr(self, safe_attr_name, dict_like[attr_name])
        except (IndexError, AttributeError):
            for col_name, col_data in zip(self._get_col_names(), args):
                setattr(self, col_name, col_data)

    @classmethod
    def _get_col_names(cls):
        return sorted(cls._col_types.keys())

    def __len__(self):
        return len(self._col_types)

    def __getitem__(self, index):
        attr_name = self._get_col_names()[index]
        return getattr(self, attr_name)

    def __setattr__(self, col_name, value):
        '''We override setattr so that only tag-named attributes can be set,
        and so that we can sanitise that data before it's stored.
        '''
        if col_name not in self._col_types:
            raise AttributeError('{!r} object has no attribute {!r}'.format(
                self.__class__.__name__, col_name))
        if value is not None:
            value = self._col_types[col_name](value)
        self.__dict__[col_name] = value

    @classmethod
    def _get_schema(cls):
        rows = []
        for col_name in cls._get_col_names():
            row = [col_name]
            row.append(cls._python_to_sql_type[cls._col_types[col_name]])
            attrs = cls._col_attrs.get(col_name)
            if attrs:
                row.append(attrs)
            rows.append(' '.join(row))
        return ', '.join(rows)

    @classmethod
    def _iter_schema(cls):
        for i, col_name in enumerate(cls._get_col_names()):
            col_type = cls._python_to_sql_type[cls._col_types[col_name]]
            yield i, col_name, col_type, 0, None, 0

    @classmethod
    def create_table(cls, cursor):
        cls.log.debug('Creating new {} table'.format(cls.__name__))
        cursor.execute('CREATE TABLE {}({})'.format(
            cls.__name__, cls._get_schema()))

    @classmethod
    def create_table_if_required(cls, cursor):
        cursor.execute('PRAGMA table_info({})'.format(cls.__name__))
        result = cursor.fetchall()
        if result:
            cls.log.debug('Found existing {} table'.format(cls.__name__))
            if len(result) == len(cls._col_types):
                for file_column, schema_column in zip(
                        result, cls._iter_schema()):
                    if file_column != schema_column:
                        break
                else:
                    cls.log.debug('{} table conforms to schema'.format(
                        cls.__name__))
                    return
            cls.log.warning(
                '{} table does not conform to schema'.format(cls.__name__))
            cls.drop_table(cursor)
        cls.create_table(cursor)

    @classmethod
    def drop_table(cls, cursor):
        cls.log.debug('Dropping {} table'.format(cls.__name__))
        cursor.execute('DROP TABLE {}'.format(cls.__name__))

    def insert_or_replace(self, cursor):
        value_placeholder = ', '.join('?' * len(self))
        col_names_placeholder = ', '.join(self._get_col_names())
        cursor.execute(
            'INSERT OR REPLACE INTO {}({}) VALUES ({})'.format(
                self.__class__.__name__, col_names_placeholder,
                value_placeholder),
            self)

    @classmethod
    def _search(cls, cursor, search_dict, operator, join_keyword):
        query_placeholder = join_keyword.join(
            '{} {} ?'.format(k, operator) for k in search_dict)
        cursor.execute(
            'SELECT * FROM {} WHERE {}'.format(
                cls.__name__, query_placeholder),
            search_dict.values())
        return [cls(*row) for row in cursor.fetchall()]

    @classmethod
    def _search_one(cls, cursor, search_dict, operator, join_keyword):
        result = cls._search(cursor, search_dict, operator, join_keyword)
        if len(result) != 1:
            raise ValueError(
                'Search of {} table for {} returned {:d} hits, which is != '
                '1'.format(cls.__name__, search_dict, len(result)))
        else:
            return result[0]

    @classmethod
    def exact_search(cls, cursor, search_dict, operator='='):
        '''Searches the existing database table accessed via cursor for the
        all of the col_name/value pairs specified in the search_dict.

        :returns: A list of new instances of this class if values are found.
        '''
        return cls._search(cursor, search_dict, operator, ' AND ')

    @classmethod
    def exact_search_one(cls, cursor, search_dict, operator='='):
        '''
        :returns: The only result of an exact search or an error if there is
            not exactly one result.
        '''
        return cls._search_one(cursor, search_dict, operator, ' AND ')

    @classmethod
    def search(cls, cursor, search_dict, operator='='):
        '''Searches the existing database table accessed via cursor for the
        any of the col_name/value pairs specified in the search_dict.

        :returns: A list of new instances of this class if values are found.
        '''
        return cls._search(cursor, search_dict, operator, ' OR ')

    @classmethod
    def search_one(cls, cursor, search_dict, operator='='):
        '''
        :returns: The only result of a search or an error if there is not
            exactly one result.
        '''
        return cls._search_one(cursor, search_dict, operator, ' OR ')

    @classmethod
    def list(cls, cursor):
        cursor.execute('SELECT * FROM {}'.format(cls.__name__))
        return [cls(*row) for row in cursor.fetchall()]


class TrackMetadata(SqlRepresentableType):
    _col_types = {
        'album': str,
        'artist': str,
        'audio_codec': str,
        'bitrate': int,
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
    _col_attrs = {
        'file_path': 'UNIQUE'}


class Dir(SqlRepresentableType):
    _col_types = {
        'path': str,
        'modified_time': float}
    _col_attrs = {}


def blocking(func):
    '''Decorator to execute a blocking method in a thread and wrap the
    management in a future.
    '''
    @wraps(func)
    def non_blocking_call(*args, **kwargs):
        return threaded_future(func, *args, **kwargs)
    return non_blocking_call


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
    def __init__(self, database_file):
        super(Library, self).__init__()
        self.database_file = os.path.expanduser(database_file)
        from gst import pbutils
        self.discoverer = pbutils.Discoverer(Gst.SECOND)

    def _do_discover_dir(self, dir_path, file_names):
        track_metadata_list = []
        for file_name in file_names:
            file_path = os.path.join(dir_path, file_name)
            try:
                track_metadata = self._do_discover_file(file_path)
                if track_metadata:
                    track_metadata_list.append(track_metadata)
            except Exception:
                self.log.exception(
                    'Error whilst discovering track {}'.format(file_path))
        return track_metadata_list

    def _do_discover_file(self, file_path):
        info = self.discoverer.discover_uri('file://' + file_path)
        gst_tags = info.get_tags()
        if gst_tags:
            metadata = TrackMetadata(gst_tags)
            metadata.file_path = file_path
            file_stats = os.stat(file_path)
            metadata.modified_time = file_stats.st_mtime
            self.log.debug('Found file {}'.format(file_path))
            return metadata

    def _dir_modified(self, cursor, dir_path):
        '''
        :returns: None if the `dir_path` has not been modified since we last
        indexed it, or the modified time if it has been updated.
        '''
        current_mtime = os.stat(dir_path).st_mtime
        try:
            directory = Dir.search_one(cursor, {'path': dir_path})
        except ValueError:
            return current_mtime
        else:
            if current_mtime != directory.modified_time:
                return current_mtime

    def _update_dir_if_required(self, cursor, dir_path, file_names):
        result = 0
        modified_time = self._dir_modified(cursor, dir_path)
        if modified_time:
            track_metadata_list = self._do_discover_dir(dir_path, file_names)
            for track_metadata in track_metadata_list:
                track_metadata.insert_or_replace(cursor)
            directory = Dir({'path': dir_path, 'modified_time': modified_time})
            directory.insert_or_replace(cursor)
            result = len(track_metadata_list)
        return result

    @blocking
    @with_database_cursor
    def discover_on_path(self, cursor, dir_path):
        dir_path = os.path.expanduser(dir_path)
        self.log.info('Discovering new tracks on {}'.format(dir_path))
        TrackMetadata.create_table_if_required(cursor)
        Dir.create_table_if_required(cursor)
        tracks_visited = 0
        for cur_dir_path, sub_dir_names, file_names in os.walk(dir_path):
            tracks_visited += self._update_dir_if_required(
                cursor, cur_dir_path, file_names)
        self.log.info(
            'Discovery complete, {:d} tracks visited'.format(tracks_visited))

    @blocking
    @with_database_cursor
    def search_tracks(self, cursor, search_string):
        self.log.debug(
            'Performing track search for {!r}'.format(search_string))
        search_string = '%{}%'.format(search_string)
        return TrackMetadata.search(
            cursor, {
                'artist': search_string,
                'album': search_string,
                'title': search_string},
            operator='LIKE')

    @blocking
    @with_database_cursor
    def list_tracks(self, cursor):
        return TrackMetadata.list(cursor)
