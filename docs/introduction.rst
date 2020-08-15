=======================================
Introduction
=======================================

.. contents::

ChiptuneSAK
-----------

**C**\ hiptune **S**\ wiss **A**\ rmy **K**\ nife is a Python music processing toolset for note data.  It can transform music originating from (or being imported into) a constrained playback environment.  The goal of ChiptuneSAK is to take some of the tedium out of processing chiptune music.

A typical ChiptuneSAk workflow would consist of these steps:

#. Import note data from a music format

#. Convert data into Chirp (**Ch**\ iptuneSAK **I**\ ntermediate **R**\ e\ **P**\ resentation), which can be processed and transformed in many ways

#. Manipulate or transform the note data

#. Export note data to a (potentially different) music format

The initial focus of ChiptuneSAK is on Commodore music, but the tools can be extended to other “chiptune” platforms.


What can I do with ChiptuneSAK?
+++++++++++++++++++++++++++++++

Our `CRX2020 <http://www.crxevent.com>`_ announcement `slides <https://github.com/c64cryptoboy/ChiptuneSAK/tree/master/docs/crx2020PresentationSlides.pdf>`_ give several examples of the kinds of things you can do with these tools, including:

* Import music from C64 SIDs and turn it into sheet music

*  Perform transformations on music note data, including transposition, tempo changes, separation of chords, trimming, time shifting, quantizing, and metric modulation.

*  Convert music from MS-DOS games into C64 SIDs

*  Automatically generate C128 BASIC music programs


What do I need to run ChiptuneSAK?
++++++++++++++++++++++++++++++++++

ChiptuneSAK requires a computer with a Python interpreter (v3.8 or higher).  It will run on Windows, MacOS, and linux.


What are some limitations of ChiptuneSAK?
+++++++++++++++++++++++++++++++++++++++++

ChiptuneSAK is primarily concerned with processing note *content* as opposed to musical *timbre*.  It is *not* a tool for:

*  Editing and tweaking instruments or particular sounds

*  Processing waveform music, such as MP3 or WAV files

*  Processing of sound effects


How mature is ChiptuneSAK?
++++++++++++++++++++++++++

ChiptunesSAK should be considered to be at an **alpha** level of maturity.  For instance, the SID Importer has been tested on
tens of SIDs, but has not yet been scripted to run all of `HVSC <https://www.hvsc.c64.org/>`_, a process that will improve
robustness and account for important edge cases.  This process should occur over the next few months.

ChiptuneSAK will eventually released as a PyPI package, but for the moment is it only available as a Github repository.
