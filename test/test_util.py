from unittest import TestCase

from pyamp.util import clamp, moving_window


class TestUtil(TestCase):
    def test_clamp_values(self):
        self.assertEqual(clamp(1, 2, 3), 2)
        self.assertEqual(clamp(4, 3, 5), 4)
        self.assertEqual(clamp(10, 8, 9), 9)
        self.assertEqual(clamp(-1, 0, 1), 0)
        self.assertEqual(clamp(1, -1, 0), 0)

    def test_clamp_unbounded(self):
        self.assertEqual(clamp(42), 42)
        self.assertEqual(clamp(-42), -42)
        self.assertEqual(clamp(121, min_=13), 121)
        self.assertEqual(clamp(-121, min_=13), 13)
        self.assertEqual(clamp(121, max_=13), 13)
        self.assertEqual(clamp(-121, max_=13), -121)

    def test_moving_window(self):
        expected = [(1, 2), (2, 3), (3, 4), (4, 5)]
        for actual, expected in zip(moving_window([1, 2, 3, 4, 5]), expected):
            self.assertEqual(actual, expected)
