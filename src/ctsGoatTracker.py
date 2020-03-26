# Code to import and export goattracker .sng files (both regular and stereo)
# 
# Notes:
# - This code ignores multispeed (for now)
#
# TODOs:
# - Add instrument file loader to use with channels on exports
# - Lots of misc TODOs in the code below

from os import path
import sys
import argparse
import copy
import math
from fractions import Fraction
from functools import reduce
from dataclasses import dataclass
from collections import defaultdict
from ctsConstants import ARCH, C0_MIDI_NUM
import ctsChirp
import ctsRChirp
import ctsMidi
from ctsErrors import ChiptuneSAKException, ChiptuneSAKQuantizationError, \
    ChiptuneSAKContentError, ChiptuneSAKPolyphonyError

# Generalized instrument handling when creating new goattracker binaries is not supported yet.
# So this constant is used so it's easy to look through the code to see where hardcoded assumptions
# are being made.
DEFAULT_INSTRUMENT = 1

# GoatTracker constants
GT_FILE_HEADER = b'GTS5'
GT_DEFAULT_TEMPO = 6
GT_DEFAULT_FUNKTEMPOS = [9, 6]  # default alternating tempos, from gplay.c

# All these MAXes are the same for goattracker 2 (1SID) and goattracker 2 stereo (2SID)
# (Note: MAXes vary in the SID-Wizard 1SID, 2SID, and 3SID engines)
# Most found in gcommon.h
GT_MAX_SUBTUNES_PER_SONG = 32  # Each subtune gets its own orderlist of patterns
# "song" means a collection of independently-playable subtunes
GT_MAX_ELM_PER_ORDERLIST = 255  # at minimum, it must contain the endmark and following byte
GT_MAX_INSTR_PER_SONG = 63
GT_MAX_PATTERNS_PER_SONG = 208  # patterns can be shared across channels and subtunes
GT_MAX_ROWS_PER_PATTERN = 128  # and min rows (not including end marker) is 1
GT_MAX_TABLE_LEN = 255

GT_REST = 0xBD  # A rest in goattracker means NOP, not rest
GT_KEY_OFF = 0xBE
GT_KEY_ON = 0xBF
GT_OL_RST = 0xFF  # order list restart marker
GT_PAT_END = 0xFF  # pattern end
GT_TEMPO_CHNG_CMD = 0x0F


#
#
# Code to parse goattracker and goattracker stereo files
#
#

@dataclass
class GtHeader:
    id: str = ''
    song_name: str = ''
    author_name: str = ''
    copyright: str = ''
    num_subtunes: int = 0


@dataclass
class GtPatternRow:
    note_data: int = GT_REST
    inst_num: int = 0
    command: int = 0
    command_data: int = 0


@dataclass
class GtInstrument:
    inst_num: int = 0
    attack_decay: int = 0
    sustain_release: int = 0
    wave_ptr: int = 0
    pulse_ptr: int = 0
    filter_ptr: int = 0
    vib_speedtable_ptr: int = 0
    vib_delay: int = 0
    gateoff_timer: int = 0x02
    hard_restart_1st_frame_wave: int = 0x09
    inst_name: str = ''


@dataclass
class GtTable:
    row_cnt: int = 0
    left_col: bytes = b''
    right_col: bytes = b''


class GTSong:
    """
    Contains parsed .sng data.
    """

    def __init__(self):
        self.headers = GtHeader()  #: goattracker file headers
        self.num_channels = 3  #: 3 or 6 voices
        self.subtune_orderlists = [[[], [], []]]  #: Nested lists: Subtunes->channels->orderlist
        self.instruments = []  #: list of GtInstrument instances
        self.wave_table = GtTable()  #: wave table
        self.pulse_table = GtTable()  #: pulse table
        self.filter_table = GtTable()  #: filter table
        self.speed_table = GtTable()  #: speed table
        self.patterns = [[]]  #: Nested lists: patterns->GtPatternRow instances

    def is_stereo(self):
        """
        Determines if this is stereo GoatTracker
        
        :return: True if stereo, False if not
        :rtype: boolean
        """
        return self.num_channels >= 4


# Convert pattern note byte value into midi note value
# Note: lowest goat tracker note C0 (0x60)
def pattern_note_to_midi_note(pattern_note_byte, octave_offset=0):
    return pattern_note_byte - (0x60 - C0_MIDI_NUM) + (octave_offset * 12)


# Convert midi note value into pattern note value
def midi_note_to_pattern_note(midi_note, octave_offset=0):
    return midi_note + (0x60 - C0_MIDI_NUM) + (-1 * octave_offset * 12)


def get_chars(in_bytes, trim_nulls=True):
    result = in_bytes.decode('Latin-1')
    if trim_nulls:
        result = result.strip('\0')  # no interpretation, preserve encoding
    return result


def get_order_list(an_index, file_bytes):
    # Note: orderlist length byte is length -1
    #    e.g. orderlist CHN1: "00 04 07 0d 09 RST00" in file as 06 00 04 07 0d 09 FF 00
    #    length-1 (06), followed by 7 bytes
    length = file_bytes[an_index] + 1  # add one for restart
    an_index += 1

    orderlist = file_bytes[an_index:an_index + length]
    an_index += length
    # check that next-to-last byte is $FF
    assert file_bytes[an_index - 2] == 255, "Error: Did not find expected $FF RST endmark in channel's orderlist"

    return orderlist


# Parse the wave, pulse, filter, or speed table
def get_table(an_index, file_bytes):
    rows = file_bytes[an_index]
    # no point in checking rows > GT_MAX_TABLE_LEN, since GT_MAX_TABLE_LEN is a $FF (max byte val)
    an_index += 1

    left_entries = file_bytes[an_index:an_index + rows]
    an_index += rows

    right_entries = file_bytes[an_index:an_index + rows]

    return GtTable(row_cnt=rows, left_col=left_entries, right_col=right_entries)


# If a 3-channel orderlist is found, returns the byte after the end, else return -1
def has_3_channel_orderlist(file_index, sng_bytes):
    for i in range(3):
        index_of_ff = sng_bytes[file_index]
        if sng_bytes[file_index + index_of_ff] != 0xff:
            return -1
        file_index += index_of_ff + 2
    return file_index


# Returns true if a 6-channel orderlist is found, evidence that this is a goattracker stereo sng file
def is_2sid(index_at_start_of_orderlist, sng_bytes):
    file_index = has_3_channel_orderlist(index_at_start_of_orderlist, sng_bytes)
    assert file_index != -1, "Error: could not parse orderlist"
    return has_3_channel_orderlist(file_index, sng_bytes) != -1


def import_sng_file_to_parsed_gt(input_filename):
    """
    Parse a goat tracker '.sng' file and put it into a GTSong instance.
    Supports 1SID and 2SID (stereo) goattracker '.sng' files.
    
    :param input_filename: Filename for input .sng file
    :type input_filename: string
    :return: A GTSong instance holding the parsed goattracker file
    :rtype: GTSong
    """
    with open(input_filename, 'rb') as f:
        sng_bytes = f.read()

    return import_sng_binary_to_parsed_gt(sng_bytes)


def import_sng_binary_to_parsed_gt(sng_bytes):
    """
    Parse a goat tracker '.sng' binary and put it into a GTSong instance.
    Supports 1SID and 2SID (stereo) goattracker '.sng' file binaries.
    
    :param sng_bytes: Binary contents of a sng file
    :type sng_bytes: bytes
    :return: A GTSong instance holding the parsed goattracker file
    :rtype: GTSong
    """
    a_song = GTSong()

    header = GtHeader()

    header.id = sng_bytes[0:4]
    assert header.id == GT_FILE_HEADER, "Error: Did not find magic header used by goattracker sng files"

    header.song_name = get_chars(sng_bytes[4:36])
    header.author_name = get_chars(sng_bytes[36:68])
    header.copyright = get_chars(sng_bytes[68:100])
    header.num_subtunes = sng_bytes[100]

    assert header.num_subtunes <= GT_MAX_SUBTUNES_PER_SONG, 'Error:  too many subtunes'

    file_index = 101
    a_song.headers = header

    # From goattracker documentation: (note: doesn't account for stereo sid)
    #    6.1.2 ChirpSong orderlists
    #    ---------------------
    #    The orderlist structure repeats first for channels 1,2,3 of first subtune,
    #    then for channels 1,2,3 of second subtune etc., until all subtunes
    #    have been gone thru.
    #
    #    Offset  Size    Description
    #    +0      byte    Length of this channel's orderlist n, not counting restart pos.
    #    +1      n+1     The orderlist data:
    #                    Values $00-$CF are pattern numbers
    #                    Values $D0-$DF are repeat commands
    #                    Values $E0-$FE are transpose commands
    #                    Value $FF is the RST endmark, followed by a byte that indicates
    #                    the restart position

    if is_2sid(file_index, sng_bytes):  # check if this is a "stereo" sid
        a_song.num_channels = 6

    subtune_orderlists = []
    for subtune_index in range(header.num_subtunes):
        channels_order_list = []
        for i in range(a_song.num_channels):
            channel_order_list = get_order_list(file_index, sng_bytes)
            file_index += len(channel_order_list) + 1
            channels_order_list.append(channel_order_list)
        subtune_orderlists.append(channels_order_list)
    a_song.subtune_orderlists = subtune_orderlists

    # From goattracker documentation:
    #    6.1.3 Instruments
    #    -----------------
    #    Offset  Size    Description
    #    +0      byte    Amount of instruments n
    #
    #    Then, this structure repeats n times for each instrument. Instrument 0 (the
    #    empty instrument) is not stored.
    #
    #    Offset  Size    Description
    #    +0      byte    Attack/Decay
    #    +1      byte    Sustain/Release
    #    +2      byte    Wavepointer
    #    +3      byte    Pulsepointer
    #    +4      byte    Filterpointer
    #    +5      byte    Vibrato param. (speedtable pointer)
    #    +6      byte    Vibraro delay
    #    +7      byte    Gateoff timer
    #    +8      byte    Hard restart/1st frame waveform
    #    +9      16      Instrument name

    instruments = [GtInstrument()]  # start with empty instrument number 0

    nonzero_inst_count = sng_bytes[file_index]
    file_index += 1

    for i in range(nonzero_inst_count):
        an_instrument = GtInstrument(attack_decay=sng_bytes[file_index], sustain_release=sng_bytes[file_index + 1],
                                     wave_ptr=sng_bytes[file_index + 2], pulse_ptr=sng_bytes[file_index + 3],
                                     filter_ptr=sng_bytes[file_index + 4],
                                     vib_speedtable_ptr=sng_bytes[file_index + 5], vib_delay=sng_bytes[file_index + 6],
                                     gateoff_timer=sng_bytes[file_index + 7],
                                     hard_restart_1st_frame_wave=sng_bytes[file_index + 8])
        file_index += 9

        an_instrument.inst_num = i + 1
        an_instrument.inst_name = get_chars(sng_bytes[file_index:file_index + 16])
        file_index += 16

        instruments.append(an_instrument)
    a_song.instruments = instruments

    # From goattracker documentation:
    #    6.1.4 Tables
    #    ------------
    #    This structure repeats for each of the 4 tables (wavetable, pulsetable,
    #    filtertable, speedtable).
    #
    #    Offset  Size    Description
    #    +0      byte    Amount n of rows in the table
    #    +1      n       Left side of the table
    #    +1+n    n       Right side of the table

    tables = []
    for i in range(4):
        a_table = get_table(file_index, sng_bytes)
        tables.append(a_table)
        file_index += a_table.row_cnt * 2 + 1

    (a_song.wave_table, a_song.pulse_table, a_song.filter_table, a_song.speed_table) = tables

    # From goattracker documentation:
    #    6.1.5 Patterns header
    #    ---------------------
    #    Offset  Size    Description
    #    +0      byte    Number of patterns n
    #
    #    6.1.6 Patterns
    #    --------------
    #    Repeat n times, starting from pattern number 0.
    #
    #    Offset  Size    Description
    #    +0      byte    Length of pattern in rows m
    #    +1      m*4     Groups of 4 bytes for each row of the pattern:
    #                    1st byte: Notenumber
    #                              Values $60-$BC are the notes C-0 - G#7
    #                              Value $BD is rest
    #                              Value $BE is keyoff
    #                              Value $BF is keyon
    #                              Value $FF is pattern end
    #                    2nd byte: Instrument number ($00-$3F)
    #                    3rd byte: Command ($00-$0F)
    #                    4th byte: Command databyte

    num_patterns = sng_bytes[file_index]
    file_index += 1
    patterns = []

    for pattern_num in range(num_patterns):
        a_pattern = []
        num_rows = sng_bytes[file_index]
        assert num_rows <= GT_MAX_ROWS_PER_PATTERN, "Too many rows in a pattern"
        file_index += 1
        for row_num in range(num_rows):
            a_row = GtPatternRow(note_data=sng_bytes[file_index], inst_num=sng_bytes[file_index + 1],
                                 command=sng_bytes[file_index + 2], command_data=sng_bytes[file_index + 3])
            assert (0x60 <= a_row.note_data < 0xBF) or a_row.note_data == GT_PAT_END, \
                "Error: unexpected note data value"
            assert a_row.inst_num <= GT_MAX_INSTR_PER_SONG, "Error: instrument number out of range"
            assert a_row.command <= 0x0F, "Error: command number out of range"
            file_index += 4
            a_pattern.append(a_row)
        patterns.append(a_pattern)

    a_song.patterns = patterns

    assert file_index == len(sng_bytes), "Error: bytes parsed didn't match file bytes length"
    return a_song


#
#
# Code to convert parsed gt file into rchirp
# 
#


PATTERN_END_ROW = GtPatternRow(note_data=GT_PAT_END)


# Used when "running" the channels to convert them to note on/off events in time
class GtChannelState:
    # The two funktable entries are shared by all channels using a funktempo, so we have it as a
    # class-side var.  Note, this approach won't work if we want GtChannelState instances belonging
    # to and processing different songs at the same time (seems unlikely).
    # TODO: ignoring multispeed considerations for now (would act as a simple multiplier for each)       
    funktable = GT_DEFAULT_FUNKTEMPOS

    def __init__(self, voice_num, channel_orderlist):
        self.voice_num = voice_num
        self.orderlist_index = -1  # -1 = bootstrapping value only, None = stuck in loop with no patterns
        self.row_index = -1  # -1 = bootstrapping value only
        self.pat_remaining_plays = 1  # default is to play a pattern once
        self.row_ticks_left = 1  # required value when bootstrapping
        self.first_tick_of_row = False
        self.curr_transposition = 0
        self.curr_note = None  # converted to midi note number
        self.row_has_note = False  # if True, curr_note is immediately set
        self.row_has_key_on = False  # gate bit mask on, reasserting last played note (found in self.curr_note)
        self.row_has_key_off = False  # gate bit mask off
        self.local_tempo_update = None
        self.global_tempo_update = None
        self.restarted = False  # channel has encountered restart one or more times
        self.channel_orderlist = channel_orderlist  # just this channel's orderlist from the subtune
        self.curr_funktable_index = None  # None = no funk tempos, 0 or 1 indicates current funktable index
        self.curr_tempo = GT_DEFAULT_TEMPO

        # position atop first pattern in orderlist for channel
        self.__inc_orderlist_to_next_pattern()

    # Advance channel/voice by a tick.  This will either:
    # 1) decrement a row's remaining ticks by one, or
    # 2) if the row's jiffies are spent, return the next row (if any)
    # Returns None if not returning a new row
    def next_tick(self, a_song):
        self.first_tick_of_row = False

        # If stuck in an orderlist loop that doesn't contain a pattern, then there's nothing to do
        if self.orderlist_index is None:
            return None

        self.row_ticks_left -= 1  # decrement ticks remaining in this row
        assert self.row_ticks_left >= 0, "Error: Can't have negative tick values"

        # if not advancing to a new row (0 ticks left), then we're done here
        if self.row_ticks_left > 0:
            return None

        new_row_duration = None
        self.inc_to_next_row(a_song.patterns)  # finished last pattern row, advance to the next
        # get the current row in the current pattern from this channel's orderlist
        row = copy.deepcopy(a_song.patterns[self.channel_orderlist[self.orderlist_index]][self.row_index])

        # If row contains a note, transpose if necessary (0 = no transform)
        if 0x60 <= row.note_data <= 0xBC:  # range $60 (C0) to $BC (G#7)
            note = row.note_data + self.curr_transposition
            assert note >= 0x60, "Error: transpose dropped note below midi C0"
            # According to docs, allowed to transpose +3 halfsteps above the highest note (G#7)
            #    that can be entered in the GT GUI, to create a B7
            assert note <= 0xBF, "Error: transpose raised note above midi B7"
            self.curr_note = pattern_note_to_midi_note(note)
            self.row_has_note = True

        # GT_REST ($BD/189, gt display "..."):  A note continues through rest rows.  Rest does not mean
        # what it would in sheet music.  For our purposes, we're ignoring it

        # GT_KEY_OFF ($BE/190, gt display "---"): Unsets the gate bit mask.  This starts the release phase
        # of the ADSR.
        # Going to ignore any effects gateoff timer and hardrestart values might have on perceived note end
        if row.note_data == GT_KEY_OFF:
            if self.curr_note is not None:
                self.row_has_key_off = True

        # GT_KEY_ON ($BF/191, gt display "+++"): Sets the gate bit mask (ANDed with data from the wavetable).
        # If no prior note has been started, then nothing will happen.  If a note is playing,
        # nothing will happen (to the note, to the instrument, etc.).  If a note was turned off,
        # this will restart it, but will not restart the instrument.
        if row.note_data == GT_KEY_ON:
            if self.curr_note is not None:
                self.row_has_key_on = True

        # Notes on funktempo (all this logic gleaned from reading through gplay.c)
        # 
        # Funktempo allows switching between two tempos on alternating pattern rows, to achieve
        # a "swing" or more organic feel.
        # - for non-multispeed songs, it defaults to 9 and 6 
        # 
        # The funktempo command is $E followed by an index to a single row in the speed table
        # - The left/right values in the speedtable row contain the two (alternating) tempo values
        # - Under the covers (in gplay.c), the array funktable[2] holds the two tempos
        #    - e.g., command E04 points to speedtable at index 4.  If the speedtable row contains
        #      01:09 06, then the alternating tempos are 9 and 6.  For a 4x-multispeed, these
        #      would need to be set instead to 01:24 18
        #    - the two values in funktable[] are global to all participating channels
        # - The command applies to all channels (3 or 6 for stereo) and all channels are set to
        #   tempo 0
        # 
        # The tempo command is $F, and "tempos" $00 and $01 change all channels to the tempo that's
        # been previously set in funktable[0] or funktable[1] respectively, and every subsequent
        # row will alternate between the [0] and [1] entries of the funktable.  In otherwords,
        # you can choose which half of the funktempo to start with.
        # - Values $80 and $81 are like $00 and $01, but apply funktempo to just the current channel
        # - Since the $E command sets all tempos to 0 (see above), it will always start with
        #   funktable[0]'s tempo (set by the left-side entry in the speed table).  But $F can choose
        #   to start with the (previously-set) first or second value in the funktempo pair.

        if row.command == 0x0E:  # funktempo command
            speed_table_index = row.command_data
            if speed_table_index > a_song.speed_table.row_cnt:
                raise ChiptuneSAKContentError("Error: speed table index %d too big for table of size %d"
                                              % (speed_table_index, a_song.speed_table.row_cnt))

            # look up the two funk tempos in the speed table and set the channel-shared funktable
            speed_table_index -= 1  # convert to zero-indexing
            GtChannelState.funktable[0] = a_song.speed_table.left_col[speed_table_index]
            GtChannelState.funktable[1] = a_song.speed_table.right_col[speed_table_index]

            new_row_duration = GtChannelState.funktable[0]

            # Record global funktempo change
            self.global_tempo_update = 0  # 0 will later become the tempo in funktable entry 0
        elif row.command == GT_TEMPO_CHNG_CMD:
            # From docs:
            #    Values $03-$7F set tempo on all channels, values $83-$FF only on current channel (subtract
            #    $80 to get actual tempo). Tempos $00-$01 recall the funktempo values set by EXY command.

            # Note: The higher voice number seems to win ties on simultaneous speed changes

            assert row.command_data not in [0x02, 0x82], \
                "TODO: Don't know how to support tempo change with value %d" % row.command_data

            new_row_duration = row.command_data & 127  # don't care if it's global or local
            if new_row_duration < 2:
                new_row_duration = GtChannelState.funktable[new_row_duration]

            # Record global tempo change
            #   From looking at the gt source code (at least for the goat tracker gui's gplay.c)
            #   when a CMD_SETTEMPO happens (for one or for all three/six channels), the tempos immediately
            #   change, but the ticks remaining on each channel's current row (in progress) is left alone --
            #   another detail that would have been nice to have had in the documentation.
            if 0x03 <= row.command_data <= 0x7F:
                self.global_tempo_update = row.command_data

            # Record tempo change for just the given channel
            if 0x83 <= row.command_data <= 0xFF:
                self.local_tempo_update = row.command_data - 0x80

                # Record global funktempo change (funktable tempo entry 0 or 1)
            if 0x00 <= row.command_data <= 0x01:
                self.global_tempo_update = row.command_data

            # Record funktempo change for just the given channel (funktable tempo entry 0 or 1)
            if 0x80 <= row.command_data <= 0x81:
                self.global_tempo_update = row.command_data - 0x80
        else:
            # given no tempo command on this row (0x0E or 0x0F), if we're in funktempo mode, time to alternate
            # our funktempo
            if self.curr_funktable_index is not None:
                self.curr_funktable_index ^= 1
                self.local_tempo_update = self.curr_funktable_index
                new_row_duration = GtChannelState.funktable[self.curr_funktable_index]

        # init duration of this row
        # (if it hasn't started to count down, a row's init duration can get overwritten by
        # another channel's global temp setting, performed later in this code)
        if new_row_duration is not None:
            self.row_ticks_left = new_row_duration
        else:
            self.row_ticks_left = self.curr_tempo

        # TODO: Possibly handle some of the (below) commands in the future?
        # from docs:
        #    Command 1XY: Portamento up. XY is an index to a 16-bit speed value in the speedtable.
        #
        #    Command 2XY: Portamento down. XY is an index to a 16-bit speed value in the speedtable.
        #
        #    Command 3XY: Toneportamento. Raise or lower pitch until target note has been reached. XY is an index
        #    to a 16-bit speed value in the speedtable, or $00 for "tie-note" effect (move pitch instantly to
        #    target note)
        #
        #    Command DXY: Set mastervolume to Y, if X is $0. If X is not $0, value XY is
        #    copied to the timing mark location, which is playeraddress+$3F.    

        return row

    # Advance to next row in pattern.  If pattern end, then go to row 0 of next pattern in orderlist
    def inc_to_next_row(self, patterns):
        self.row_index += 1  # init val is -1
        self.row_has_note = self.row_has_key_on = self.row_has_key_off = False
        self.local_tempo_update = self.global_tempo_update = None
        self.first_tick_of_row = True
        row = patterns[self.channel_orderlist[self.orderlist_index]][self.row_index]
        if row == PATTERN_END_ROW:
            self.pat_remaining_plays -= 1
            assert self.pat_remaining_plays >= 0, "Error: negative number of remaining plays for pattern"
            self.row_index = 0  # all patterns are guaranteed to start with at least one meaningful (not end mark) row
            if self.pat_remaining_plays == 0:  # all done with this pattern, moving on
                self.__inc_orderlist_to_next_pattern()

    def __inc_orderlist_to_next_pattern(self):
        self.pat_remaining_plays = 1  # patterns default to one playthrough unless otherwise specified
        while True:
            self.orderlist_index += 1  # bootstraps at -1
            a_byte = self.channel_orderlist[self.orderlist_index]

            # parse transpose
            # Transpose is in half steps.  Transposes changes are absolute, not additive.
            #   If transpose combined with repeat, transpose must come before a repeat
            #   Testing shows transpose ranges from '-F' (225) to '+E' (254) in orderlist
            #   Bug in goattracker documentation: says range is $E0 (224) to $FE (254)
            #   I'm assuming byte 224 is never used in orderlists
            assert a_byte != 0xE0, "TODO: I don't believe byte E0 should occur in the orderlist"
            if 0xE1 <= a_byte <= 0xFE:  # F0 = +0 = no transposition
                self.curr_transposition = a_byte - 0xF0  # transpose range is -15 to +14
                continue

            # parse repeat
            # Repeat values 1 to 16.  In tracker, instead of R0..RF, it's R1..RF,R0
            #   i.e., 'R0'=223=16reps, 'RF'=222=15 reps, 'R1'=208=1rep
            # Note:  Repeat n really means repeat n-1, so it's actually "number of times to play"
            #    So R1 (repeat 1) is essentially a NOP
            if 0xD0 <= a_byte <= 0xDF:
                self.pat_remaining_plays = a_byte - 0xCF
                continue

            # parse RST (restart)
            if a_byte == GT_OL_RST:  # RST ($FF)
                self.restarted = True

                start_index = self.channel_orderlist[
                    self.orderlist_index + 1]  # byte following RST is orderlist restart index
                end_index = self.orderlist_index  # byte containing RST
                self.orderlist_index = self.channel_orderlist[self.orderlist_index + 1]  # perform orderlist "goto" jump
                # check if there's at least one pattern between the restart location and the RST
                if sum(1 for p in self.channel_orderlist[start_index:end_index] if p < GT_MAX_PATTERNS_PER_SONG) == 0:
                    self.orderlist_index = None
                    break  # no pattern to ultimately end up on, so we're done
                # continue loop, just in case we land on a repeat or transpose that needs resolving
                self.orderlist_index -= 1  # "undo" +1 at start of loop
                continue

                # parse pattern
            if a_byte < GT_MAX_PATTERNS_PER_SONG:  # if it's a pattern
                break  # found one, done parsing

            raise ChiptuneSAKException("Error: found uninterpretable value %d in orderlist" % a_byte)


def import_parsed_gt_to_rchirp(sng_data, subtune_num=0):
    """
    Convert the parsed goattracker file into rchirp 
    
    :param sng_data: Parsed goattracker file
    :type sng_data: GTSong
    :param subtune_num: The subtune number to convert to rchirp, defaults to 0
    :type subtune_num: int, optional
    :return: rchirp song instance
    :rtype: RChirpSong
    """

    # init state holders for each channel to use as we step through each tick (aka jiffy aka frame)
    channels_state = [GtChannelState(i + 1, sng_data.subtune_orderlists[subtune_num][i])
                      for i in range(sng_data.num_channels)]

    rchirp_song = ctsRChirp.RChirpSong()
    # This is instead of channels_time_events (TODO: delete this comment later)
    rchirp_song.voices = [ctsRChirp.RChirpVoice(rchirp_song) for i in range(sng_data.num_channels)]

    # TODO: Later, make track assignment to SID groupings not hardcoded
    if sng_data.is_stereo:
        rchirp_song.voice_groups = [(1, 2, 3), (4, 5, 6)]
    else:
        rchirp_song.voice_groups = [(1, 2, 3)]

        # Handle the rarely-used sneaky default global tempo setting
    # from docs:
    #    For very optimized songdata & player you can refrain from using any pattern
    #    commands and rely on the instruments' step-programming. Even in this case, you
    #    can set song startup default tempo with the Attack/Decay parameter of the last
    #    instrument (63/0x3F), if you otherwise leave this instrument unused.

    # TODO: This code block is untested
    if len(sng_data.instruments) == GT_MAX_INSTR_PER_SONG:
        ad = sng_data.instruments[GT_MAX_INSTR_PER_SONG - 1].attack_decay
        if 0x03 <= ad <= 0x7F:
            for cs in channels_state:
                cs.curr_tempo = ad

    global_tick = -1
    # Step through each tick.  For each tick, evaluate the state of each channel.
    # Continue until all channels have hit the end of their respective orderlists
    while not all(cs.restarted for cs in channels_state):
        # When not using multispeed, tempo = ticks per row = screen refreshes per row.
        # 'Ticks' on C64 are also 'frames' or 'jiffies'.  Each tick in PAL is around 20ms,
        # and ~16.7‬ms on NTSC.
        # (in contrast, for a multispeed of 2, there would be two music updates per frame)
        global_tick += 1
        global_tempo_change = None

        for i, cs in enumerate(channels_state):
            # Either reduce time left on this row, or get the next new goattracker data row
            gt_row = cs.next_tick(sng_data)
            if gt_row is None:  # if we didn't advance to a new row...
                continue

            rc_row = ctsRChirp.RChirpRow()
            rc_row.jiffy_num = global_tick
            rc_row.jiffy_len = cs.curr_tempo

            # KeyOff (only recorded if there's a curr_note defined)
            if cs.row_has_key_off:
                rc_row.note_num = cs.curr_note
                rc_row.gate = False

            # KeyOn (only recorded if there's a curr_note defined)
            if cs.row_has_key_on:
                rc_row.note_num = cs.curr_note
                rc_row.gate = True

            # if note_data is an actual note, then cs.curr_note has been updated
            elif cs.row_has_note:
                rc_row.note_num = cs.curr_note
                rc_row.gate = True

                # process tempo changes
            # Note: local_tempo_update and global_tempo_update init to None when new row fetched
            if cs.local_tempo_update is not None:
                # Apply local (single channel) tempo change
                if cs.local_tempo_update >= 2:
                    cs.curr_funktable_index = None
                    cs.curr_tempo = cs.local_tempo_update
                else:  # it's an index to a funktable tempo
                    cs.curr_funktable_index = cs.local_tempo_update
                    # convert into a normal tempo change
                    cs.curr_tempo = GtChannelState.funktable[cs.curr_funktable_index]
                rc_row.jiffy_len = cs.curr_tempo

            # this channel signals a global tempo change that will affect all the channels
            # once out of this per-channel loop
            elif cs.global_tempo_update is not None:
                global_tempo_change = cs.global_tempo_update

            rchirp_song.voices[i].append_row(rc_row)

        # By this point, we've passed through all channels for this particular tick
        # If more than one channel made a tempo change, the global tempo change on the highest
        # voice/channel number wins (consistent with goattracker behavior)
        if global_tempo_change is not None:
            for j, cs in enumerate(channels_state):  # Time to apply the global changes:
                if global_tempo_change >= 2:
                    cs.curr_funktable_index = None  # funk tempo mode off
                    new_tempo = global_tempo_change
                else:  # it's an index to a funktable tempo
                    cs.curr_funktable_index = global_tempo_change  # stateful funky tracking
                    # convert into a normal tempo change
                    new_tempo = GtChannelState.funktable[cs.curr_funktable_index]

                current_rc_row = rchirp_song.voices[j].get_last_row()

                # If row state is in progress, leave its remaining ticks alone.
                # But if it's the very start of a new row, then override with the new global tempo
                if cs.first_tick_of_row:
                    cs.row_ticks_left = new_tempo
                    current_rc_row.jiffy_len = new_tempo

                cs.curr_tempo = new_tempo

    # Create note offs once all channels have hit their orderlist restart one or more times
    #    Ok, cheesy hack here.  The loop above repeats until all tracks have had a chance to restart, but it
    #    allows each voice to load in one row after that point.  Taking advantage of that, we modify that
    #    row with note off events, looking backwards to previous rows to see what the last note was to use
    #    in the note off events.
    for i, cs in enumerate(channels_state):
        rows = rchirp_song.voices[i].rows
        reversed_index = list(reversed(list(rows.keys())))
        for seek_index in reversed_index[1:]:  # skip largest row num, and work backwards
            if rows[seek_index].note_num is not None:
                rows[reversed_index[0]].note_num = rows[seek_index].note_num
                rows[reversed_index[0]].gate = False  # gate off
                break

    # In rchirp (as of right now), all tempo changes are specific to each channel, even if the
    # tempo change was originally global.  This can can lead to lots of tempo changes when
    # unrolling a global funk tempo.
    for voice in rchirp_song.voices:
        prev_tempo = -1
        for rchirp_row in voice.get_sorted_rows():
            if rchirp_row.jiffy_len != prev_tempo:
                rchirp_row.new_jiffy_tempo = rchirp_row.jiffy_len
                prev_tempo = rchirp_row.jiffy_len

    # TODO: There is not yet generalized handling for instruments when creating output goattracker
    # binaries.  This code will just stub in a default instrument for each voice on that voice's
    # first note (if any).
    for voice in rchirp_song.voices:
        for rchirp_row in voice.get_sorted_rows():
            if rchirp_row.note_num is not None and rchirp_row.new_instrument is None:
                rchirp_row.new_instrument = DEFAULT_INSTRUMENT
                break

    # Before returning the rchirp song, might as well make use of our test cases here
    rchirp_song.integrity_check()  # Will throw assertions if there are any problems
    assert rchirp_song.is_contiguous(), "Error: rchirp representation should not be sparse"

    return rchirp_song


#
#
# Code to convert rchirp to goattracker file
#
#

PATTERN_EMPTY_ROW = GtPatternRow(note_data=GT_REST)

TRUNCATE_IF_TOO_BIG = True


# A Procrustean bed for GT text fields.  Can accept a string or bytes.
def pad_or_truncate(to_pad, length):
    if isinstance(to_pad, str):
        to_pad = to_pad.encode('latin-1')
    return to_pad.ljust(length, b'\0')[0:length]


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


def export_rchirp_to_gt(rchirp_song, output_filename, end_with_repeat=False, compress=False, pattern_len=126):
    """
    Convert rchirp into a goattracker .sng file.
    
    :param output_filename: Output path and filename
    :type output_filename: string
    :param rchirp_song: The rchirp song to convert
    :type rchirp_song: RChirpSong
    :param end_with_repeat: True if song should repeat when finished, defaults to False
    :type end_with_repeat: bool, optional
    :param compress: True if to create reusable patterns, defaults to False
    :type compress: bool, optional
    :param pattern_len: Maximum pattern lengths to create
    :type pattern_len: int, optional
    """
    binary = export_rchirp_to_gt_binary(rchirp_song, end_with_repeat, compress, pattern_len)
    with open(output_filename, 'wb') as out_file:
        out_file.write(binary)


def export_rchirp_to_gt_binary(rchirp_song, end_with_repeat=False, compress=False, pattern_len=126):
    """
    Convert rchirp into a goattracker .sng binary.
    
    :param rchirp_song: The rchirp song to convert
    :type rchirp_song: RChirpSong
    :param end_with_repeat: True if song should repeat when finished, defaults to False
    :type end_with_repeat: bool, optional
    :param compress: True if to create reusable patterns, defaults to False
    :type compress: bool, optional
    :param pattern_len: Maximum pattern lengths to create
    :type pattern_len: int, optional
    """

    is_stereo = len(rchirp_song.voices) >= 4
    if len(rchirp_song.voices) > 6:
        raise ChiptuneSAKContentError("Error: Stereo SID can only support up to 6 voices")

    if is_stereo:
        num_channels = 6
    else:
        num_channels = 3

    patterns = []  # can be shared across all channels
    orderlists = [[] for _ in range(num_channels)]  # Note: this is bad: [[]] * len(tracknums)

    if compress:
        exit("Sorry, generating patterns to support reuse has not been implemented yet")
    else:
        # Convert the sparse representation into separate patterns (of bytes)
        curr_pattern_num = 0
        too_many_patterns = False

        # for each channel, get its rows, and create patterns, adding them to the 
        # channel's orderlist
        for i, rchirp_voice in enumerate(rchirp_song.voices):
            rchirp_rows = rchirp_voice.rows
            pattern_row_index = 0
            pattern = bytearray()  # create a new, empty pattern
            # TODO: Instead of max, range, and in, just do a sort
            max_row = max(rchirp_rows)
            prev_instrument = 1  # TODO: Default instrument 1, this must be generalized

            # Iterate across row num span (inclusive).  Would normally iterated over
            # sorted rchirp_rows dict keys, but since rchirp is allowed to be sparse
            # we're being careful here to insert an empty row for missing row num keys
            for j in range(max_row + 1):

                # Convert each rchirp_row into the gt_row (used for binary gt row representation)
                if j in rchirp_rows:
                    rchirp_row = rchirp_rows[j]
                    gt_row = GtPatternRow()

                    if rchirp_row.gate:  # if starting a note
                        gt_row.note_data = midi_note_to_pattern_note(rchirp_row.note_num)

                        # only bother to populate instrument if there's a new note
                        if rchirp_row.new_instrument is not None:
                            gt_row.inst_num = rchirp_row.new_instrument
                            prev_instrument = rchirp_row.new_instrument
                        else:
                            # unlike SID-Wizard which only asserts instrument changes (on any row),
                            # goattracker asserts the current instrument with every note
                            # (goattracker can assert instrument without note, but that's a NOP)
                            gt_row.inst_num = prev_instrument

                    elif rchirp_row.gate is False:  # if ending a note ('false' check because tri-state)
                        gt_row.note_data = GT_KEY_OFF

                    if rchirp_row.new_jiffy_tempo is not None:
                        gt_row.command = GT_TEMPO_CHNG_CMD
                        # insert local channel tempo change
                        gt_row.command_data = rchirp_row.new_jiffy_tempo + 0x80
                    pattern += row_to_bytes(gt_row)
                else:
                    pattern += row_to_bytes(PATTERN_EMPTY_ROW)

                pattern_row_index += 1
                # pattern_len notes: index 0 to len-1 for data, index len for 0xFF pattern end mark
                if pattern_row_index == pattern_len:  # if pattern is full
                    pattern += row_to_bytes(PATTERN_END_ROW)  # finish with end row marker
                    patterns.append(pattern)
                    orderlists[i].append(curr_pattern_num)  # append to orderlist for this channel
                    curr_pattern_num += 1
                    if curr_pattern_num >= GT_MAX_PATTERNS_PER_SONG:
                        too_many_patterns = True
                        break
                    pattern = bytearray()
                    pattern_row_index = 0
            if too_many_patterns:
                break
            if len(pattern) > 0:  # if there's a final partially-filled pattern, add it
                pattern += row_to_bytes(PATTERN_END_ROW)
                patterns.append(pattern)
                orderlists[i].append(curr_pattern_num)
                curr_pattern_num += 1
                if curr_pattern_num >= GT_MAX_PATTERNS_PER_SONG:
                    too_many_patterns = True
        if too_many_patterns:
            if TRUNCATE_IF_TOO_BIG:
                print("Warning: too much note data, truncated patterns")
            else:
                raise ChiptuneSAKContentError("Error: More than %d goattracker patterns created"
                                              % GT_MAX_PATTERNS_PER_SONG)

    # Usually, songs repeat.  Each channel's orderlist ends with RST00, which means restart at the
    # 1st entry in that channel's pattern list (note: orderlist is normally full of pattern numbers,
    # but the number after RST is not a pattern number, but an index back into that channel's orderlist)
    # As far as I can tell, people create an infinite loop at the end when they don't want a song to
    # repeat, so that's what this code can do.

    # end_with_repeat == False in no way implies that all tracks will restart at the same time...
    if not end_with_repeat and not too_many_patterns:
        # create a new empty pattern for all channels to loop on forever
        # and add to the end of each orderlist
        loop_pattern = bytearray()
        loop_pattern += row_to_bytes(GtPatternRow(note_data=GT_KEY_OFF))
        loop_pattern += row_to_bytes(PATTERN_END_ROW)
        patterns.append(loop_pattern)
        loop_pattern_num = len(patterns) - 1
        for i in range(num_channels):
            orderlists[i].append(loop_pattern_num)

    for i in range(num_channels):
        orderlists[i].append(GT_OL_RST)  # patterns end with restart indicator
        if end_with_repeat:
            orderlists[i].append(0)  # index of start of channel order list
        else:
            orderlists[i].append(len(orderlists[i]) - 2)  # index of the empty loop pattern

    gt_binary = bytearray()

    # append headers to gt binary
    gt_binary += GT_FILE_HEADER
    gt_binary += pad_or_truncate(rchirp_song.metadata.name, 32)
    gt_binary += pad_or_truncate(rchirp_song.metadata.composer, 32)
    gt_binary += pad_or_truncate(rchirp_song.metadata.copyright, 32)
    gt_binary.append(0x01)  # number of subtunes

    # append orderlists to gt binary
    for i in range(num_channels):
        gt_binary.append(len(orderlists[i]) - 1)  # orderlist length minus 1
        gt_binary += bytes(orderlists[i])

    # append instruments
    # TODO: At some point, should add support for loading gt .ins instrument files for the channels
    # Need an instrument
    # For now, just going to design a simple triangle sound as instrument number 1.
    # This requires setting ADSR, and a wavetable position of 01.
    # Then a wavetable with the entires 01:11 00, and 02:FF 00 
    gt_binary.append(0x01)  # number of instruments (not counting NOP instrument 0)
    gt_binary += instrument_to_bytes(GtInstrument(inst_num=DEFAULT_INSTRUMENT,
                                                  attack_decay=0x22, sustain_release=0xFA, wave_ptr=0x01,
                                                  inst_name='simple triangle'))
    # TODO: In the future, more instruments appended here (in instrument number order)

    # append tables
    # TODO: Currently hardcoded: tables for DEFAULT_INSTRUMENT:
    gt_binary.append(0x02)  # wavetable with two row entries
    gt_binary += bytes([0x11, 0xFF, 0x00, 0x00])  # simple triangle instrument waveform

    gt_binary.append(0x00)  # length 0 pulsetable

    gt_binary.append(0x00)  # length 0 filtertable

    gt_binary.append(0x00)  # length 0 speedtable

    # append patterns
    gt_binary.append(len(patterns))  # number of patterns
    for pattern in patterns:
        assert len(pattern) % 4 == 0, "Error: unexpected pattern byte length"
        gt_binary.append(len(pattern) // 4)  # length of pattern in rows
        gt_binary += pattern

    return gt_binary
