*****************
Metric Modulation
*****************

.. contents::

Definition/Description
######################

The simplest conception of music uses note durations that are powers of 2 from some basic beat.  For example, in Western (European) music, a whole note is made up of 2 half notes, 4 quarter notes, 8 eighth notes, or 16 sixteenth notes.  The note names themselves reflect this division.

However, even in Western music there exists a great deal of music that uses note divisions that are *not* powers of 2.  By far the most common grouping is of three notes.  For longer durations, this grouping can be accomplished using so-called dot notation: a dotted note is 1 1/2 times the equivalent undotted note; thus, a dotted half note is equal to three quarter notes. However, there are many situations in which groups of three are in music that is better suited to the powers-of two representation.  In these situations, a notation concept called *tuples* is used to represent groups of multiple notes that fill a single beat. By far the most common tuples are groups of three notes, called *triplets*. Tuplets of other numers of notes exist but are quite rare.

If a song is primarily comprised of factor-of-two rhythms, then the song is written in a *simple meter* (implying powers-of-two lengths) and triplets are appropriate. If the song is dominated by groups-of-three rhythms, then it is usually written in what is known as a *compound meter*, in which each beat represents three subdivisions instead of two.  Common compound meters include 6/4, 6/8, and 12/8 time signatures.

**Metric Modulation** is a technique that allows music written in a simple meter to be converted to a compound meter. Chiptune engines frequently only support simple meters and require that all notes be powers-of-two lengths. Using metric modulation, music that contains tuples can be converted to music that obeys factor-of-two constraints.

Examples:
#########

Example 1: Enforce a shortest note division
*******************************************

tools/BWV_799.mid is a three-part Bach invention.  We can convert it to a C128 BASIC program as follows:

::

    python tools\midiToC128Basic.py test\BWV_test.mid test\BWV_test.prg -t prg

This should sound fine to anyone not familiar with the piece.  However, C128 BASIC PLAY command can perform 16th notes, but not finer durations (e.g., 32nd notes, etc).  And BWV 799 contains 32nd notes towards the end.

A solution is to use metric modulation to double all the note durations, as well as doubling the BPM so that the perceived tempo remains the same.  That way, the smallest note duration is a 16th note, which PLAY commands can play.

This command will change the 3/8 time signature piece into a 3/4 time signature, along with the changes described above:

::

    python tools\midiTransform.py -m 2/1 -q 16 -j 3/4 test\BWV_799.mid test\BWV_test.mid

Now when BWV_test is converted to C128 BASIC, all the notes are present.

Example 2: Remove triplets by converting to a compound meter
************************************************************

TODO
