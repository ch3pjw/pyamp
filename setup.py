import os
import sys
from setuptools import setup

try:
    print('Testing gstreamer python support...')
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
except ImportError:
    sys.exit("Cannot install pyamp, no gstreamer python bindings present")

print('Found gstreamer python bindings, gstreamer version is {}'.format(
    '.'.join(str(n) for n in Gst.version())))

__version__ = None
# Populate __version__ using _pyamp._version module, without importing
this_dir_path = os.path.dirname(__file__)
version_module_path = os.path.join(this_dir_path, 'pyamp', '_version.py')
exec(open(version_module_path).read())

setup(
    name='pyamp',
    version=__version__,
    install_requires=[
        'asyncio',
        'jcn',
        'enum34',
        'pyyaml'],
    packages=[
        'pyamp'],
    package_data={
        'pyamp': ['default.config']},
    entry_points={
        'console_scripts': ['pyamp = pyamp.pyamp:main']},
    extras_require={
        'development': [
            'pep8',
            'mock',
            'nose',
            'nose-progressive',
            'coverage']}
)
