from unittest import TestCase

import yaml
from copy import deepcopy

from pyamp.config import UserConfig


class TestUserConfig(TestCase):
    def setUp(self):
        self.default_config_data = {
            'blasters': False,
            'engines': [
                {'1': 'good'},
                {'2': 'good'},
                {'3': 'good'},
                {'4': 'good'},
            ],
            'shields': {
                'front': 'good',
                'back': 'middling',
            },
            'pilot': 'Luke',
            'clean_trousers': 1,
            'update': "should never be accessible, because it's a method name"
        }
        self.latest_config_data = {
            'blasters': True,
            'engines': [
                {'1': 'medium'},
                {'2': 'flamy'},
                {'3': 'good'},
                # Arg! We lost 4 captain!
            ],
            'shields': {
                'front': 'knackered',
                'sides': 'yeah, we needed more',
            },
            'clean_trousers': None
        }

    def test_attribute_lookup(self):
        user_config = UserConfig(self.default_config_data)
        self.assertFalse(user_config.blasters)
        self.assertEqual(
            user_config.engines,
            [{'1': 'good'}, {'2': 'good'}, {'3': 'good'}, {'4': 'good'}])
        self.assertIsInstance(user_config.shields, UserConfig)
        self.assertEqual(user_config.shields.front, 'good')
        self.assertEqual(user_config.shields.back, 'middling')
        self.assertEqual(user_config.pilot, 'Luke')
        self.assertTrue(callable(user_config.update))
        self.assertRaises(AttributeError, lambda: user_config.ship_type)
        try:
            user_config.loafers
        except AttributeError as e:
            self.assertIn('loafers', e.message)

    def test_dir(self):
        user_config = UserConfig(self.default_config_data)
        self.assertEqual(
            dir(user_config),
            sorted(dir(UserConfig) + [
                'blasters', 'clean_trousers', 'engines', 'pilot', 'shields']))

    def test_eq(self):
        config1 = UserConfig(self.default_config_data)
        copied_data = deepcopy(self.default_config_data)
        config2 = UserConfig(copied_data)
        self.assertEqual(config1, config2)
        self.assertEqual(config1, copied_data)
        config3 = UserConfig(self.latest_config_data)
        self.assertNotEqual(config1, config3)
        self.assertNotEqual(config1, self.latest_config_data)

    def test_str(self):
        user_config = UserConfig(self.default_config_data)
        string = str(user_config)
        restored_data = yaml.load(string)
        self.assertEqual(restored_data, self.default_config_data)

    def test_iter(self):
        user_config = UserConfig(self.default_config_data)
        user_config_output = [tup for tup in user_config]
        self.assertItemsEqual(user_config_output, [
            (k, v) for k, v in self.default_config_data.iteritems() if
            k != 'update'])
        self.assertIsInstance(dict(user_config_output)['shields'], UserConfig)

    def test_update(self):
        default_config = UserConfig(self.default_config_data)
        latest_config_data = UserConfig(self.latest_config_data)
        default_config.update(latest_config_data)
        self.assertTrue(default_config.blasters)
        self.assertEqual(
            default_config.engines,
            self.latest_config_data['engines'])
        self.assertEqual(
            default_config.shields, {
                'front': 'knackered',
                'sides': 'yeah, we needed more',
                'back': 'middling'})
        self.assertEqual(default_config.pilot, 'Luke')
        self.assertEqual(default_config.clean_trousers, 1)
