*********************
Sheet Music: Lilypond
*********************

.. contents::

Lilypond Sheet Music Markup
###########################


`Lilypond <http://lilypond.org/index.html>`_ is a TeX-like markup language for sheet music.  It does an excellent job of generating professional-quality music engraving.

ChiptuneSAK and Lilypond
########################

ChiptuneSAK can generate Lilypond markup for the very useful subset of cases with a limited number of voices and no in-voice polyphony.

The LilyPond exporter is implemented in the :ref:`Lilypond Class`.

To use Lilypond with ChiptuneSAK, you will need to obtain and install Lilypond for your platform. The ChiptuneSAK Lilypond generator requires the MChirp intermediate format, in which the music has been interpreted as notes in measures.

The ChiptuneSAK :ref:`Lilypond Class` can export sheet music in two ways:  either as the entire piece of music or
as a clip from a single voice.  The former is usually converted to a pdf, while the latter is usually
a png file, but those options are part of the lilypond command line and not required by ChiptuneSAK.

Because the lilypond format is a text format, the output from ChiptuneSAK can easily be edited by hand with a
text editor.  To facilitate such editing, ChiptuneSAK annotates the lilypond file with measure numbers and other
hints.

Lilypond Examples
#################

See the following examples for use of Lilypond with ChiptuneSAK.

*  :ref:`Lilypond Song to PDF` shows conversion of a captured DOS midi file into pdf sheet music.

*  :ref:`Lilypond Measures to PNG` shows conversion of a snippet of music into a png image file.

