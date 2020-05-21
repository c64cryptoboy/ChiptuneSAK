=========
Polyphony
=========

In electronic music, the word `polyphony <https://en.wikipedia.org/wiki/Polyphony_and_monophony_in_instruments>`_ refers to playing multiple independent notes at the same time.  Because of hardware limitations, electronic music instruments can only play a certain number of notes simultaneously. For synthesizers, the maximum number of notes that can be played simultaneously is the `polyphonic specification <https://electronicmusic.fandom.com/wiki/Polyphonic>`_ .  Modern music workstations generally have between 64 and 256-note polyphony, or, in some cases, no polyphonic limits at all.

A related term is `paraphony <https://sdiy.info/wiki/Paraphony>`_ , in which an instrument can play multiple notes at once, but these independent voices can (or must) be further processed through common electronic signal paths.

Polyphony in retro computers
----------------------------

The original Apple I (1976) has the ability to produce a single tone on the speaker.  With the advent of the Mockingboard (1983) on the Apple II (1977), this was expanded to 3 voices, and later to 6 square-wave voices.

The Atari 400 and Atari 800 computers (1979) feature the distinctive sounding POKEY chip, which can be configured for four 8-bit (frequency) channels, two 16-bit channels, or one 16-bit and two 8-bit channels.  Each of its square-wave channels has an independent volume control, and they share a filter (high-pass only).

The Commodore 64 (1982) uses the well-known SID chip, which offers 3 independent voices and multiple waveforms.  Like the other systems, it has some shared-feature paraphony, which for the SID includes a master volume and a programmable filter through which each voice can be routed.

PC sound cards, such at the AdLib (1987) and Soundblaster (1989), use FM synthesis, creating greater potential polyphony, although for FM synthesis there is a tradeoff between polyphony and sound quality. The original AdLib card performs 9 voices plus percussion, and the Soundblaster 16 has 18-voice polyphony.

FM synthesis is difficult to program and, in the early 90s, required specialists to obtain acceptable-sounding music. So PC sound cards began to use MIDI as input, with a set of pre-defined instruments.

Of course this history is incomplete and lacks many important details, but it is meant to put polyphony into perspective.

Polyphony in ChiptuneSAK
------------------------

The act of performing sheet music can increase the polyphony over what is indicated by the sheet music. For example, if a series of notes is played on a given channel, the previous note may not be released before the new note is struck, creating a short overlap in which polyphony is increased. Polyphony can also arise from effects such as sustain, which leaves notes on after their release.

Often, when adapting music for use in retro computers that can only support limited polyphony, much of the polyphony arising from performance or effects must be removed. In general, for conversion to or from retro formats, ChiptuneSAK requires each individual channel (or track) to be monophonic.  ChiptuneSAK also requires each track to be monophonic for the generation of sheet music.  Fortunately, ChiptuneSAK offers a growing set of tools to help control polyphony for playback in constrained environments.

One can think of polyphony removal as removing any overlap between notes. Combined with :ref:`quantization`, it ensures that the music representation is the same as an exact literal reading of the sheet music.

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



