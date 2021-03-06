=====================
The MIDI Music Format
=====================

The `MIDI <https://en.wikipedia.org/wiki/MIDI>`_ (**M**\ usic **I**\ nstrument **D**\ igital **I**\ nterface) specification is a standard that allows digital control of musical instruments. The standard encompasses both hardware and communications protocols.

MIDI hardware uses a TTL-level serial interface with optical isolation to communicate between a controller and instruments. The serial rate is about 33 kib/s, which is fast enough to communicate instructions to the instrument with no perceptual latency.

The MIDI protocol defines messages for sending note on/off and control data. These messages are sent in real time from the controller to the instruments. Different instruments are controlled by specifying different *channels* for the MIDI messages.

The MIDI protocol is stateless -- every message is complete on its own and does not rely on any state in the instrument. The instrument, of course, must retain state (such as what notes are playing) but the protocol itself does not.

MIDI Files
----------

Inevitably, the MIDI protocol spawned file formats to contain MIDI messages for playback and editing. The `standard MIDI file format <http://www.somascape.org/midi/tech/mfile.html>`_ (SMF), with extension .mid, was created to fill that need. Because a MIDI file is made of instructions to send to a set of instruments, it is far more compact than the equivalent recorded music file, usually by a factor of 100 or more.

MIDI File Formats
+++++++++++++++++

There are 3 types of SMF files:  types 0, 1, and 2.  Type 0 files contain all the data for all instruments mixed together.  Type 1 files have a separate track for each channel (or instrument), with a dedicated track for meta-messages such as tempo or key signature changes.  Type 2 files can store multiple arrangements of the same music, and are rarely used.

ChiptuneSAK can read MIDI type 0 and type 1 files with the :ref:`MIDI` class.  When reading type 0 files, it automatically splits the channels into separate tracks.  The MIDI class will only write type 1 files.

MIDI Tempos and PPQ
+++++++++++++++++++

The MIDI transport protocol does not declare an explicit tempo. However, playing back MIDI files requires a tempo marking to reproduce a live performance. As a result, two concepts were added to MIDI files. The first is the **tempo**\ , specified in units of QPM (quarter-notes per minute).  The second is called **PPQ**\ , or Pulses Per Quarter note (PPQN), which sets the resolution of the MIDI playback. These pulses are commonly known as "MIDI ticks."  Every MIDI event during playback of a MIDI file occurs on a MIDI tick; however, multiple MIDI messages can be specified to occur on the same tick.

The playback speed, in QPM, determines the rate at which the MIDI ticks will be played back. Because of this separation between ticks and tempo, the same music can be played back at different speeds without any modification of the underlying MIDI messages.  The MIDI tempo setting can be changed at any point in the song.

Because every note must start and end on a MIDI tick, the PPQ is usually set to divide every note in the song evenly. Since music will frequently have notes that have both powers of 2 and factors of 3 in their durations, commonly-used PPQ values have several factors of each: 120 (= 2 * 3 * 4 * 5), 480 (= 2 * 2 * 3 * 4 * 5), and 960 (= 2 * 2 * 2 * 3 * 4 * 5) are the most-commonly seen. Occasionally, for music with no triples, powers of 2 are used; PPQ value of 512 and 1024 are not uncommon.

ChiptuneSAK defaults to a PPQ of 960, which allows fine-resolution playback of most music.

MIDI Recordings and PPQ
#######################

Much game music, especially from MS-DOS games, was played as MIDI commands to the sound cards. The internal storage of the music was often not as MIDI files, however. Many of these songs have been recovered by capturing the MIDI messages and saving them. While this technique allows simple reproduction of the music, the captured MIDI commands do not have any information about tempo or PPQ, and thus a great deal of information must be reconstructed.  ChiptuneSAK has tools that will help to recover that lost information to aid in transforming it to other forms, such as sheet music or tracker-based music.

MIDI Key Signatures and Time Signatures
+++++++++++++++++++++++++++++++++++++++

As the MIDI standard became widespread, it was used for music composition and editing as well as live performance and playback. Additional features, such as song and track names, composer name, and copyright information were added to the file-based MIDI. Most significantly, meta-messages for time signature and key signature were added to the MIDI specification.

None of these messages are ever transmitted to the instruments; they are there for composition and editing of the music. Neither time signatures nor key signatures have any effect on MIDI playback. However, they are required to convert MIDI music to sheet music.  ChiptuneSAK supports all of these meta-messages in MIDI files.

MIDI File Encoding
++++++++++++++++++

To save space, MIDI files store messages in what is known as *time-delta* format.  That is, the messages are stored as events along with the time in ticks between events. There is no concept of absolute time for MIDI messages.  A note is started with a note_on message and ended with a note_off message. The MIDI protocol is stateless and has no concept of note durations.

Humans, on the other hand, do not perceive music in a stateless way.  We think of notes as starting and having a duration.  ChiptuneSAK converts the stateless MIDI messages to a human-friendly stateful representation to make editing, conversion, and display easier.

MIDI Keyswitches
++++++++++++++++

Some modern virtual instruments (such as Garritan) use `keyswitches <https://blog.presonus.com/index.php/2018/11/30/friday-tips-keyswitching-made-easy/>`_ , specific (usually low) MIDI notes that trigger real-time modification of instrument sounds during performance. This practice violates the spirit of the MIDI standard, in that it uses *notes* to trigger *effects*, something that was meant to be done via MIDI controllers and program messages.

Whether or not it is a good idea, the practice exists and as a result MIDI files will often contain spurious notes that are meant as keyswitches and not meant to be played back.  ChiptuneSAK will, by default, remove the keyswitch notes (noes with MIDI number <= 8) when importing a MIDI file, but the option can be overridden.

