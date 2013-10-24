import os
import shutil
import collections
import yaml


class UserConfig(object):
    '''Represents a nested data structure in a conventient, dotted-lookup
    kinda way.
    '''
    def __init__(self, data):
        self._data = data

    def __getattr__(self, name):
        try:
            return self.__class__(self._data[name])
        except KeyError as e:
            raise AttributeError(e.message)

    def __dir__(self):
        return self._data.keys()

    def update(self, new):
        '''Recursively update current data with data from another UserConfig
        instance.
        '''
        self._update(self._data, new._data)

    def _update(self, existing, new):
        for key, value in new.iteritems():
            if isinstance(value, collections.Mapping):
                existing[key] = self._update(existing.get(key, {}), value)
            else:
                existing[key] = new[key]
        return existing

    def __str__(self):
        return yaml.dump(self._data, default_flow_style=False)


def load_config():
    path_to_here = os.path.dirname(__file__)
    default_config_file_path = os.path.join(path_to_here, 'default.pyamp')
    user_config_file_path = os.path.join(os.path.expanduser('~'), '.pyamp')
    if not os.path.exists(user_config_file_path):
        shutil.copy2(default_config_file_path, user_config_file_path)
    with open(default_config_file_path) as fp:
        default_config = UserConfig(yaml.load(fp))
    with open(user_config_file_path) as fp:
        user_config = UserConfig(yaml.load(fp))
    default_config.update(user_config)
    return default_config
