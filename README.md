pyamp
=====

`pyamp` is a command-line media player written in Python and uses Gstreamer as
the media backend. It began life as a holiday project for Paul Weaver, and the
name is either an homage to Winamp of old, or, more likely an acronym for
"Please, yet another media player?!".

To try it out, you'll need to install python-gstreamer and sqlite from your
repos, and then you can `pip install` it. There's not a huge amount to go on as
yet, but current features are:

* Full-screen terminal interface to really get you in the zone
* Progress bar, time and track title display
* Seeking, volume controls, fade-out on quit
* Track indexing and searching
* Very customisable via YAML config

You can currently run it on the command line like:
```
pyamp /path/to/media_file
```
or, for some more fun, try
```
pyamp <partial artist/album/track name>
```

Enjoy!
