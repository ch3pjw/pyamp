from unittest import TestCase
from mock import patch

import sqlite3

from pyamp.library import SqlSchema, SqlRepresentableType, TrackMetadata


class TestSqlRepresentableTypeMeta(TestCase):
    def test_abc(self):
        # Can't instantiate abstract base class
        self.assertRaises(TypeError, SqlRepresentableType)
        class MySqlReprType(SqlRepresentableType):
            _columns = {'foo': str}
        self.assertIsInstance(MySqlReprType(), MySqlReprType)

    @patch('pyamp.library.sqlite3.register_converter', autospec=True)
    def test_class_registered(self, register_converter_mock):
        class StillAbstract(SqlRepresentableType):
            pass
        self.assertEqual(register_converter_mock.call_count, 0)
        class Concrete(SqlRepresentableType):
            _columns = {'bar': int}
        register_converter_mock.assert_called_once_with(
            'Concrete', Concrete._convert_from_sql)


class TestTrackMetadata(TestCase):
    def test_get_and_setattr(self):
        metadata = TrackMetadata()
        metadata.title = 1
        self.assertEqual(metadata.title, '1')
        self.assertIsInstance(metadata.title, str)
        metadata.modified_time = 1.0
        self.assertEqual(metadata.modified_time, 1.0)
        self.assertIsInstance(metadata.modified_time, float)
        metadata = TrackMetadata({'artist': 'Paul'})
        self.assertIsNone(metadata.title)
        self.assertEqual(metadata.artist, 'Paul')

    def test_conform_and_convert(self):
        metadata = TrackMetadata({'artist': 'Paul', 'bitrate': 32000})
        sql = ';Paul;;32000;;;;;;;;;;'
        self.assertIsNone(metadata.__conform__('random_protocol'))
        self.assertEqual(metadata.__conform__(sqlite3.PrepareProtocol), sql)
        metadata = TrackMetadata._convert_from_sql(sql)
        self.assertIsInstance(metadata, TrackMetadata)
        self.assertEqual(metadata.artist, 'Paul')
        self.assertEqual(metadata.bitrate, 32000)
        self.assertIsNone(metadata.genre)


class TestSqlSchema(TestCase):
    def setUp(self):
        self.columns = {'foo': str, 'bar': int, 'baz': long, 'floaty': float}
        self.schema = SqlSchema('Test', self.columns)

    def test_sql_schema_str(self):
        self.schema.set_column_attributes('bar', 'UNIQUE')
        self.assertEqual(
            str(self.schema),
            'Test(bar INTEGER UNIQUE, baz LONG, floaty SINGLE, foo TEXT)')

    def test_sql_schema_eq(self):
        new_schema = SqlSchema('Wrong', {'deffo_not': str, 'equal': str})
        self.assertNotEqual(new_schema, self.schema)
        new_schema = SqlSchema('Right', self.columns)
        self.assertEqual(new_schema, self.schema)
        self.schema.set_column_attributes('bar', 'UNIQUE')
        self.assertEqual(new_schema, self.schema)
