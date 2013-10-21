#! /usr/bin/env python
import sys
import os
import time
import pygst
pygst.require('0.10')
import gst


class Player(object):
    def __init__(self):
        self.gst_player = gst.element_factory_make('playbin2', 'player')

    def handle_messages(self):
        bus = self.gst_player.get_bus()
        while True:
            message = bus.poll(gst.MESSAGE_EOS, timeout=0.1)
            if message:
                self.stop()
                raise StopIteration('Finished playing!')
            else:
                break

    def set_file(self, filepath):
        filepath = os.path.abspath(filepath)
        print 'setting filepath', filepath
        self.gst_player.set_property('uri', 'file://{}'.format(filepath))

    def play(self):
        print 'playing'
        self.gst_player.set_state(gst.STATE_PLAYING)

    def stop(self):
        self.gst_player.set_state(gst.STATE_NULL)


if __name__ == '__main__':
    p = Player()
    p.set_file(sys.argv[1])
    p.play()
    try:
        while p.gst_player.get_state()[1] == gst.STATE_PLAYING:
            p.handle_messages()
            time.sleep(0.5)
    except KeyboardInterrupt:
        print 'Stopping player gracefully'
        p.stop()
    except StopIteration:
        print 'Track finished'
