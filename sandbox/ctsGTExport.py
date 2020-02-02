# Convert Chirp to GoatTracker2 and save as .sng file
#
# TODOs:
# -

import sys
import sandboxPath
from fractions import Fraction
import math
from functools import reduce, partial
from ctsErrors import ChiptuneSAKQuantizationError, ChiptuneSAKPolyphonyError
from ctsConstants import GT_FILE_HEADER, NTSC_FRAMES_PER_SEC, PAL_FRAMES_PER_SEC, \
    GT_MAX_ELM_PER_ORDERLIST, GT_MAX_PATTERNS_PER_SONG, GT_MAX_ROWS_PER_PATTERN
from ctsBase import duration_to_note_name
import ctsChirp
import ctsMidiImport


# A Procrustean bed for GT text fields.  Can accept a string or bytes.
def pad_or_truncate(to_pad, length):
    if isinstance(to_pad, str):
        to_pad = to_pad.encode('latin-1')
    return to_pad.ljust(length, b'\0')[0:length]


def chirp_to_GT(song, out_filename, tracknums = [1, 2, 3], jiffy=NTSC_FRAMES_PER_SEC):
    def midi_to_gt_tick(midi_ticks, offset, factor):
        return midi_ticks // factor + offset

    if not song.is_quantized():
        raise ChiptuneSAKQuantizationError("ChirpSong must be quantized for export to GT")
    if song.is_polyphonic():
        raise ChiptuneSAKPolyphonyError("ChirpSong must be non-polyphonic for export to GT")

    # Get distinct note lengths from quantized song
    note_lengths_ticks = set(n.duration for t in song.tracks for n in t.notes)

    # Any note length can be formed from a multiple of tick granularity
    required_tick_granularity = reduce(math.gcd, sorted(note_lengths_ticks))

    min_row_note_lengths = set(n//required_tick_granularity for n in note_lengths_ticks)
    # This is the minumum number of rows required to have all notes representable by an integer number of rows.
    min_rows_per_note = min(min_row_note_lengths)

    # TODO: Debug info (remove or turn into comments later)
    dur_str = duration_to_note_name(required_tick_granularity, song.metadata.ppq)
    print("required granularity = %s note" % dur_str)
    print("song time signature denominator = %d" % song.metadata.time_signature.denom)
    min_rows_per_beat = song.metadata.ppq * 4 // song.metadata.time_signature.denom // required_tick_granularity
    print("minimum rows per beat = %d" % min_rows_per_beat)
    print("available bpms for jiffy = %.2lf per sec:" % jiffy)
    print('\n'.join("%.1lf bpm" % (jiffy / (n * min_rows_per_beat) * 60.) for n in range(1, 20)))

    # This is now a real number to convert between unitless midi ticks and unitless GT ticks
    # The complication is that you can multiply the min_rows_per_note by an integer to give better
    #   time resolution, which will result in a different set of GT tempos available
    midi_to_tick = partial(midi_to_gt_tick, offset=0, factor=song.metadata.ppq // min_rows_per_note)

    # Logic that can help with assigning a tempo to the GT rows:
    jiffies_per_beat = jiffy / (song.metadata.bpm / 60) # jiffies per sec / bps
    min_rows_per_quarter = song.metadata.ppq // required_tick_granularity

    # Convert chirp tracks into patterns and orderlists
    # TODO: This simple transformation will need to be changed when it's time
    #       to incorporate music compression
    EXPORT_PATTERN_LEN = 64 # will actually be this +1 (there's a 0xFF pattern end mark)
    for itrack, tracknum in enumerate(tracknums):
        track = song.tracks[tracknum-1]
        for note in track.notes:
            note_num = note.note_num # do midi to gt conversion
            tick_start = midi_to_tick(note.start_time)
            tick_end = midi_to_tick(note.start_time + note.duration)

            # CODE: divide note.duraiton by required_tick_granularity to get rows for the note
            #   use note.duration to insert note off, which will likely get overwriten by
            #   the next upcoming note on event.

            # When EXPORT_PATTERN_LEN notes processed, add that pattern to collection, update
            # the order list structure

        # Take any notes left, make them a pattern, update order list

    gt_binary = bytearray()
    gt_binary += GT_FILE_HEADER
    gt_binary += pad_or_truncate(song.metadata.name, 32)
    gt_binary += pad_or_truncate(song.metadata.composer, 32)
    gt_binary += pad_or_truncate("TODO: copyright", 32)
    gt_binary += b'0x01' # number of subtunes

    # CODE: Next things to go into the binary is the orderlist for each channel

    """
    6.1.2 ChirpSong orderlists
    ---------------------
    The orderlist structure repeats first for channels 1,2,3 of first subtune,
    then for channels 1,2,3 of second subtune etc., until all subtunes
    have been gone thru.

    Offset  Size    Description
    +0      byte    Length of this channel's orderlist n, not counting restart pos.
    +1      n+1     The orderlist data:
                    Values $00-$CF are pattern numbers
                    Values $D0-$DF are repeat commands
                    Values $E0-$FE are transpose commands
                    Value $FF is the RST endmark, followed by a byte that indicates
                    the restart position
    """

    # Note: orderlist length byte is length -1
    #    e.g. CHN1: 00 04 07 0d 09 RST00 in file as 06 00 04 07 0d 09 FF 00
    #    length-1 (06), followed by 7 bytes

    # TODO: Set the tempo at tick 0 for all three voices


    return gt_binary


if __name__ == "__main__":
    song = ctsMidiImport.midi_to_chirp(sys.argv[1])
    song.estimate_quantization()
    song.quantize()
    song.remove_polyphony()

    gt_binary = chirp_to_GT(song, 'tmp.sng')
