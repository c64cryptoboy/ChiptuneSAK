# Metric Modulation

## Definition/Description

TODO

## Example 1: Enforce a shortest note division
tools/BWV_799.mid is a three-part Bach invention.  We can convert it to a C128 BASIC program as follows:

```C:\Users\crypt\git\chiptune-sak>python tools\midiToC128Basic.py test\BWV_test.mid test\BWV_test.prg -t prg```

This should sound fine to anyone not familiar with the piece.  However, C128 BASIC PLAY command can perform 16th notes, but not finer durations (e.g., 32nd notes, etc).  And BWV 799 contains 32nd notes towards the end.

A solution is to use metric modulation to double all the note durations, as well as doubling the BPM so that the perceived tempo remains the same.  That way, the smallest note duration is a 16th note, which PLAY commands can play.

This command will change the 3/8 time signature piece into a 3/4 time signature, along with the changes described above:
```python tools\TransformMidi.py -m 2/1 -q 16 -j 3/4 test\BWV_799.mid test\BWV_test.mid```

Now when BWV_test is converted to C128 BASIC, all the notes are present.

## Example 2: Remove triplets by converting to a compound meter

TODO