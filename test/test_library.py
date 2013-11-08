from unittest import TestCase
from mock import patch

from pyamp.library import SqlRepresentableType, TrackMetadata, Dir, Library


class TestSqlRepresentableType(TestCase):
    def setUp(self):
        class TestSqlType(SqlRepresentableType):
            _col_types = {
                'stringy': str, 'floaty': float, 'looong': int, 'inty': int}
            _col_attrs = {'stringy': 'UNIQUE'}
        self.cls = TestSqlType
        self.schema_string = (
            'floaty SINGLE, inty LONG, looong LONG, stringy TEXT UNIQUE')
        self.schema_data = [
            (0, 'floaty', 'SINGLE', 0, None, 0),
            (1, 'inty', 'LONG', 0, None, 0),
            (2, 'looong', 'LONG', 0, None, 0),
            (3, 'stringy', 'TEXT', 0, None, 0)]

    def test_construction(self):
        attr_names = self.cls._col_attrs.keys()
        plain = self.cls()
        for name in attr_names:
            self.assertIsNone(getattr(plain, name))
        argy = self.cls(1.0, 2, 3, '4')
        self.assertEqual(argy.floaty, 1.0)
        self.assertEqual(argy.inty, 2)
        self.assertEqual(argy.looong, 3)
        self.assertEqual(argy.stringy, '4')
        missing_argy = self.cls(1.0)
        self.assertEqual(missing_argy.floaty, 1.0)
        for name in ('inty', 'looong', 'stringy'):
            self.assertIsNone(getattr(missing_argy, name))
        data = {'looong': 40, 'floaty': 30.0, 'inty': 20, 'stringy': '10'}
        dicty = self.cls(data)
        for k, v in data.items():
            self.assertEqual(getattr(dicty, k), v)

    def test_get_col_names(self):
        names = ['floaty', 'inty', 'looong', 'stringy']
        self.assertEqual(self.cls._get_col_names(), names)
        instance = self.cls()
        self.assertEqual(instance._get_col_names(), names)

    def test_len(self):
        instance = self.cls()
        self.assertEqual(len(instance), 4)

    def test_getitem(self):
        def check():
            for i, expected_type in enumerate((float, int, int, str)):
                self.assertEqual(instance[i], expected_type(i))
        instance = self.cls(0, 1, 2, 3)
        check()
        instance = self.cls()
        instance.inty = 1
        instance.floaty = 0.0
        instance.stringy = '3'
        instance.looong = 2
        check()

    def test_setattr(self):
        for instance in (self.cls(), self.cls(9, 9, 9, 9)):
            for name, type_ in self.cls._col_types.items():
                setattr(instance, name, 1)
                self.assertIsInstance(getattr(instance, name), type_)
                self.assertEqual(getattr(instance, name), type_(1))
                setattr(instance, name, None)
                self.assertIsNone(getattr(instance, name))
        self.assertRaises(AttributeError, lambda: setattr(instance, 'bob', 15))

    def test_get_schema(self):
        self.assertEqual(self.cls._get_schema(), self.schema_string)
        instance = self.cls()
        self.assertEqual(instance._get_schema(), self.schema_string)

    def test_iter_schema(self):
        for result, expected in zip(self.cls._iter_schema(), self.schema_data):
            self.assertEqual(result, expected)
        for result, expected in zip(
                self.cls()._iter_schema(), self.schema_data):
            self.assertEqual(result, expected)

    @patch('pyamp.library.sqlite3.Cursor', autospec=True)
    def test_create_table(self, mock_cursor):
        self.cls.create_table(mock_cursor)
        mock_cursor.execute.assert_called_once_with(
            'CREATE TABLE TestSqlType({})'.format(self.schema_string))

    @patch('pyamp.library.sqlite3.Cursor', autospec=True)
    # FIXME: don't seem to autospec classmethods and them be callable :-(
    @patch('pyamp.library.SqlRepresentableType.create_table')
    @patch('pyamp.library.SqlRepresentableType.drop_table')
    def test_create_table_if_required(
            self, mock_drop_table, mock_create_table, mock_cursor):
        mock_cursor.fetchall.return_value = self.schema_data
        self.cls.create_table_if_required(mock_cursor)
        mock_cursor.execute.assert_called_once_with(
            'PRAGMA table_info(TestSqlType)')
        self.assertEqual(mock_create_table.call_count, 0)
        self.assertEqual(mock_drop_table.call_count, 0)

        self.schema_data[2] = (2, 'interloper', 'INT', 0, None, 0)
        self.cls.create_table_if_required(mock_cursor)
        self.assertEqual(mock_create_table.call_count, 1)
        self.assertEqual(mock_drop_table.call_count, 1)

        self.schema_data[2] = (2, 'looong', 'TEXT', 0, None, 0)
        self.cls.create_table_if_required(mock_cursor)
        self.assertEqual(mock_create_table.call_count, 2)
        self.assertEqual(mock_drop_table.call_count, 2)

        del self.schema_data[2]
        self.cls.create_table_if_required(mock_cursor)
        self.assertEqual(mock_create_table.call_count, 3)
        self.assertEqual(mock_drop_table.call_count, 3)

        mock_cursor.fetchall.return_value = None
        self.cls.create_table_if_required(mock_cursor)
        self.assertEqual(mock_create_table.call_count, 4)
        self.assertEqual(mock_drop_table.call_count, 3)

    @patch('pyamp.library.sqlite3.Cursor', autospec=True)
    def test_drop_table(self, mock_cursor):
        self.cls.drop_table(mock_cursor)
        mock_cursor.execute.assert_called_once_with(
            'DROP TABLE TestSqlType')

    @patch('pyamp.library.sqlite3.Cursor', autospec=True)
    def test_insert_or_replace(self, mock_cursor):
        instance = self.cls(7, 42, 121, 1024)
        instance.insert_or_replace(mock_cursor)
        mock_cursor.execute.assert_called_once_with(
            'INSERT OR REPLACE INTO TestSqlType(floaty, inty, looong, stringy'
            ') VALUES (?, ?, ?, ?)',
            instance)


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


class TestLibrary(TestCase):
    pass
