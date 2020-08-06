=======================================
Introduction
=======================================

.. contents::

ChiptuneSAK
-----------

**C**\ hiptune **S**\ wiss **A**\ rmy **K**\ nife is a Python toolset built for processing music for constrained (i.e. chiptunes) environments.

The package includes a Python library, chiptunesak, examples, and supporting scripts.

Who is ChiptuneSAK for?
+++++++++++++++++++++++

ChiptuneSAK was built for chiptunes enthusiasts who prefer to work in a sheet-music-like environment, with music represented as notes in measures. It is designed to enable conversion from chiptunes sources to the "sheet music" model, transformations of the music while in that environment, and conversion back to chiptunes formats. With these capabilities, it is possible to parse, print, and modify a wide range of chiptunes music.

What can I do with ChiptuneSAK?
+++++++++++++++++++++++++++++++

ChiptuneSAK allows you to convert music between different chiptunes formats, such as MIDI, GoatTracker, and C128 BASIC.

It is not designed to convert exact music, including instruments and sound effects.  Rather, the intent is to allow you to move musical *content* (i.e. notes) between formats and representations.  For example, with ChiptuneSAK you can:

*  Convert a song written for a DOS game into a C64 SID and print sheet music.

*  Convert a C64 SID to MIDI and print it as sheet music.

*  Convert classical music (e.g. Bach) to C64 SIDs.

*  Perform many operations on chiptunes music:

   * Transposition
   * Tempo changes
   * "Explode" chords into multiple tracks
   * Edit (trim, move, quantize, metric modulation)
   * Convert to sheet music

What do I need to run ChiptuneSAK?
++++++++++++++++++++++++++++++++++

ChiptuneSAK requires a computer with a Python interpreter, v 3.8 or higher.  It will work on any operating system that has a qualifying Python interpreter.

What are some limitations of ChiptuneSAK?
+++++++++++++++++++++++++++++++++++++++++

ChiptuneSAK is primarily concerned with musical *content* as opposed to *sound quality*.  What it does, it does well.  But there are a number of things it does *not* do:

*  It is not particularly good at dealing with percussion.
*  It does not provide many tools for editing and tweaking instruments or particular sounds.
*  It does not work with waveform music, such as MP3 or WAV files.
*  It is not intended for conversion or processing of sound effects.

