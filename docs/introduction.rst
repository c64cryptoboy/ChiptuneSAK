=======================================
Introduction
=======================================

.. contents::

ChiptuneSAK
-----------

**C**\ hiptune **S**\ wiss **A**\ rmy **K**\ nife is a Python music processing toolset for note data.  It can transform music originating from (or being importing into) a constrained playback environment.  The goal is to take some of the tedium out of processing chiptune music.

Typical Workflow:

#. Import note data from a music format

#. Data converted into Chirp (**Ch**\ iptuneSAK **I**\ ntermediate **R**\ e\ **P**\ resentation), which can be processed and transformed in many ways

#. Export note data to a (potentially different) music format

Initial focus is Commodore music, but can be extended to other “chiptune platforms”


What can I do with ChiptuneSAK?
+++++++++++++++++++++++++++++++

Our `CRX2020 <http://www.crxevent.com>`_ announcement `slides <https://github.com/c64cryptoboy/ChiptuneSAK/tree/master/docs/crx2020PresentationSlides.pdf>`_ gives many examples of the kinds of things you can do with these tools, including:

* Import music from C64 SIDs and turn it into sheet music

*  Perform transformations on music note data, including transposition, tempo changes, separation of chords, trimming, time shifting, quantizing, and metric modulation.

*  Convert music from MS-DOS games into C64 SIDs

*  Automatically generate C128 BASIC music programs


What do I need to run ChiptuneSAK?
++++++++++++++++++++++++++++++++++

ChiptuneSAK requires a computer with a Python interpreter (v3.8 or higher).


What are some limitations of ChiptuneSAK?
+++++++++++++++++++++++++++++++++++++++++

ChiptuneSAK is primarily concerned with processing note *content* as opposed to musical *timbre*.  It is not a tool for:

*  Editing and tweaking instruments or particular sounds

*  Processing waveform music, such as MP3 or WAV files

*  Processing of sound effects


How mature is ChiptuneSAK?
++++++++++++++++++++++++++

ChiptunesSAK should be considered to be at an Alpha level of maturity.  For instance, the SID Importer has been tested on tens of SIDs, but needs to scripted to run against all of HVSC to improve robustness and account for important edge cases.  This will happen as we have time.  We are also in the progress of making ChiptuneSAK a PyPy package.
