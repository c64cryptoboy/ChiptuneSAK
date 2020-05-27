*****************
Metric Modulation
*****************

.. contents::

Definition/Description
######################

The simple factors-of-two rhythm scheme is inadequate. Even in Western music there exists a great deal of music that uses note divisions that are *not* powers of 2.  By far the most common grouping is of three notes.  For longer durations, this grouping can be accomplished using so-called dot notation: a dotted note is 1 1/2 times the equivalent undotted note; thus, a dotted half note is equal to three quarter notes. However, there are many situations in which groups of three are in music that is better suited to the powers-of two representation.  In these situations, a notation concept called *tuples* is used to represent groups of multiple notes that fill a single beat. By far the most common tuples are groups of three notes, called *triplets*. Tuplets of other numers of notes exist but are quite rare.

If a song is primarily comprised of factor-of-two rhythms, then the song is written in a *simple meter* (implying powers-of-two lengths) and triplets are appropriate. If the song is dominated by groups-of-three rhythms, then it is usually written in what is known as a *compound meter*, in which each beat represents three subdivisions instead of two.  Common compound meters include 6/4, 6/8, and 12/8 time signatures.

**Metric Modulation** is a technique that changes note duration types while still sounding the same, allowing music to meet the constraints that may be imposed by 8-bit chiptunes devices.

Metric Modulation in ChiptuneSAK
################################

Metric modulation is primarily used for two purposes in ChiptuneSAK:

1. Some architectures do not support note durations less than a minimum amount.  For example, the shortest note available in C128 BASIC is a 16th note.

  In this case, the length of each note can be multiplied by a constant and the tempo increased by the same factor, resulting in music that sounds the same but now has a shortest note duration that is longer than the original.  This technique is shown in the :ref:`Fix too-short note durations` example.  It is also used in the :ref:`C128 Basic Example`.

2. Many chiptunes architectures do not support triplets.  This limitation can be overcome by using a metric modulation of a factor of 3/2, which eliminates the triplets and puts the music into a compound meter. This technnique is illustrated in the :ref:`Eliminate triplets` example.

Metric modulation is achieved by use of the ChirpSong modulate() method:

.. automethod:: ctsChirp.ChirpSong.modulate
    :noindex: