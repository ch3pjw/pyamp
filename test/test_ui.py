from unittest import TestCase

from pyamp.ui import (
    clamp, weighted_round_robin, Fill, HorizontalContainer, ProgressBar)


class TestHelpers(TestCase):
    def test_clamp_values(self):
        self.assertEqual(clamp(1, 2, 3), 2)
        self.assertEqual(clamp(4, 3, 5), 4)
        self.assertEqual(clamp(10, 8, 9), 9)

    def test_clamp_unbounded(self):
        self.assertEqual(clamp(42), 42)
        self.assertEqual(clamp(-42), -42)
        self.assertEqual(clamp(121, min_=13), 121)
        self.assertEqual(clamp(-121, min_=13), 13)
        self.assertEqual(clamp(121, max_=13), 13)
        self.assertEqual(clamp(-121, max_=13), -121)

    def test_weighted_round_robin(self):
        test_data = [('a', 3), ('b', 1), ('c', 2)]
        result = [
            val for val, _ in zip(weighted_round_robin(test_data), xrange(12))]
        expected = ['a', 'c', 'b', 'a', 'c', 'a'] * 2
        self.assertEqual(result, expected)


class TestUIElements(TestCase):
    def test_fill(self):
        fill = Fill()
        self.assertEqual(fill.draw(10, 0), '')
        self.assertEqual(fill.draw(10, 1), '.' * 10)
        self.assertEqual(fill.draw(2, 2), '..\n..')
        self.assertEqual(fill.draw(0, 10), '\n' * 9)
        fill = Fill('o')
        self.assertEqual(fill.draw(1, 1), 'o')

    def test_horizontal_container_basic(self):
        fill1 = Fill('1')
        horizontal_container = HorizontalContainer([fill1])
        self.assertEqual(horizontal_container.draw(3, 1), '111')
        fill2 = Fill('2')
        horizontal_container.add_element(fill2)
        self.assertEqual(horizontal_container.draw(5, 1), '11 22')
        fill3 = Fill('3')
        horizontal_container.add_element(fill3, weight=2)
        self.assertEqual(horizontal_container.draw(10, 1), '11 22 3333')
        horizontal_container.remove_element(fill2)
        self.assertEqual(horizontal_container.draw(4, 1), '1 33')

    def test_horizontal_container_constraints(self):
        fill1 = Fill('1')
        fill2 = Fill('2')
        horizontal_container = HorizontalContainer([fill1, fill2])
        fill4 = Fill('4')
        fill4.max_width = 2
        horizontal_container.add_element(fill4)
        self.assertEqual(horizontal_container.draw(10, 1), '111 222 44')
        self.assertEqual(horizontal_container.draw(5, 1), '1 2 4')
        fill4.max_width = None
        fill4.min_width = 3
        self.assertEqual(horizontal_container.draw(7, 1), '1 2 444')
        self.assertEqual(horizontal_container.draw(14, 1), '1111 2222 4444')
        fill4.max_width = fill4.min_width = 5
        self.assertEqual(horizontal_container.draw(9, 1), '1 2 44444')
        self.assertEqual(
            horizontal_container.draw(19, 1), '111111 222222 44444')
        horizontal_container.remove_element(fill2)
        self.assertEqual(horizontal_container.draw(7, 1), '1 44444')
        self.assertEqual(horizontal_container.draw(14, 1), '11111111 44444')
        fill1.min_width = 3
        self.assertEqual(horizontal_container.draw(9, 1), '111 44444')

    def test_horizontal_container_max_width(self):
        fill1 = Fill('1')
        fill1.max_width = 30
        fill2 = Fill('2')
        horizontal_container = HorizontalContainer([fill1, fill2])
        self.assertIsNone(horizontal_container.max_width)
        fill2.max_width = 11
        self.assertEqual(horizontal_container.max_width, 42)

    def test_horizontal_container_min_width(self):
        fill1 = Fill('1')
        fill1.min_width = 7
        fill2 = Fill('2')
        horizontal_container = HorizontalContainer([fill1, fill2])
        self.assertEqual(horizontal_container.min_width, 8)
        fill2.min_width = 34
        self.assertEqual(horizontal_container.min_width, 42)

    def test_progress_bar(self):
        progress_bar = ProgressBar()
        self.assertEqual(progress_bar.draw(3, 1), '[ ]')
        progress_bar.fraction = 0.5
        self.assertEqual(progress_bar.draw(10, 1), '[====    ]')
        progress_bar.fraction = 0.45
        self.assertEqual(progress_bar.draw(9, 1), '[===-   ]')
        progress_bar.fraction = 1
        self.assertEqual(progress_bar.draw(9, 1), '[=======]')
