========
Examples
========

.. toctree::
   :caption: Table of Contents
   :maxdepth: 2

Chirp Examples
--------------


Lilypond Sheet Music Examples
-----------------------------

Lilypond Song to PDF
++++++++++++++++++++

In this example a MIDI song is read in and output to a multi-page PDF document:

.. literalinclude:: ../examples/lilypondExample.py
    :language: python

Lilypond Measures to PNG
++++++++++++++++++++++++

In this example a MIDI song is read, and a snippet of measures is converted to a PNG image;

.. literalinclude:: ../examples/lilypondClipExample.py
    :language: python

Metric Modulation Examples
--------------------------

Fix too-short note durations
++++++++++++++++++++++++++++

tools/BWV_799.mid is a three-part Bach invention.  We can convert it to a C128 BASIC program as follows:

::

    python tools\midiToC128Basic.py test\BWV_test.mid test\BWV_test.prg -t prg

This should sound fine to anyone not familiar with the piece.  However, C128 BASIC PLAY command can perform 16th notes, but not finer durations (e.g., 32nd notes, etc).  And BWV 799 contains 32nd notes towards the end.

A solution is to use metric modulation to double all the note durations, as well as doubling the BPM so that the perceived tempo remains the same.  That way, the smallest note duration is a 16th note, which PLAY commands can play.

This command will change the 3/8 time signature piece into a 3/4 time signature, along with the changes described above:

::

    python tools\midiTransform.py -m 2/1 -q 16 -j 3/4 test\BWV_799.mid test\BWV_test.mid

Now when BWV_test is converted to C128 BASIC, all the notes are present.

Eliminate triplets
++++++++++++++++++

