import sandboxPath
from fractions import Fraction
from functools import reduce, partial
from ctsErrors import *
from ctsConstants import *
import ctsSong

def chirp_to_GT(song, tracknums = [1, 2, 3], jiffy=60):
    def midi_to_gt_tick(midi_ticks, offset, factor):
        return midi_ticks // factor + offset

    if not song.is_quantized():
        raise ChiptuneSAKQuantizationError("Song must be quantized for export to GT")
    if song.is_polyphonic():
        raise ChiptuneSAKPolyphonyError("Song must be non-polyphonic for export to GT")

    ###  For the following, I am currently IGNORING triplets!!!!

    # Count the number of jiffies per beat
    rows_per_beat = (jiffy * 60) // song.bpm  # (rows/sec) / (beats/min/60)

    # Get the minimum note length for the song from the quantization
    min_note_length = Fraction(song.qticks_durations/song.ppq).limit_denominator(64)

    # Assuming that the beat is a quarter note, get rows per midi tick
    rows_per_midi_tick = int(rows_per_beat * min_note_length)

    # Minimum number of rows needed per note for this song
    min_rows = int(rows_per_beat * min_note_length)

    # TODO: Change GT tempos to reflect upcoming note lengths.  For now, just set to the tempo needed.
    midi_to_tick = partial(midi_to_gt_tick(offset=0, factor=min_rows))
    tempo = min_rows

    # Set the tempo at tick 0 for all three voices

    for itrack, tracknum in enumerate(tracknums):
        track = song.tracks[tracknum]
        for note in track:
            tick_start = midi_to_tick(note.start_time)
            tick_end = midi_to_tick(note.start_time + note.duration)
            note_num = note.note_num
            ## Add the start and end of the note to the ticks for track itrack

    ## Clean up and write .sng file
    ##  And that should be it!
