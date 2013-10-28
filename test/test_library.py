from unittest import TestCase

from pyamp.library import SqlSchema


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
