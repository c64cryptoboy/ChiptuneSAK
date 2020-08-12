*********************
Sheet Music: Lilypond
*********************

.. contents::

Lilypond Sheet Music Markup
###########################


`Lilypond <http://lilypond.org/index.html>`_ is a TeX-like markup language for sheet music.  It does an excellent job of generating professional-quality music engraving.

ChiptuneSAK and Lilypond
########################

ChiptuneSAK can generate Lilypond markup for a very useful subset of cases with a limited number of voices and no in-voice polyphony.

The LilyPond exporter is implemented in the :ref:`Lilypond Class`.

To use Lilypond with ChiptuneSAK, you will need to obtain and install Lilypond for your platform. The ChiptuneSAK Lilypond generator requires the MChirp intermediate format, in which the music has been interpreted as notes in measures.

Sheet Music Examples
####################

Example 1:  Midi to Lilypond Sheet Music clip
*********************************************

You'll need to write your own script to perform this workflow.  In your code, read in the midi file, convert it to measures, and then select the measures you want to turn into a clip. Then call *chiptunesak.lilypond.export_clip_to_lilypond()* to create the Lilypond source for the clip.

::

    song = midi.MIDI().to_chirp('bach_invention_4.mid')
    song.quantize_from_note_name('16')  # Quantize to sixteenth notes
    song.remove_polyphony()
    m_song = song.to_mchirp()
    lp = chiptunesak.lilypond.Lilypond()
    lp.set_options(format='clip', measures=m_song.tracks[0].measures[3:8])
    ly = chiptunesak.lilypond.to_bin(m_song)
    with open('bach.ly', 'w') as f:
        f.write(ly)

Then execute the Lilypond command:

::

    lilypond -ddelete-intermediate-files -dbackend=eps -dresolution=600 --png bach.ly

The result will be `bach.png` that looks like this:

.. image:: _images/bach.png
    :alt: alternate bachMusic

Example 2:  Midi game music to sheet music
******************************************

 Often, `midi ripped from MS-DOS games <http://www.mirsoft.info/gamemids-ripping-guide.php/>`_ results in messy midi files that don't include keys, time signatures, or even reliable ticks per quarter notes.  This example workflow shows how to turn such music into Lilypond-generated sheet music, and will use `a piece of music <http://www.midi-karaoke.info/21868cd1.html>`_ from an MS-DOS RPG Betrayal At Krondor (Sierra On-Line, 1993).

View the :ref:`DOS MIDI File Example` for the details of this example.
