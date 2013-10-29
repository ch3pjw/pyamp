import os
import sqlite3
from collections import namedtuple
from functools import wraps
from twisted.internet import threads
from abc import ABCMeta, abstractproperty

from base import PyampBase
from player import gst


class SqlRepresentableTypeMeta(ABCMeta):
    '''We define a metaclass so that any SqlRepresentableType we define will
    automatically be registered as a converter for the sqlite3 module, and so
    that we can dynamically define __slots__ based on the value of the
    sub-class's attributes.
    '''
    def __new__(metacls, name, bases, attrs):
        if metacls._is_concrete(attrs):
            attrs['__slots__'] = sorted(attrs['_columns'].keys())
        return super(SqlRepresentableTypeMeta, metacls).__new__(
            metacls, name, bases, attrs)

    def __init__(cls, name, bases, attrs):
        super(cls.__metaclass__, cls).__init__(name, bases, attrs)
        if cls.__metaclass__._is_concrete(attrs):
            sqlite3.register_converter(name, cls._convert_from_sql)

    @staticmethod
    def _is_concrete(attrs):
        '''Is the class we're creating a concrete example of an
        SqlRepresentableType?
        '''
        _columns = attrs.get('_columns')
        return _columns and not isinstance(_columns, abstractproperty)


class SqlRepresentableType(object):
    __metaclass__ = SqlRepresentableTypeMeta

    @abstractproperty
    def _columns(self):
        '''`dict`-like object listing key-value pairs of column name and Python
        data type.
        '''

    __slots__ = []

    def __init__(self, *args):
        for col_name in self.__slots__:
            setattr(self, col_name, None)
        for col_name, col_data in zip(self.__slots__, args):
            setattr(self, col_name, col_data)

    def __setattr__(self, col_name, value):
        '''We make cheeky use of slots here to define limit what attributes
        make up track metadata. We intercept __setattr__ here (N.B. *not*
        __setattribute__, which is not defined on a class with __slots__) to do
        data sanitation on every value assignment.
        '''
        member_descriptor = getattr(self.__class__, col_name)
        if value is not None:
            value = self._columns[col_name](value)
        member_descriptor.__set__(self, value)

    def __conform__(self, protocol):
        if protocol is sqlite3.PrepareProtocol:
            strings = []
            for col_name in self.__slots__:
                col_data = getattr(self, col_name)
                col_data = str(col_data) if col_data is not None else ''
                strings.append(col_data)
            return ';'.join(strings)

    @classmethod
    def _convert_from_sql(cls, row):
        return cls(*[d if d else None for d in row.split(';')])


class TrackMetadata(SqlRepresentableType):
    _columns = {
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

    def __init__(self, *args):
        if len(args) == 1:
            tags = args[0]
            super(TrackMetadata, self).__init__()  # No args!
            # tags might be a gst.TagList object, which only has .keys...
            for tag_name in tags.keys():
                tag_name = tag_name.replace('-', '_')
                setattr(self, tag_name, tags[tag_name])
        else:
            super(TrackMetadata, self).__init__(*args)


class Dir(SqlRepresentableType):
    _columns = {
        'dir_path': str,
        'modified_time': float}


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


class SqlSchema(PyampBase):
    _python_to_sql_type = {
        str: 'TEXT',
        int: 'INTEGER',
        long: 'LONG',
        float: 'SINGLE'}

    def __init__(self, name, columns):
        '''
        :parameter name: The name of the database table.
        :parameter columns: Dictionary in the form:
            {<column_name>: <python data type>}
        '''
        super(SqlSchema, self).__init__()
        self.name = name
        self.types = columns
        self.attributes = {}
        self.namedtuple = namedtuple(name, sorted(self.types.keys()))

    @property
    def columns(self):
        return sorted(self.types.keys())

    @property
    def value_placholder(self):
        return ', '.join('?' * len(self.types))

    @property
    def column_placeholder(self):
        return ', '.join(self.columns)

    def create_table(self, cursor):
        self.log.debug('Creating new {} table'.format(self.name))
        cursor.execute('CREATE TABLE {}'.format(self))

    def drop_table(self, cursor):
        self.log.debug('Dropping {} table'.format(self.name))
        cursor.execute('DROP TABLE {}'.format(self.name))

    def insert_or_replace(self, cursor, data):
        query = 'INSERT OR REPLACE INTO {}({}) VALUES ({})'.format(
            self.name, self.column_placeholder, self.value_placholder)
        cursor.execute(query, self._make_data(data))

    def _make_data(self, data):
        for name, type_ in self.types.iteritems():
            if name in data:
                data[name] = self.types[name](data[name])
            else:
                data[name] = None
        return self.namedtuple(**data)

    def set_column_attributes(self, column_name, attribute):
        assert column_name in self.types
        self.attributes[column_name] = attribute

    def __iter__(self):
        for column_name in self.columns:
            yield self._get_column_schema(column_name)

    def __eq__(self, sql_schema):
        return sql_schema.types == self.types

    def _get_column_schema(self, column_name):
        type_ = self._python_to_sql_type[self.types[column_name]]
        schema = [column_name, type_]
        attrs = self.attributes.get(column_name)
        if attrs:
            schema.append(attrs)
        return schema

    def __str__(self):
        column_schemas = [' '.join(schema) for schema in self]
        return '{name}({fields})'.format(
            name=self.name, fields=', '.join(column_schemas))


def make_schema_from_existing_table(cursor, table_name):
    _sql_to_python_type = {
        v: k for k, v in SqlSchema._python_to_sql_type.iteritems()}
    cursor.execute('PRAGMA table_info({})'.format(table_name))
    result = cursor.fetchall()
    if result:
        schema_dict = {}
        for column in result:
            id_, name, type_, _, _, _ = column
            schema_dict[name] = _sql_to_python_type[type_]
        return SqlSchema(table_name, schema_dict)


class Library(PyampBase):
    _tracks_schema = SqlSchema('Tracks', {
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
        'track_number': int})
    _tracks_schema.set_column_attributes('file_path', 'UNIQUE')
    _dirs_schema = SqlSchema('Dirs', {
        'dir_path': str,
        'modified_time': float})
    _dirs_schema.set_column_attributes('dir_path', 'UNIQUE')

    def __init__(self, database_file):
        super(Library, self).__init__()
        self.database_file = os.path.expanduser(database_file)
        from gst import pbutils
        self.discoverer = pbutils.Discoverer(gst.SECOND)

    def _make_metadata(self, file_path, gst_tags):
        if gst_tags:
            metadata = {}
            for gst_tag_name in gst_tags.keys():
                tag_name = gst_tag_name.replace('-', '_')
                metadata[tag_name] = gst_tags[gst_tag_name]
            metadata['file_path'] = file_path
            file_stats = os.stat(file_path)
            metadata['modified_time'] = file_stats.st_mtime
            self.log.debug('Found file {}'.format(file_path))
            return metadata

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
        metadata = self._make_metadata(file_path, info.get_tags())
        return metadata

    def _create_table_if_required(self, cursor, sql_schema):
        existing_schema = make_schema_from_existing_table(
            cursor, sql_schema.name)
        if existing_schema:
            self.log.debug('Found existing {} table...'.format(
                sql_schema.name))
            if existing_schema == sql_schema:
                self.log.debug(
                    '{} table conforms to schema'.format(sql_schema.name))
                return
            else:
                self.log.warning(
                    '{} table does not conform to schema, dropping'.format(
                        sql_schema.name))
                sql_schema.drop_table(cursor)
        sql_schema.create_table(cursor)

    def _dir_modified(self, cursor, dir_path):
        '''
        :returns: None if the `dir_path` has not been modified since we last
        indexed it, or the modified time if it has been updated.
        '''
        cursor.execute(
            'SELECT modified_time FROM Dirs WHERE dir_path = ?', (dir_path,))
        result = cursor.fetchone()
        if result:
            stored_mtime = result[0]
        else:
            stored_mtime = None
        current_mtime = os.stat(dir_path).st_mtime
        if current_mtime != stored_mtime:
            return current_mtime

    def _update_dir_if_required(self, cursor, dir_path, file_names):
        result = 0
        modified_time = self._dir_modified(cursor, dir_path)
        if modified_time:
            track_metadata_list = self._do_discover_dir(dir_path, file_names)
            for track_metadata in track_metadata_list:
                self._tracks_schema.insert_or_replace(cursor, track_metadata)
            self._dirs_schema.insert_or_replace(
                cursor, {'dir_path': dir_path, 'modified_time': modified_time})
            result = len(track_metadata_list)
        return result

    @blocking
    @with_database_cursor
    def discover_on_path(self, cursor, dir_path):
        dir_path = os.path.expanduser(dir_path)
        self.log.info('Discovering new tracks on {}'.format(dir_path))
        self._create_table_if_required(cursor, self._dirs_schema)
        self._create_table_if_required(cursor, self._tracks_schema)
        tracks_visited = 0
        for cur_dir_path, sub_dir_names, file_names in os.walk(dir_path):
            tracks_visited += self._update_dir_if_required(
                cursor, cur_dir_path, file_names)
        self.log.info(
            'Discovery complete, {:d} tracks visited'.format(tracks_visited))

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
