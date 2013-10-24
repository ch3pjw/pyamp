import os
import shutil
import collections
import yaml


def update(existing, new):
    for key, value in new.iteritems():
        if isinstance(value, collections.Mapping):
            existing[key] = update(existing.get(key, {}), value)
        else:
            existing[key] = new[key]
    return existing


def load_config():
    path_to_here = os.path.dirname(__file__)
    default_config_file_path = os.path.join(path_to_here, 'default.pyamp')
    user_config_file_path = os.path.join(os.path.expanduser('~'), '.pyamp')
    if not os.path.exists(user_config_file_path):
        shutil.copy2(default_config_file_path, user_config_file_path)
    with open(default_config_file_path) as fp:
        default_config = yaml.load(fp)
    with open(user_config_file_path) as fp:
        user_config = yaml.load(fp)
    print default_config
    print user_config
    update(default_config, user_config)
    print default_config
