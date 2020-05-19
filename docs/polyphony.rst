=========
Polyphony
=========

In electronic music, the word `polyphony <https://en.wikipedia.org/wiki/Polyphony_and_monophony_in_instruments>`_ refers to playing multiple independent notes at the same time.  Because of hardware limitations, electronic music instruments can only play a certain number of notes simultaneously. For synthesizers, the maximum number of notes that can be played simultaneously is the `polyphonic specification <https://electronicmusic.fandom.com/wiki/Polyphonic>`_ .  Modern music workstations generally have between 64 and 256-note polyphony, or, in some cases, no polyphonic limits at all.

A related term is `paraphony <https://sdiy.info/wiki/Paraphony>`_ , in which an instrument can play multiple notes at once, but they all pass through a common filter and amplifier.

Polyphony in retro computers
----------------------------

The original Apple I had the ability to produce a single tone on the speaker.  With the advent of the Mockingboard on the Apple II, this was expanded to 3 voices, and later to 6 square-wave voices.

The Commodore 64 used the SID chip, which had 3 voices and was a mixture between paraphony and polyphony.  It could use independent waveforms for each voice, but voices did not have independent filters.

PC sound cards, such at the AdLib and Soundblaster, used FM synthesis and had higher potential polyphony, although for FM synthesis there is a tradeoff between polyphony and sound quality. The original AdLib card could do 9 voices plus percussion, and the Soundblaster 16 had 18-voice polyphony.

FM synthesis is difficult and, in the early 90s, required specialists to obtain acceptable-sounding music. So PC sound cards began to use MIDI as input, with a set of pre-defined instruments.

Of course this history is incomplete and lacks many important details, but it is meant to put polyphony into perspective.

Polyphony in ChiptuneSAK
------------------------

For live music, polyphony is often much higher than intended. For example, if series of notes is played on a  given channel the previous note may not be released before the new note is struck, with a short overlap in which polyphony is increased.

Retro computers generally are not tolerant of such polyphony; a given voice on a SID chip can play only one note at a time.

To enable of music to these constrained environments, ChiptuneSAK provides tools to control polyphony. In general, for conversion to or from retro formats, ChiptuneSAK requires each individual channel (or track) to be monophonic.

ChiptuneSAK also requires each track to be monophonic for the generation of sheet music.

The :ref:`Chirp` intermediate representation has methods to eliminate polyphony in an intelligent manner, as well as to "explode" a polyphonic track into multiple monophonic tracks.

Chirp Polyphony Methods
+++++++++++++++++++++++

.. automethod:: ctsChirp.ChirpTrack.is_polyphonic
    :noindex:

.. automethod:: ctsChirp.ChirpTrack.remove_polyphony
    :noindex:

.. automethod:: ctsChirp.ChirpSong.is_polyphonic
    :noindex:

.. automethod:: ctsChirp.ChirpSong.remove_polyphony
    :noindex:

.. automethod:: ctsChirp.ChirpSong.explode_polyphony
    :noindex:



