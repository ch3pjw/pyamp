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
            data = self._data[name]
        except KeyError as e:
            raise AttributeError(e.message)
        if isinstance(data, collections.Mapping):
            return self.__class__(data)
        else:
            return data

    def __dir__(self):
        return sorted(set(dir(self.__class__) + self._data.keys()))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._data == other._data
        else:
            return self._data == other

    def __iter__(self):
        cls_attrs = dir(self.__class__)
        for key in self._data:
            if key not in cls_attrs:
                yield key, getattr(self, key)

    def update(self, new):
        '''Recursively update current data with data from another UserConfig
        instance.
        '''
        self._update(self._data, new._data)

    def _update(self, existing, new):
        for key, value in new.iteritems():
            if isinstance(value, collections.Mapping):
                existing[key] = self._update(existing.get(key, {}), value)
            elif value is None:
                # If the new data doesn't provide any information for a key
                # that we had previously, then we don't want to nuke our
                # existing data.
                pass
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
