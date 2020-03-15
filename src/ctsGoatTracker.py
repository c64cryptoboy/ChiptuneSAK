# Code to import and export goattracker .sng files (both regular and stereo)
# 
# Notes:
# - Multispeed updates the music multiple times per frame.  This means different things in
#   different trackers.  In SID-Wizard, only the tables (waveform, pulse, and filter) are
#   affected, but the onset of new notes only happens on frame boundaries.  In GoatTracker,
#   the entire engine is driven faster, requiring speedtable values (e.g. tempos) and
#   gateoff timers to be multiplied by the multispeed factor.
#   This code ignores multispeed (for now)
#
# TODOs:
# - Add instrument file loader to use with channels on exports
# - recode gt->sparse timestamp columns->chirp as gt->columns with jiffy duration->rchirp->chirp
# - recode chirp->gt as chirp->rchirp and rchirp->gt

from os import path
import sys
import argparse
import copy
import math
from fractions import Fraction
from functools import reduce, partial
from dataclasses import dataclass
from collections import defaultdict
from ctsConstants import ARCH, C0_MIDI_NUM
import ctsChirp
import ctsRChirp
import ctsMidi
from ctsErrors import ChiptuneSAKException, ChiptuneSAKQuantizationError, \
    ChiptuneSAKContentError, ChiptuneSAKPolyphonyError


# GoatTracker constants
GT_FILE_HEADER = b'GTS5'
GT_DEFAULT_TEMPO = 6
GT_DEFAULT_FUNKTEMPOS = [9,6] # default alternating tempos, from gplay.c

# All these MAXes are the same for goattracker 2 (1SID) and goattracker 2 stereo (2SID)
# (Note: MAXes vary in the SID-Wizard 1SID, 2SID, and 3SID engines)
# Most found in gcommon.h
GT_MAX_SUBTUNES_PER_SONG = 32 # Each subtune gets its own orderlist of patterns
                              # "song" means a collection of independently-playable subtunes
GT_MAX_ELM_PER_ORDERLIST = 255 # at minimum, it must contain the endmark and following byte
GT_MAX_INSTR_PER_SONG = 63
GT_MAX_PATTERNS_PER_SONG = 208 # patterns can be shared across channels and subtunes
GT_MAX_ROWS_PER_PATTERN = 128 # and min rows (not including end marker) is 1
GT_MAX_TABLE_LEN = 255

GT_REST = 0xBD # A rest in goattracker means NOP, not rest
GT_KEY_OFF = 0xBE
GT_KEY_ON = 0xBF
GT_OL_RST = 0xFF # order list restart marker
GT_PAT_END = 0xFF # pattern end

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
    def __init__(self):
        self.headers = GtHeader()
        self.num_channels = 3 # 6 for "stereo"  
        self.subtune_orderlists =  [[[],[],[]]] # [subtune][channel_index0-2][orderlist_byte_index]
        self.instruments = [] # list of GtInstrument instances
        self.wave_table = GtTable()
        self.pulse_table = GtTable()
        self.filter_table = GtTable()
        self.speed_table = GtTable()
        self.patterns = [[]] # list of patterns, each of which is an list of GtPatternRow instances

    def is_stereo(self):
        return self.num_channels >= 4

# Convert pattern note byte value into midi note value
# Note: lowest goat tracker note C0 (0x60)
def pattern_note_to_midi_note(pattern_note_byte, octave_offset = 0):
    return pattern_note_byte - (0x60 - C0_MIDI_NUM) + (octave_offset * 12)


# Convert midi note value into pattern note value
def midi_note_to_pattern_note(midi_note, octave_offset = 0):
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


def import_sng(gt_filename):
    """ 
    Parse a goat tracker .sng file and put it into a GTSong instance
  
    Supports 1SID and 2SID (stereo) goattracker .sng files 
  
    Parameters: 
       gt_filename (string): Filename for input .sng file
  
    Returns: 
       GTSong: A GTSong instance holding the parsed goattracker file
    """
    with open(gt_filename, 'rb') as f:
        sng_bytes = f.read()

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

    if is_2sid(file_index, sng_bytes): # check if this is a "stereo" sid
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

    instruments = []
    instruments.append(GtInstrument())  # start with empty instrument number 0

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
            assert (0x60 <= a_row.note_data < 0xBF) or a_row.note_data == GT_PAT_END, "Error: unexpected note data value"
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
# Code to convert parsed gt file into events in time
# 
#


# TimeEntry are values, keys will be jiffy # (since time 0)
# Over time, might add other commands to this as well (Portamento, etc.)
@dataclass
class TimeEntry:
    note: int = None
    note_on: bool = None # True/False/None
    tempo: int = None

PATTERN_END_ROW = GtPatternRow(note_data = GT_PAT_END)

# Used when "running" the channels to convert them to note on/off events in time
class GtChannelState:
    # The two funktable entries are shared by all channels using a funktempo, so we have it as a
    # class-side var.  Note, this approach won't work if we want GtChannelState instances belonging
    # to and processing different songs at the same time (seems unlikely).
    # TODO: ignoring multispeed considerations for now (would act as a simple multiplier for each)       
    funktable = GT_DEFAULT_FUNKTEMPOS 

    def __init__(self, voice_num, channel_orderlist):
        self.voice_num = voice_num
        self.orderlist_index = -1 # -1 = bootstrapping value only, None = stuck in loop with no patterns
        self.row_index = -1 # -1 = bootstrapping value only
        self.pat_remaining_plays = 1 # default is to play a pattern once
        self.row_ticks_left = 1 # required value when bootstrapping
        self.first_tick_of_row = False
        self.curr_transposition = 0
        self.curr_note = None # converted to midi note number
        self.row_has_note = False # if True, curr_note is immediately set
        self.row_has_key_on = False # gate bit mask on, reasserting last played note (found in self.curr_note)
        self.row_has_key_off = False # gate bit mask off
        self.local_tempo_update = None
        self.global_tempo_update = None
        self.restarted = False # channel has encountered restart one or more times
        self.channel_orderlist = channel_orderlist # just this channel's orderlist from the subtune
        self.curr_funktable_index = None # None = no funk tempos, 0 or 1 indicates current funktable index
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

        self.row_ticks_left -= 1 # decrement ticks remaining in this row
        assert self.row_ticks_left >=0, "Error: Can't have negative tick values"

        # if not advancing to a new row (0 ticks left), then we're done here
        if self.row_ticks_left > 0:
            return None
        
        new_row_duration = None
        self.inc_to_next_row(a_song.patterns) # finished last pattern row, advance to the next
        # get the current row in the current pattern from this channel's orderlist
        row = copy.deepcopy(a_song.patterns[self.channel_orderlist[self.orderlist_index]][self.row_index])

        # If row contains a note, transpose if necessary (0 = no transform)
        if 0x60 <= row.note_data <= 0xBC: # range $60 (C0) to $BC (G#7)
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

        if row.command == 0x0E: # funktempo command
            speed_table_index = row.command_data
            if speed_table_index > a_song.speed_table.row_cnt:
                raise ChiptuneSAKContentError("Error: speed table index %d too big for table of size %d" \
                    % (speed_table_index, a_song.speed_table.row_cnt))

            # look up the two funk tempos in the speed table and set the channel-shared funktable
            speed_table_index -= 1 # convert to zero-indexing
            GtChannelState.funktable[0] = a_song.speed_table.left_col[speed_table_index]
            GtChannelState.funktable[1] = a_song.speed_table.right_col[speed_table_index]

            new_row_duration = GtChannelState.funktable[0]

            # Record global funktempo change
            self.global_tempo_update = 0 # 0 will later become the tempo in funktable entry 0
        elif row.command == 0x0F: # tempo change
            # From docs:
            #    Values $03-$7F set tempo on all channels, values $83-$FF only on current channel (subtract
            #    $80 to get actual tempo). Tempos $00-$01 recall the funktempo values set by EXY command.

            # Note: The higher voice number seems to win ties on simultaneous speed changes

            assert row.command_data not in [0x02, 0x82] \
                , "TODO: Don't know how to support tempo change with value %d" % (row.command_data)     

            new_row_duration = row.command_data & 127 # don't care if it's global or local
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
                self.global_tempo_update = row.command_data  - 0x80
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
        self.row_index += 1 # init val is -1
        self.row_has_note = self.row_has_key_on = self.row_has_key_off = False 
        self.local_tempo_update = self.global_tempo_update = None
        self.first_tick_of_row = True
        row = patterns[self.channel_orderlist[self.orderlist_index]][self.row_index]
        if row == PATTERN_END_ROW:
            self.pat_remaining_plays -= 1
            assert self.pat_remaining_plays >= 0, "Error: cannot have a negative number of remaining plays for a pattern"
            self.row_index = 0 # all patterns are guaranteed to start with at least one meaningful (not end mark) row
            if self.pat_remaining_plays == 0: # all done with this pattern, moving on
                self.__inc_orderlist_to_next_pattern()


    def __inc_orderlist_to_next_pattern(self):
        self.pat_remaining_plays = 1 # patterns default to one playthrough unless otherwise specified
        while(True):
            self.orderlist_index += 1 # bootstraps at -1
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

                start_index = self.channel_orderlist[self.orderlist_index+1] # byte following RST is orderlist restart index
                end_index = self.orderlist_index # byte containing RST
                self.orderlist_index = self.channel_orderlist[self.orderlist_index+1] # perform orderlist "goto" jump
                # check if there's at least one pattern between the restart location and the RST
                if sum(1 for p in self.channel_orderlist[start_index:end_index] if p < GT_MAX_PATTERNS_PER_SONG) == 0:
                    self.orderlist_index = None
                    break # no pattern to ultimately end up on, so we're done
                # continue loop, just in case we land on a repeat or transpose that needs resolving
                self.orderlist_index -= 1 #"undo" +1 at start of loop
                continue 

            # parse pattern
            if a_byte < GT_MAX_PATTERNS_PER_SONG: # if it's a pattern
                break # found one, done parsing

            raise ChiptuneSAKException("Error: found uninterpretable value %d in orderlist" % a_byte)


# TODO: Delete convert_to_note_events() once the rchirp conversion is finished

# Convert the orderlist and patterns into three (or six) channels of note on/off events in time (ticks)
def convert_to_note_events(sng_data, subtune_num):
    # init state holders for each channel to use as we step through each tick (aka jiffy aka frame)
    channels_state = [GtChannelState(i+1, sng_data.subtune_orderlists[subtune_num][i]) for \
        i in range(sng_data.num_channels)]
    channels_time_events = [defaultdict(TimeEntry) for i in range(sng_data.num_channels)]

    # Handle the rarely-used sneaky default global tempo setting
    # from docs:
    #    For very optimized songdata & player you can refrain from using any pattern
    #    commands and rely on the instruments' step-programming. Even in this case, you
    #    can set song startup default tempo with the Attack/Decay parameter of the last
    #    instrument (63/0x3F), if you otherwise leave this instrument unused.

    # TODO: This code block is untested
    if len(sng_data.instruments) == GT_MAX_INSTR_PER_SONG:
        ad = sng_data.instruments[GT_MAX_INSTR_PER_SONG-1].attack_decay
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
            channel_time_events = channels_time_events[i]

            # Either reduce time left on this row, or get the next new row
            row = cs.next_tick(sng_data)
            if row is None:  # if we didn't advance to a new row
                continue

            #print("Debug: new row tick %d voice %d" %(global_tick, i))

            # KeyOff (only recorded if there's a curr_note defined)
            if cs.row_has_key_off:
                channel_time_events[global_tick].note = cs.curr_note
                channel_time_events[global_tick].note_on = False

            # KeyOn (only recorded if there's a curr_note defined)
            if cs.row_has_key_on:
                channel_time_events[global_tick].note = cs.curr_note
                channel_time_events[global_tick].note_on = True

            # if note_data is an actual note
            elif cs.row_has_note:
                channel_time_events[global_tick].note = cs.curr_note
                channel_time_events[global_tick].note_on = True
            
            # process tempo changes
            # Note: local_tempo_update and global_tempo_update init to None when new row fetched
            if cs.local_tempo_update is not None:
                # Apply local (single channel) tempo change
                if cs.local_tempo_update >= 2:
                    cs.curr_funktable_index = None
                    cs.curr_tempo = cs.local_tempo_update
                else: # it's an index to a funktable tempo
                    cs.curr_funktable_index = cs.local_tempo_update
                    # convert into a normal tempo change
                    cs.curr_tempo = GtChannelState.funktable[cs.curr_funktable_index]
                channel_time_events[global_tick].tempo = cs.curr_tempo
            
            # this channel signals a global tempo change that will affect all the channels
            # once out of this per-channel loop
            elif cs.global_tempo_update is not None:
                global_tempo_change = cs.global_tempo_update

        # By this point, we've passed through all channels for this particular tick
        # If more than one channel made a tempo change, the global tempo change on the highest
        # voice/channel number wins (consistent with goattracker behavior)
        if global_tempo_change is not None:
            for j, cs in enumerate(channels_state):  # Time to apply the global changes:
                if global_tempo_change >= 2:
                    cs.curr_funktable_index = None
                    new_tempo = global_tempo_change
                else: # it's an index to a funktable tempo
                    cs.curr_funktable_index = global_tempo_change # stateful funky tracking
                    # convert into a normal tempo change
                    new_tempo = GtChannelState.funktable[cs.curr_funktable_index]

                # If a row is in progress, leave its remaining ticks alone.
                # But if it's the very start of a new row, then override with new global tempo
                if cs.first_tick_of_row:
                    cs.row_ticks_left = new_tempo

                cs.curr_tempo = new_tempo
                # tempo change plays out in sparse representation, but log it anyway
                channels_time_events[j][global_tick].tempo = cs.curr_tempo

    # Create note offs when all channels have hit their orderlist restart one or more times
    #    Ok, cheesy hack here.  The loop above repeats until all tracks have had a chance to restart, but it
    #    allows each voice to load in one row after that point.  Taking advantage of that, we modify that
    #    row with note off events, looking backwards to previous rows to see what the last note was to use
    #    in the note off events.
    for i, cs in enumerate(channels_state):
        reversed_index = list(channels_time_events[i].keys())
        reversed_index.sort(reverse=True)
        for index in reversed_index[1:]:
            if channels_time_events[i][index].note is not None:
                channels_time_events[i][global_tick].note = channels_time_events[i][index].note
                channels_time_events[i][global_tick].note_on = False
                break

    return channels_time_events


#
#
# Code to convert parsed gt file into rchirp
# 
#

def convert_parsed_gt_to_rchirp(sng_data, subtune_num = 0):
    """ 
    Convert the parsed orderlist and patterns into rchirp 
  
    Parameters: 
       sng_data (GTSong): Parsed goattracker file
       subtune_num (int): The subtune number to convert to rchirp (default 0)

    Returns: 
       RChirpSong: rchirp song instance
    """    
    # init state holders for each channel to use as we step through each tick (aka jiffy aka frame)
    channels_state = [GtChannelState(i+1, sng_data.subtune_orderlists[subtune_num][i]) for \
        i in range(sng_data.num_channels)]

    rchirp_song = ctsRChirp.RChirpSong()
    # This is instead of channels_time_events (TODO: delete this comment later)
    rchirp_song.voices = [ctsRChirp.RChirpVoice(rchirp_song) for i in range(sng_data.num_channels)]

    # TODO: Later, make track assignment to SID groupings not hardcoded
    if sng_data.is_stereo:
        rchirp_song.voice_groups = [(1,2,3),(4,5,6)]
    else:
        rchirp_song.voice_groups = [(1,2,3)]        

    # Handle the rarely-used sneaky default global tempo setting
    # from docs:
    #    For very optimized songdata & player you can refrain from using any pattern
    #    commands and rely on the instruments' step-programming. Even in this case, you
    #    can set song startup default tempo with the Attack/Decay parameter of the last
    #    instrument (63/0x3F), if you otherwise leave this instrument unused.

    # TODO: This code block is untested
    if len(sng_data.instruments) == GT_MAX_INSTR_PER_SONG:
        ad = sng_data.instruments[GT_MAX_INSTR_PER_SONG-1].attack_decay
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
                else: # it's an index to a funktable tempo
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
                else: # it's an index to a funktable tempo
                    cs.curr_funktable_index = global_tempo_change # stateful funky tracking
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
        for seek_index in reversed_index[1:]: # skip largest row num, and work backwards
            if rows[seek_index].note_num is not None:
                rows[reversed_index[0]].note_num = rows[seek_index].note_num
                rows[reversed_index[0]].gate = False # gate off
                break

    # Might as well make use of our test cases here
    rchirp_song.integrity_check() # Will throw assertions if there's problems    
    assert rchirp_song.is_contiguous(), "Error: rchirp representation should not be sparse"

    return rchirp_song


#
#
# Code to convert events in time into chirp
# TODO: This code section will be ultimately deleted.  rchirp->chirp used instead, and living in ctsRChirp.py
#
#


# Create CVS debug output
def note_time_data_str(num_channels, channels_time_events):
    max_tick = max(max(channels_time_events[i].keys()) for i in range(num_channels))

    csv_header = []
    csv_header.append("jiffy")
    for i in range(num_channels):
        csv_header.append("v%d note" % (i+1))
        csv_header.append("v%d on/off/none" % (i+1))
        csv_header.append("v%d tempo update" % (i+1))

    csv_rows = []
    for tick in range(max_tick+1):
        # if any channel has a entry at this tick, create a row for all channels
        if any(tick in channels_time_events[ch] for ch in range(num_channels)):
            a_csv_row = []
            a_csv_row.append("%d" % tick)
            for i in range(num_channels):
                if tick in channels_time_events[i]:
                    a_csv_row.append("%s" % \
                        ('' if channels_time_events[i][tick].note is None else channels_time_events[i][tick].note))
                    a_csv_row.append("%s" % \
                        ('' if channels_time_events[i][tick].note_on is None else channels_time_events[i][tick].note_on))
                    a_csv_row.append("%s" % \
                        ('' if channels_time_events[i][tick].tempo is None else channels_time_events[i][tick].tempo))
                else:
                    a_csv_row.append("")
                    a_csv_row.append("")
                    a_csv_row.append("")
            csv_rows.append(','.join(a_csv_row))
    spreadsheet = '\n'.join(csv_rows)
    spreadsheet = ','.join(csv_header) + '\n' + spreadsheet
    
    return spreadsheet


def convert_to_chirp(num_channels, channels_time_events, song_name):
    def tick_to_midi(tick, offset=0, factor=1):
        return (tick - offset) * factor

    song = ctsChirp.ChirpSong()
    song.metadata.ppq = 960
    song.name = song_name

    all_ticks = sorted(set(int(t) for i in range(num_channels) for t in channels_time_events[i].keys()))
    note_ticks = sorted([t for t in all_ticks if any(channels_time_events[ch].get(t, None) 
                    and (channels_time_events[ch][t].note_on is not None) for ch in range(num_channels))])
    notes_offset = note_ticks[0]
    # TODO: Should the two "100"s be parameterized?
    ticks_per_note = reduce(math.gcd, (note_ticks[i] - notes_offset for i in range(100)))
    if ticks_per_note < 3:  # no decent gcd for this data
        ticks_per_note = 6
    notes_per_minute = 60 * 60 / ticks_per_note
    tmp = notes_per_minute // 100
    tempo = int(notes_per_minute // tmp)
    tick_factor = int(song.metadata.ppq // tempo * tmp)

    tick_to_miditick = partial(tick_to_midi, offset=notes_offset, factor=tick_factor)

    midi_tick = 0
    for it, channel_data in enumerate(channels_time_events):
        track = ctsChirp.ChirpTrack(song)
        track.name = 'Track %d' % (it + 1)
        track.channel = it
        current_note = None
        for tick in sorted(channel_data):
            midi_tick = tick_to_miditick(tick)
            event = channel_data[tick]
            if event.note_on:
                if current_note:
                    new_note = ctsChirp.Note(
                        current_note.start_time, current_note.note_num, midi_tick - current_note.start_time
                    )
                    if new_note.duration > 0:
                        track.notes.append(new_note)
                current_note = ctsChirp.Note(midi_tick, event.note, 1)
            elif event.note_on is False:
                if current_note:
                    new_note = ctsChirp.Note(
                        current_note.start_time, current_note.note_num, midi_tick - current_note.start_time
                    )
                    if new_note.duration > 0:
                        track.notes.append(new_note)
                current_note = None
        if current_note:
            new_note = ctsChirp.Note(
                current_note.start_time, current_note.note_num, midi_tick - current_note.start_time
            )
            if new_note.duration > 0:
                track.notes.append(new_note)
        song.tracks.append(track)

    return song


#
#
# Code to convert chirp to goattracker file
# TODO: This will be replaced with code to convert rchirp to goattracker file
#
#

PATTERN_EMPTY_ROW = GtPatternRow(note_data = GT_REST)

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


def chirp_to_GT(song, out_filename, tracknums=[1,2,3], is_stereo = False, \
    arch='NTSC', end_with_repeat = False):

    def midi_to_gt_tick(midi_ticks, offset, factor):
        return midi_ticks // factor + offset

    if is_stereo:
        num_channels = 6
    else:
        num_channels = 3

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

    """
    dur_str = duration_to_note_name(required_tick_granularity, song.metadata.ppq)
    print("required granularity = %s note" % dur_str)
    print("song time signature denominator = %d" % song.metadata.time_signature.denom)
    min_rows_per_beat = song.metadata.ppq * 4 // song.metadata.time_signature.denom // required_tick_granularity
    print("minimum rows per beat = %d" % min_rows_per_beat)
    print("available qpms for jiffy = %.2lf per sec:" % jiffy)
    print('\n'.join("%.1lf qpm" % (jiffy / (n * min_rows_per_beat) * 60.) for n in range(1, 20)))

    # This is now a real number to convert between unitless midi ticks and unitless GT ticks
    # The complication is that you can multiply the min_rows_per_note by an integer to give better
    #   time resolution, which will result in a different set of GT tempos available
    midi_to_tick = partial(midi_to_gt_tick, offset=0, factor=song.metadata.ppq // min_rows_per_note)

    # Logic that can help with assigning a tempo to the GT rows:
    jiffies_per_beat= int(jiffy / (song.metadata.qpm / 60)) # jiffies per sec / bps
    rows_per_beat = min_rows_per_beat
    jiffies_per_row = jiffies_per_beat / rows_per_beat 
    """

    # Make a sparse representation of rows for each channel
    # TODO: This simple transformation will need to be changed when it's time
    #       to incorporate music compression, mid-tune tempo changes, etc.
    DEFAULT_INSTRUMENT = 1
    channels_rows = [defaultdict(GtPatternRow) for i in range(num_channels)]
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
            channel_row[global_row_start].note_data = note_num
            # update that pattern row
            channel_row[global_row_start].inst_num = DEFAULT_INSTRUMENT

            # Since we get the notes in order, this note end is very likely to be overwritten
            # later by the next note (this is good)
            channel_row[global_row_end].note_data = GT_KEY_OFF

    # Inject tempo updates here
    # TODO: Someday, inject tempo updates where needed.  For right now, just set the initial tempo.
    # TODO: Initial tempo should be set by logic, not hardcoded like this, which injects global tempo 6
    #       into channel 0 at row 0 (row 0 will belong to the first pattern later).
    channels_rows[0][0].command = 0x0F  # tempo change command
    # $03-$7F sets tempo on all channels
    # $83-$FF only on current channel (subtract $80 to get actual tempo)
    min_rows_per_quarter = song.metadata.ppq  // required_tick_granularity
    print('Rows per beat = %d' % min_rows_per_quarter)
    jiffies_per_quarter = int(ARCH[arch].frame_rate / (song.metadata.qpm / 60) + 0.5)  # jiffies per sec / bps
    print('qpm = %d, jiffies/beat = %d' % (song.metadata.qpm, jiffies_per_quarter))
    rows_per_quarter = min_rows_per_quarter
    jiffies_per_row = jiffies_per_quarter // rows_per_quarter
    print("%d jiffies per row" % jiffies_per_row)

    #channels_rows[0][0].command_data=0x06 # global tempo of 6 (goat tracker's default)
    channels_rows[0][0].command_data=jiffies_per_row # global tempo of 6 (goat tracker's default)

    # Convert the sparse representation into separate patterns (of bytes)
    EXPORT_PATTERN_LEN = 126 # index 0 to len-1 for data, index len for 0xFF pattern end mark
    patterns = [] # can be shared across all channels
    orderlists = [[] for _ in range(len(tracknums))] # Note: this is bad: [[]] * len(tracknums)
    curr_pattern_num = 0
    too_many_patterns = False

    # for each channel, get its rows, and create patterns, adding them to the 
    # channel's orderlist
    for i, channel_rows in enumerate(channels_rows):       
        pattern_row_index = 0
        pattern = bytearray() # create a new, empty pattern
        max_row = max(channel_rows)
        for j in range(max_row+1): # iterate across row num span (inclusive)
            if j in channel_rows: # if something there...
                pattern += row_to_bytes(channel_rows[j])
            else:
                pattern += row_to_bytes(PATTERN_EMPTY_ROW)
            pattern_row_index += 1
            if pattern_row_index == EXPORT_PATTERN_LEN: # if pattern is full
                pattern += row_to_bytes(PATTERN_END_ROW) # finish with end row marker
                patterns.append(pattern)
                orderlists[i].append(curr_pattern_num) # append to orderlist for this channel
                curr_pattern_num += 1
                if curr_pattern_num >= GT_MAX_PATTERNS_PER_SONG:
                    too_many_patterns = True
                    break
                pattern = bytearray()
                pattern_row_index = 0
        if too_many_patterns:
            break
        if len(pattern) > 0: # if there's a final partially-filled pattern, add it
            pattern += row_to_bytes(PATTERN_END_ROW)
            patterns.append(pattern)
            orderlists[i].append(curr_pattern_num)
            curr_pattern_num += 1
            if curr_pattern_num >= GT_MAX_PATTERNS_PER_SONG:
                too_many_patterns = True
    if too_many_patterns and not TRUNCATE_IF_TOO_BIG:
        raise ChiptuneSAKContentError("Error: More than %d goattracker patterns created"
            % GT_MAX_PATTERNS_PER_SONG)
    else:
        print("Warning: too much note data, truncating patterns...")
    

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
        loop_pattern_num = len(patterns)-1
        for i in range(num_channels):
            orderlists[i].append(loop_pattern_num)

    for i in range(num_channels):
        orderlists[i].append(GT_OL_RST) # patterns end with restart indicator
        if end_with_repeat:
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
    for i in range(num_channels):
        gt_binary.append(len(orderlists[i])-1) # orderlist length minus 1
        gt_binary += bytes(orderlists[i])

    # append instruments
    # TODO: At some point, should add support for loading gt .ins instrument files for the channels
    # Need an instrument
    # For now, just going to design a simple triangle sound as instrument number 1.
    # This requires setting ADSR, and a wavetable position of 01.
    # Then a wavetable with the entires 01:11 00, and 02:FF 00 
    gt_binary.append(0x01) # number of instruments (not counting NOP instrument 0)
    gt_binary += instrument_to_bytes(GtInstrument(inst_num=1, attack_decay=0x22, sustain_release=0xFA,
        wave_ptr=0x01, inst_name='simple triangle'))
    # TODO: In the future, more instruments appended here (in instrument number order)
    
    # append tables
    gt_binary.append(0x02) # wavetable with two row entries
    gt_binary += bytes([0x11, 0xFF, 0x00, 0x00]) # simple triangle instrument waveform
    gt_binary.append(0x00) # length 0 pulsetable
    gt_binary.append(0x00) # length 0 filtertable
    gt_binary.append(0x00) # length 0 speedtable

    # append patterns
    gt_binary.append(len(patterns)) # number of patterns
    for pattern in patterns:
        assert len(pattern) % 4 == 0, "Error: unexpected pattern byte length"
        gt_binary.append(len(pattern) // 4) # length of pattern in rows
        gt_binary += pattern

    return gt_binary


#
#
# TODO: Code to convert rchirp to goattracker file
#
#


if __name__ == "__main__":
    pass

