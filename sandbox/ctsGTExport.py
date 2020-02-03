# Convert Chirp to GoatTracker2 and save as .sng file
#
# TODOs:
# - get a simplified end-to-end working, then add features

import sys
import sandboxPath
import copy
import math
from fractions import Fraction
from recordtype import recordtype
from functools import reduce, partial
from sortedcontainers import SortedDict
from ctsConstants import GT_FILE_HEADER, NTSC_FRAMES_PER_SEC, PAL_FRAMES_PER_SEC, \
    GT_MAX_ELM_PER_ORDERLIST, GT_MAX_PATTERNS_PER_SONG, GT_MAX_ROWS_PER_PATTERN, \
    GT_OCTAVE_BASE, GT_KEY_ON, GT_KEY_OFF, GT_OL_RST
from ctsBase import duration_to_note_name, GtPatternRow, PATTERN_END_ROW, PATTERN_EMPTY_ROW, \
    GtInstrument
import ctsChirp
import ctsMidiImport
from ctsErrors import ChiptuneSAKQuantizationError, ChiptuneSAKPolyphonyError


# A Procrustean bed for GT text fields.  Can accept a string or bytes.
def pad_or_truncate(to_pad, length):
    if isinstance(to_pad, str):
        to_pad = to_pad.encode('latin-1')
    return to_pad.ljust(length, b'\0')[0:length]


# Convert midi note value into pattern note value
# Note: lowest goat tracker note C0 (0x60) = midi #24
def midi_note_to_pattern_note(midi_note):
    return midi_note + 0x60 + (-1 * GT_OCTAVE_BASE * 12)


def row_to_bytes(row):
    return bytes([row.note_data, row.inst_num, row.command, row.command_data])


def instrument_to_bytes(instrument):
    result = bytearray()
    result += bytes([instrument.attack_decay, instrument.sustain_release, 
        instrument.wave_ptr, instrument.pulse_ptr, instrument.filter_ptr,
        instrument.vib_speedtable_ptr, instrument.vib_delay, instrument.gateoff_timer,
        instrument.hard_restart_1st_frame_wave])
    result += pad_or_truncate(instrument.inst_name, 16)
    return result


def chirp_to_GT(song, out_filename, tracknums = [1, 2, 3], jiffy=NTSC_FRAMES_PER_SEC):
    def midi_to_gt_tick(midi_ticks, offset, factor):
        return midi_ticks // factor + offset

    if not song.is_quantized():
        raise ChiptuneSAKQuantizationError("ChirpSong must be quantized for export to GT")
    if song.is_polyphonic():
        raise ChiptuneSAKPolyphonyError("ChirpSong must be non-polyphonic for export to GT")

    export_tracks = [copy.deepcopy(song.tracks[t-1]) for t in tracknums]
    # Get distinct note lengths from quantized song
    note_lengths_ticks = set(n.duration for t in export_tracks for n in t.notes)

    # Any note length can be formed from a multiple of tick granularity
    required_tick_granularity = reduce(math.gcd, sorted(note_lengths_ticks))

    min_row_note_lengths = set(n//required_tick_granularity for n in note_lengths_ticks)
    # This is the minimum number of rows required to have all notes representable by an integer number of rows.
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


    # Make a sparse representation of rows for each channel
    # TODO: This simple transformation will need to be changed when it's time
    #       to incorporate music compression, mid-tune tempo changes, etc.
    DEFAULT_INSTRUMENT = 1
    channels_rows = [SortedDict() for i in range(3)]
    for i, track in enumerate(export_tracks):
        channel_row = channels_rows[i]
        for note in track.notes:
            note_num = midi_note_to_pattern_note(note.note_num)
            assert note.duration % required_tick_granularity == 0, \
                'Error: unexpected quantized value'
            assert note.start_time % required_tick_granularity == 0, \
                'Error: unexpected quantized value'
            global_row_start = int(note.start_time / required_tick_granularity)
            global_row_end = int((note.start_time + note.duration) / required_tick_granularity)

            # insert or update a pattern row
            channel_row.setdefault(global_row_start, GtPatternRow()).note_data=note_num
            # update that pattern row
            channel_row[global_row_start].inst_num=DEFAULT_INSTRUMENT

            # Since we get the notes in order, this note end is very likely to be overwritten
            # later by the next note (this is good)
            channel_row.setdefault(global_row_end, GtPatternRow()).note_data=GT_KEY_OFF

    # TODO: In sparse representation, add code to inject the initial tempo into the first row
    # of one of the channels

    # Convert the sparse representation into separate patterns (of bytes)
    EXPORT_PATTERN_LEN = 64 # index 0 to len-1 for data, index len for 0xFF pattern end mark
    patterns = [] # can be shared across all channels
    orderlists = [[],[],[]] # one for each channel
    curr_pattern_num = 0
    for i, channel_rows in enumerate(channels_rows):
        pattern_row_index = 0
        pattern = bytearray()
        max_row = channel_rows.keys()[-1]
        for j in range(max_row+1): # iterate across row num span (inclusive)
            if j in channel_rows:
                pattern += row_to_bytes(channel_rows[j])
            else:
                pattern += row_to_bytes(PATTERN_EMPTY_ROW)
            pattern_row_index += 1
            if pattern_row_index == EXPORT_PATTERN_LEN:
                pattern += row_to_bytes(PATTERN_END_ROW)
                patterns.append(pattern)
                orderlists[i].append(curr_pattern_num)
                curr_pattern_num += 1
                pattern = bytearray()
                pattern_row_index = 0
        if len(pattern) > 0: # if there's a final partially-filled pattern, add it
             pattern += row_to_bytes(PATTERN_END_ROW)
             patterns.append(pattern)
             orderlists[i].append(curr_pattern_num)
             curr_pattern_num += 1
    
    # Usually, songs repeat.  Each channel's orderlist ends with RST00, which means restart at the
    # 1st entry in that channel's pattern list (note: orderlist is normally full of pattern numbers,
    # but the number after RST is not a pattern number, but an index back into that channel's orderlist)
    # As far as I can tell, people create an infinite loop at the end when they don't want a song to
    # repeat, so that's what this code can do.

    # TODO: Setting this boolean should be an optional command line flag
    END_WITH_REPEAT = False # This doesn't imply that all tracks will restart at the same time...

    if not END_WITH_REPEAT:
        # create a new empty pattern for all three channels to loop on forever
        # and add to the end of each orderlist
        loop_pattern = []
        loop_pattern += row_to_bytes(GtPatternRow(note_data=GT_KEY_OFF))
        loop_pattern += row_to_bytes(PATTERN_END_ROW)
        patterns.append(loop_pattern)
        loop_pattern_num = len(patterns)-1
        for i in range(3):
            orderlists[i].append(loop_pattern_num)

    for i in range(3):
        orderlists[i].append(GT_OL_RST) # patterns end with restart indicator
        if END_WITH_REPEAT:
            orderlists[i].append(0) # index of start of channel order list 
        else:
            orderlists[i].append(len(orderlists[i])-2) # index of the empty loop pattern

    gt_binary = bytearray()

    # append headers to gt binary
    gt_binary += GT_FILE_HEADER
    gt_binary += pad_or_truncate(song.metadata.name, 32)
    gt_binary += pad_or_truncate(song.metadata.composer, 32)
    gt_binary += pad_or_truncate(song.metadata.copyright, 32)
    gt_binary.append(0x01) # number of subtunes

    # append orderlists to gt binary
    for i in range(3):
        gt_binary.append(len(orderlists[i])-1) # orderlist length minus 1
        gt_binary += bytes(orderlists[i])

    # Need an instrument
    # For now, just going to design a simple triangle sound as instrument number 1.
    # This requires setting ADSR, and a wavetable position of 01.
    # Then a wavetable with the entires 01:11 00, and 02:FF 00

    # TODO: At some point, should add support for loading gt .ins instrument files for the channels

    gt_binary.append(0x01) # number of instruments (not counting NOP instrument 0)
    gt_binary += instrument_to_bytes(GtInstrument(inst_num=1, attack_decay=0x22, sustain_release=0xFA,
        wave_ptr=0x01, inst_name='simple triangle'))
    # TODO: In the future, more instruments appended here (in instrument number order)
    
    # TODO: append the four tables (create the wavetable first)

    # TODO: append patterns
    """
    This structure repeats for each of the 4 tables (wavetable, pulsetable,
    filtertable, speedtable).

    Offset  Size    Description
    +0      byte    Amount n of rows in the table
    +1      n       Left side of the table
    +1+n    n       Right side of the table

    Offset  Size    Description
    +0      byte    Number of patterns n

    Repeat n times, starting from pattern number 0.

    Offset  Size    Description
    +0      byte    Length of pattern in rows m
    +1      m*4     Groups of 4 bytes for each row of the pattern:
                    1st byte: Notenumber
                            Values $60-$BC are the notes C-0 - G#7
                            Value $BD is rest
                            Value $BE is keyoff
                            Value $BF is keyon
                            Value $FF is pattern end
                    2nd byte: Instrument number ($00-$3F)
                    3rd byte: Command ($00-$0F)
                    4th byte: Command databyte   
    """

    return gt_binary


if __name__ == "__main__":
    song = ctsMidiImport.midi_to_chirp(sys.argv[1])
    song.estimate_quantization()
    song.quantize()
    song.remove_polyphony()

    gt_binary = chirp_to_GT(song, 'tmp.sng')
