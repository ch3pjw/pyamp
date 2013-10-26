import os

from twisted.internet import threads, defer

from base import PyampBase
from player import gst


class Library(PyampBase):
    def __init__(self):
        super(Library, self).__init__()
        from gst import pbutils
        self.discoverer = pbutils.Discoverer(gst.SECOND)

    def _do_discover(self, file_path):
        info = self.discoverer.discover_uri('file://' + file_path)
        tags = info.get_tags()
        tags = {tag_name: tags[tag_name] for tag_name in tags.keys()}
        self.log.debug('Found file {}: {}'.format(file_path, tags))
        return tags

    def discover_on_path(self, dir_path):
        dir_path = os.path.expanduser(dir_path)
        def on_error(self, failure):
            self.log.exception(failure.value)
        deferreds = []
        for cur_dir_path, sub_dir_names, file_names in os.walk(dir_path):
            for file_name in file_names:
                d = threads.deferToThread(
                    self._do_discover, os.path.join(dir_path, file_name))
                d.addErrback(on_error)
                deferreds.append(d)
        return defer.gatherResults(deferreds, consumeErrors=True)
