=================
Metric Modulation
=================

.. contents::

Tuplets background
------------------

A simple factors-of-two rhythm scheme is inadequate to represent chiptunes note data. In Western music there exists a great deal of music that uses note divisions that are *not* powers of 2.  By far the most common non-binary division is of three notes.  This division can be accommodated via the choice of time signature (i.e., 3/4) or by using dot notation to change note durations.  A dotted note is 1 1/2 times the equivalent undotted note; thus, a dotted half note is equal to three quarter notes. However, there are many situations in which groups of three require an explicit representation.  In these situations, *tuplets* are used to represent groups of multiple notes that span a power-of-two duration. By far the most common tuplets are groups of three notes, called *triplets*. Tuplets of other numbers of notes (e.g., 5) exist but are relatively unusual.

If a song is primarily comprised of factor-of-two rhythms, then the song is written in a *simple meter* (implying powers-of-two lengths) and triplets are appropriate. If the song is dominated by groups-of-three rhythms, then it is usually written in what is known as a *compound meter*, in which each beat represents three subdivisions instead of two.  Common compound meters include 6/4, 6/8, and 12/8 time signatures.

**Metric Modulation** is a technique that changes note duration types while still sounding the same, allowing note data to meet the constraints that may be imposed by chiptunes playback environments.

Metric Modulation in ChiptuneSAK
--------------------------------

Metric modulation is primarily used for two purposes in ChiptuneSAK:

1. Some architectures do not support note durations less than a minimum amount.  For example, the shortest note available in C128 BASIC is a 16th note.

  In this case, the length of each note can be multiplied by a constant and the tempo increased by the same factor, resulting in music that sounds the same but now has a shortest note duration that is longer than the original.  This technique is shown in the :ref:`Fix too-short note durations` example.  It is also used in the :ref:`C128 Basic Example`.

2. Many chiptunes architectures do not support triplets.  This limitation can be overcome by using a metric modulation of a factor of 3/2, which eliminates the triplets and puts the music into a compound meter. This technique is illustrated in the :ref:`Eliminate triplets` example.

Metric modulation is achieved by use of the ChirpSong modulate() method:

.. automethod:: chiptunesak.chirp.ChirpSong.modulate
    :noindex:
