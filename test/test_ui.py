from unittest import TestCase

from pyamp.ui import clamp, Fill, HorizontalContainer


class TestClamp(TestCase):
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


class TestUIElements(TestCase):
    def test_fill(self):
        fill = Fill()
        self.assertEqual(fill.draw(10, 0), '')
        self.assertEqual(fill.draw(10, 1), '.' * 10)
        self.assertEqual(fill.draw(2, 2), '..\n..')
        self.assertEqual(fill.draw(0, 10), '\n' * 9)
        fill = Fill('o')
        self.assertEqual(fill.draw(1, 1), 'o')

    def test_horizontal_container(self):
        fill1 = Fill('1')
        horizontal_container = HorizontalContainer([fill1])
        self.assertEqual(horizontal_container.draw(3, 1), '111')
        fill2 = Fill('2')
        horizontal_container.add_element(fill2)
        self.assertEqual(horizontal_container.draw(5, 1), '11 22')
        fill3 = Fill('3')
        horizontal_container.add_element(fill3, weight=2)
        self.assertEqual(horizontal_container.draw(10, 1), '11 22 3333')
        horizontal_container.remove_element(fill3)
        self.assertEqual(horizontal_container.draw(3, 1), '1 2')
        fill4 = Fill('4')
        fill4.max_width = 2
        horizontal_container.add_element(fill4)
        self.assertEqual(horizontal_container.draw(10, 1), '111 222 44')
        self.assertEqual(horizontal_container.draw(5, 1), '1 2 4')
        fill4.max_width = None
        fill4.min_width = 3
        self.assertEqual(horizontal_container.draw(7, 1), '1 2 444')
        self.assertEqual(horizontal_container.draw(14, 1), '1111 2222 4444')
