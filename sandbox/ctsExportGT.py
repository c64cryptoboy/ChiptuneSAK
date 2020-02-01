# Convert Chirp to GoatTracker2 and save as .sng file
#
# TODOs:
# - 

import sys
import sandboxPath
from fractions import Fraction
from functools import reduce, partial
from ctsErrors import *
from ctsConstants import *
import ctsChirp

def chirp_to_GT(song, out_filename, tracknums = [1, 2, 3], jiffy=PAL_FRAMES_PER_SEC):
    def midi_to_gt_tick(midi_ticks, offset, factor):
        return midi_ticks // factor + offset

    if not song.is_quantized():
        raise ChiptuneSAKQuantizationError("ChirpSong must be quantized for export to GT")
    if song.is_polyphonic():
        raise ChiptuneSAKPolyphonyError("ChirpSong must be non-polyphonic for export to GT")

    ###  For the following, I am currently IGNORING triplets!!!!

    # TODO: Algorithm design
    # Assertion: chirp ticks and goattracker rows are unitless (no mapping to time without tempo)
    # Find the unique set of note lengths in chirp ticks
    # reduce set to create most granular row length (e.g. 20, 30, 40, 80 -> 2, 3, 4, 8)
    #    this means finding the greatest common divisor, and divising it
    #    In other words, the minimum reduction that remains integers
    # From this, map BPM to what the tempo should be
    #    This creates the minimum number of rows necessary per note type


    # Count the number of jiffies per beat
    jiffies_per_beat = jiffy / (song.bpm / 60) # jiffies per sec / bpm / 60

    # Get the minimum note length for the song from the quantization
    min_note_length = Fraction(song.qticks_durations/song.ppq).limit_denominator(64)

    # Minimum number of rows needed per note for this song
    min_rows = int(jiffies_per_beat * min_note_length)

    print(jiffies_per_beat, min_note_length, ctsChirp.duration_to_note_name(min_note_length * song.ppq, song.ppq), min_rows)

    # TODO: Change GT tempos to reflect upcoming note lengths.  For now, just set to the tempo needed.
    midi_to_tick = partial(midi_to_gt_tick, offset=0, factor=min_rows)

    # Set the tempo at tick 0 for all three voices

    for itrack, tracknum in enumerate(tracknums):
        track = song.tracks[tracknum-1]
        for note in track.notes:
            tick_start = midi_to_tick(note.start_time)
            tick_end = midi_to_tick(note.start_time + note.duration)
            note_num = note.note_num
            ## Add the start and end of the note to the ticks for track itrack

    ## Clean up and write .sng file
    ##  And that should be it!


# Here for debugging, remove later
def main():
    pass


if __name__ == "__main__":
    main()
