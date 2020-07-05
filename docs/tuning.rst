======
Tuning
======

Base Tuning Frequency
---------------------

By default, ChiptuneSAK uses the **A4 = 440.00 Hz** tuning convention.

Historically, tuning standards have been based on the frequency of the note A4, which by convention is the A above middle C. Prior to the 20th century, 432 Hz (France) and 435 Hz (Italy) were competing tuning standards. By 1953, nearly everyone had agreed on 440.00 Hz, which is an `ISO standard <https://www.iso.org/standard/3601.html>`_ for all instruments based on chromatic scale. The Commodore SID chip covers a wide range of frequencies, from well below the range of human hearing to B7 (NTSC) or Bb7 (PAL). By comparison, a piano keyboard only covers a little over 7 octaves, from A0 to C8.

MIDI note numbers are based on an even-tempered chromatic scale with middle C (C4) as note 60. The tuning standard, A4, is therefore note 60.

Using this convention, the frequency of MIDI note number *n* is given by :math:`440*2^{(n - 69)/12}`

Some MIDI octave conventions differ, e.g., calling middle C (261.63Hz) C3 instead of C4.  However, since MIDI does not internally use a note-octave representation, but rather a pitch number, this difference is only one of convention. With respect to ChiptuneSAK, such a system would have an octave offset of -1.

Pitches and Cents
-----------------

The Western music scale is made up of 12 evenly-spaced pitches. Humans hear pitch as the *logarithm* of the frequency, and an octave (made up of 12 equally-spaced steps, called *semitones*) is a factor of exactly 2 in frequency. Thus, a semitone is a frequency ratio of :math:`2^{1/12}`, or a factor of about 1.06.  Following this logarithmic pattern, musicians divide semitones into 100 equally-spaced ratios of :math:`2^{1/1200}`, called *cents*.  100 cents make up a semitone, so any frequency can be described by a note and an offset in cents, usually set up to range from -50 to +50.

**Note:** all musical notes and tunings are described by **ratios**, not by **differences**. A common mistake is to treat the difference between two notes as the *difference* in their frequencies. So, for example, you might think that the midpoint between an A4 (440 Hz) and B4 (493.88 Hz) is  :math:`(440 + 493.88) / 2 = 466.94` Hz. That, however, is incorrect.  The true midpoint is :math:`440 * 2^{(log_2(466.94) - log_2(440)) / 2} = 466.16` Hz.

Luckily, ChiptuneSAK has functions to take care of all the math for you.  So think of pitches as notes plus or minus cents.  This notation is very convenient.  For example, if a song is written with a tuning different from the standard 440 Hz, but is otherwise in tune, *all* notes will differ from their standard counterparts *by the same number of cents.*


Chiptunes Tunings
-----------------

C64: NTSC and PAL
+++++++++++++++++

American and European television standards diverged in the 1950s, with American and Japan using `NTSC <https://en.wikipedia.org/wiki/NTSC>`_ and Europe using `PAL <https://en.wikipedia.org/wiki/PAL>`_. Ever since, a debate has raged about which is "better."  Each has its strengths and weaknesses, and ChiptuneSAK lets you work with whichever you prefer.

For the NTSC standard, the frame rate is supposed to be 60 ⁄ 1.001 Hz, which is very close to 59.94 frames per second. The origin of this very strange refresh rate was the need for whole numbers for dividing the refresh rate in order to allow filtering of the color signal. The PAL standard frame rate is exactly 50 frames per second.

However, life is considerably more complex than you might think.  The standards allow for a certain slop in the frame rate; retro computer hardware generally did not produce frames at exactly the specification frequencies.  For example, the NTSC Commodore 64 produces frames at 59.826 Hz, determined by the main system clock frequency of 1.022727 MHz. Likewise, the PAL C64 frame rate is 50.125 Hz, from a system clock frequency of 0.985248 MHz.

As a result, music from identical music generation code will sound very different on the two architectures. For music written for a PAL system, the NTSC playback will be about 19% faster and the notes 65 cents higher.