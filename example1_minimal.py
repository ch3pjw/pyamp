import sys
import time
import pygst
pygst.require('0.10')
import gst


def on_message(bus, message):
    print 'bus: {}, message: {}'.format(bus, message)

my_player = gst.element_factory_make('playbin2', 'player')
bus = my_player.get_bus()
bus.add_signal_watch()
bus.connect('message', on_message)

filepath = sys.argv[1]
my_player.set_property('uri', 'file://{}'.format(filepath))
my_player.set_state(gst.STATE_PLAYING)

print 'sleeping 20'
time.sleep(20)

my_player.set_state(gst.STATE_NULL)
