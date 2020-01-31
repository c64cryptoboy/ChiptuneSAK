# Code to parse and import goattracker .sng files
# 
# Prereqs
#    pip install recordtype
#    pip install sortedcontainers

# TODO: Refactor this into a generalized chiptune-sak importer (command line option, etc.), and put in src
# TODO: Test the repeat command on a different goat tracker tune (consultant one doesn't use it)

from os import path
import argparse
import copy
import math
from functools import reduce, partial
from ctsErrors import ChiptuneSAKException
from ctsML64 import pitch_to_ml64_note_name
from recordtype import recordtype
from sortedcontainers import SortedDict
import ctsSong

OCTAVE_BASE = -1  # -1 means that in goattracker, middle C (note 60) is "C4"
DEFAULT_TEMPO = 6

# Goat tracker uses the term "song" to mean a collection of independently-playable subtunes
MAX_SUBTUNES_PER_SONG = 32 # Each subtune gets its own orderlist of patterns
MAX_ELM_PER_ORDERLIST = 255 # at minimum, it must contain the endmark and following byte
MAX_INSTR_PER_SONG = 63
MAX_PATTERNS_PER_SONG = 208
MAX_ROWS_PER_PATTERN = 128 # and min rows (not including end marker) is 1


class GTSong:
    def __init__(self):
        self.headers = GtHeader()
        self.subtune_orderlists =  [[[],[],[]]] # [subtune][channel_index0-2][orderlist_byte_index]
        self.instruments = [] # list of GtInstrument instances
        self.wave_table = GtTable()
        self.pulse_table = GtTable()
        self.filter_table = GtTable()
        self.speed_table = GtTable()
        self.patterns = [[]] # list of patterns, each of which is an list of GtPatternRow instances        


GtHeader = recordtype('GtHeader',
    [('id', ''), ('song_name', ''), ('author_name', ''), ('copyright', ''), ('num_subtunes', 0)])

GtInstrument = recordtype('GtInstrument',
    [('inst_num', 0), ('attack_decay', 0), ('sustain_release', 0), ('wave_ptr', 0), ('pulse_ptr', 0),
    ('filter_ptr', 0), ('vib_speedtable_ptr', 0), ('vib_delay', 0), ('gateoff_timer', 0),
    ('hard_restart_1st_frame_wave', 0), ('inst_name', '')])

GtTable = recordtype('GtTable',
    [('row_cnt', 0), ('left_col', b''), ('right_col', b'')])

GtPatternRow = recordtype('GtPatternRow',
    [('note_data', 0), ('inst_num', 0), ('command', 0), ('command_data', 0)])

PATTERN_END_ROW = GtPatternRow(note_data = 0xFF)

# TimeEntry instances are values in SortedDict where key is tick
# Over time, might add other commands to this as well (funktempo, Portamento, etc.)
TimeEntry = recordtype('TimeEntry',
    [('note', None), # midi note number
    ('note_on', None), # True for note on, False for note off, or None (when no note)
    ('tempo', None)]) # shows when the tempo changed (which affected note time placement)

# Used when "running" the channels to convert them to note on/off events in time
class GtChannelState:
    __init_tempo_override = None
    __patterns = [] # patterns across all subtunes and channels
    # would have init this to None, but this triggers a pylint bug where some references
    # to this variable will trigger an "unscriptable-object" error
    # https://github.com/PyCQA/pylint/issues/1498

    def __init__(self, voice_num, channel_orderlist):
        if (GtChannelState.__patterns == []):
            raise ChiptuneSAKException("Must first init class with GtChannelState.set_patterns()")

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

        if GtChannelState.__init_tempo_override is None:
            self.curr_tempo = DEFAULT_TEMPO
        else:
            self.curr_tempo = GtChannelState.__init_tempo_override

        self.__inc_orderlist_to_next_pattern() # position atop first pattern in orderlist for channel

    @classmethod
    def set_song(cls, song):
        GtChannelState.__patterns = song.patterns

        """ from docs:
        For very optimized songdata & player you can refrain from using any pattern
        commands and rely on the instruments' step-programming. Even in this case, you
        can set song startup default tempo with the Attack/Decay parameter of the last
        instrument (63/0x3F), if you otherwise leave this instrument unused.
        """
        # Handle the sneaky default global tempo (NOTE: THIS CODE IS UNTESTED)
        if len(song.instruments) == MAX_INSTR_PER_SONG:
            ad = song.instruments[MAX_INSTR_PER_SONG-1].attack_decay
            if 0x02 <= ad <= 0x7F:
                __init_tempo_override = ad

    # Advance channel/voice by a tick.  If advancing to a new row, then return it, otherwise None.
    def next_tick(self):
        self.first_tick_of_row = False

        # If stuck in an orderlist loop that doesn't contain a pattern, then there's nothing to do
        if self.orderlist_index is None:
            return None

        self.row_ticks_left -= 1 # init val is 1
        assert self.row_ticks_left >=0, "Error: Can't have negative tick values"
        if self.row_ticks_left > 0:
            return None
        
        self.__inc_to_next_row() # finished last pattern row, on to the next

        row = copy.deepcopy(GtChannelState.__patterns[
            self.channel_orderlist[self.orderlist_index]][self.row_index])

        # If row contains a note, transpose if necessary (0 = no transform)
        if 0x60 <= row.note_data <= 0xBC: # range $60 (C0) to $BC (G#7)
            note = row.note_data + self.curr_transposition
            assert note >= 0x60, "Error: transpose dropped note below midi C0"
            # According to docs, allowed to transpose +3 halfsteps above the highest note (G#7)
            #    that can be entered in the GT GUI, to create a B7
            assert note <= 0xBF, "Error: transpose raised note above midi B7"
            self.curr_note = pattern_note_to_midi_note(note)
            self.row_has_note = True

        # Rest ($BD/189, gt display "..."):  A note continues through rest rows.  Rest does not mean
        # what it would in sheet music.  For our purposes, we're ignoring it

        # KeyOff ($BE/190, gt display "---"): Unsets the gate bit mask.  This starts the release phase
        # of the ADSR.
        # Going to ignore any effects gateoff timer and hardrestart values might have on perceived note end
        if row.note_data == 0xBE:
            if self.curr_note is not None:
                self.row_has_key_off = True

        # KeyOn ($BF/191, gt display "+++"): Sets the gate bit mask (ANDed with data from the wavetable).
        # If no prior note has been started, then nothing will happen.  If a note is playing,
        # nothing will happen (to the note, to the instrument, etc.).  If a note was turned off,
        # this will restart it, but will not restart the instrument.
        if row.note_data == 0xBF:
            if self.curr_note is not None:
                self.row_has_key_on = True
            
        if row.command == 0x0F: # tempo change
            """
            From docs:
            Values $03-$7F set tempo on all channels, values $83-$FF only on current channel (subtract
            $80 to get actual tempo). Tempos $00-$01 recall the funktempo values set by EXY command.
            """
            # From experiments:
            # - funktempo is basically swing tempo
            # - empirically, the higher voice number seems to win ties on simultaneous speed changes
            # - $80-$81 will recall the funktempo for just that channel
            # - $02 and $82 are possible speeds under certain constraints, but not going to support
            #   them here (yet).

            assert row.command_data not in [0x02, 0x82] \
                , "TODO: Don't know how to support tempo change with value %d" % (row.command_data)     

            # Change tempo for all channels
            #   From looking at the gt source code (at least for the goat tracker gui's gplay.c)
            #   when a CMD_SETTEMPO happens (for one or for all three channels), the tempos immediately
            #   change, but the ticks remaining on each channel's current row (in progress) is left alone --
            #   another detail that would have been nice to have had in the documentation.
            if 0x03 <= row.command_data <= 0x7F:
                self.global_tempo_update = row.command_data
                self.curr_tempo = self.global_tempo_update
                # Note: Can't set this global tempo change in the other two channels here, will
                #    be done elsewhere.

            # Change tempo for just the given channel
            if 0x83 <= row.command_data <= 0xFF:
                self.local_tempo_update = row.command_data - 0x80
                self.curr_tempo = self.local_tempo_update         

        # TODO: Possibly handle some of the (below) commands in the future?
        """ from docs:
        Command 1XY: Portamento up. XY is an index to a 16-bit speed value in the speedtable.
    
        Command 2XY: Portamento down. XY is an index to a 16-bit speed value in the speedtable.
    
        Command 3XY: Toneportamento. Raise or lower pitch until target note has been reached. XY is an index
        to a 16-bit speed value in the speedtable, or $00 for "tie-note" effect (move pitch instantly to
        target note)
        
        Command DXY: Set mastervolume to Y, if X is $0. If X is not $0, value XY is
        copied to the timing mark location, which is playeraddress+$3F.
    
        Command EXY: Funktempo. XY is an index to the speedtable, tempo will alternate
        between left side value and right side value on subsequent pattern
        steps. Sets the funktempo active on all channels, but you can use
        the next command to override this per-channel.
        """

        # Number of ticks for a row is based on tempo.  This can be overwritten by another
        # channel's global tempo change.  However, this class only knows of one channel at a time.
        # A different part of this program will coordinate when one instance of GtChannelState affects
        # the tempo of the others.
        self.row_ticks_left = self.curr_tempo # reset the tick counter for the row

        return row

    # Advance to next row in pattern.  If pattern end, then go to row 0 of next pattern in orderlist
    def __inc_to_next_row(self):
        self.row_index += 1 # init val is -1
        self.row_has_note = self.row_has_key_on = self.row_has_key_off = False 
        self.local_tempo_update = self.global_tempo_update = None
        self.first_tick_of_row = True
        row = GtChannelState.__patterns[self.channel_orderlist[self.orderlist_index]][self.row_index]
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
            #     Bug in goattracker documentation: says range is $E0 (224) to $FE (254)
            #     I'm assuming byte 224 is never used in orderlists
            assert a_byte != 0xE0, "TODO: I don't believe byte E0 should occur in the orderlist"          
            if 0xE1 <= a_byte <= 0xFE:  # F0 = +0 = no transposition
                self.curr_transposition = a_byte - 0xF0  # transpose range is -15 to +14
                continue

            # parse repeat
            # Repeat values 1 to 16.  In tracker, instead of R0..RF, it's R1..RF,R0
            #   i.e., 'R0'=223=16reps, 'RF'=222=15 reps, 'R1'=208=1rep
            if 0xD0 <= a_byte <= 0xDF:
                # repeat range is 1 to 16, so remaining plays (default 1) can reach 17
                self.pat_remaining_plays = a_byte - 0xCF + 1
                continue

            # parse RST (restart)
            if a_byte == 0xFF:  # RST
                self.restarted = True

                start_index = self.channel_orderlist[self.orderlist_index+1] # byte following RST is orderlist restart index
                end_index = self.orderlist_index # byte containing RST
                self.orderlist_index = self.channel_orderlist[self.orderlist_index+1] # perform orderlist "goto" jump
                # check if there's at least one pattern between the restart location and the RST
                if sum(1 for p in self.channel_orderlist[start_index:end_index] if p < MAX_PATTERNS_PER_SONG) == 0:
                    self.orderlist_index = None
                    break # no pattern to ultimately end up on, so we're done
                # continue loop, just in case we land on a repeat or transpose that needs resolving
                self.orderlist_index -= 1 #"undo" +1 at start of loop
                continue 

            # parse pattern
            if a_byte < MAX_PATTERNS_PER_SONG: # if it's a pattern
                break # found one, done parsing

            raise ChiptuneSAKException("Error: found uninterpretable value %d in orderlist" % a_byte)


# Convert pattern note byte value into midi note value
# Note: lowest goat tracker note C0 = midi #24
def pattern_note_to_midi_note(pattern_note_byte):
    return pattern_note_byte - 72 + (OCTAVE_BASE * 12)


def get_chars(in_bytes, trim_nulls=True):
    result = in_bytes.decode('Latin-1')
    if trim_nulls:
        result = result.strip('\0')  # no interpretation, preserve encoding
    return result


def get_order_list(an_index, file_bytes):
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
    an_index += 1

    left_entries = file_bytes[an_index:an_index + rows]
    an_index += rows

    right_entries = file_bytes[an_index:an_index + rows]

    return GtTable(row_cnt=rows, left_col=left_entries, right_col=right_entries)


# Parse a goat tracker .sng file and put it into a GTSong instance
def import_sng(gt_filename):
    with open(gt_filename, 'rb') as f:
        sng_bytes = f.read()

    a_song = GTSong()

    header = GtHeader()

    header.id = sng_bytes[0:4]
    assert header.id == b'GTS5', "Error: Did not find magic header used by goattracker sng files"

    header.song_name = get_chars(sng_bytes[4:36])
    header.author_name = get_chars(sng_bytes[36:68])
    header.copyright = get_chars(sng_bytes[68:100])
    header.num_subtunes = sng_bytes[100]

    assert header.num_subtunes <= MAX_SUBTUNES_PER_SONG, 'Error:  too many subtunes'

    file_index = 101
    a_song.headers = header
    
    # print("\nDebug: %s" % header)

    """ From goattracker documentation:
    6.1.2 Song orderlists
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

    subtune_orderlists = []
    for subtune_index in range(header.num_subtunes):
        order_list_triple = []
        for i in range(3):
            channel_order_list = get_order_list(file_index, sng_bytes)
            file_index += len(channel_order_list) + 1
            order_list_triple.append(channel_order_list)
        subtune_orderlists.append(order_list_triple)
    a_song.subtune_orderlists = subtune_orderlists
    
    # print("\nDebug: %s" % subtune_orderlists)

    """ From goattracker documentation:
    6.1.3 Instruments
    -----------------
    Offset  Size    Description
    +0      byte    Amount of instruments n

    Then, this structure repeats n times for each instrument. Instrument 0 (the
    empty instrument) is not stored.

    Offset  Size    Description
    +0      byte    Attack/Decay
    +1      byte    Sustain/Release
    +2      byte    Wavepointer
    +3      byte    Pulsepointer
    +4      byte    Filterpointer
    +5      byte    Vibrato param. (speedtable pointer)
    +6      byte    Vibraro delay
    +7      byte    Gateoff timer
    +8      byte    Hard restart/1st frame waveform
    +9      16      Instrument name
    """

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

    # print("\nDebug: %s" % instruments)

    """ From goattracker documentation:
    6.1.4 Tables
    ------------
    This structure repeats for each of the 4 tables (wavetable, pulsetable,
    filtertable, speedtable).

    Offset  Size    Description
    +0      byte    Amount n of rows in the table
    +1      n       Left side of the table
    +1+n    n       Right side of the table
    """

    tables = []
    for i in range(4):
        a_table = get_table(file_index, sng_bytes)
        tables.append(a_table)
        file_index += a_table.row_cnt * 2 + 1

    # print("\nDebug: %s" % tables)
    (a_song.wave_table, a_song.pulse_table, a_song.filter_table, a_song.speed_table) = tables

    """ From goattracker documentation:
    6.1.5 Patterns header
    ---------------------
    Offset  Size    Description
    +0      byte    Number of patterns n
    
    6.1.6 Patterns
    --------------
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

    num_patterns = sng_bytes[file_index]
    file_index += 1
    patterns = []

    for pattern_num in range(num_patterns):
        a_pattern = []
        num_rows = sng_bytes[file_index]
        assert num_rows <= MAX_ROWS_PER_PATTERN, "Too many rows in a pattern"
        file_index += 1
        for row_num in range(num_rows):
            a_row = GtPatternRow(note_data=sng_bytes[file_index], inst_num=sng_bytes[file_index + 1],
                                 command=sng_bytes[file_index + 2], command_data=sng_bytes[file_index + 3])
            assert (0x60 <= a_row.note_data < 0xBF) or a_row.note_data == 0xFF, "Error: unexpected note data value"
            assert a_row.inst_num <= MAX_INSTR_PER_SONG, "Error: instrument number out of range"
            assert a_row.command <= 0x0F, "Error: command number out of range"                     
            file_index += 4
            a_pattern.append(a_row)
        patterns.append(a_pattern)
        #print("\nDebug: pattern num: %d, pattern rows: %d, content: %s" %
        #    (pattern_num, len(a_pattern), a_pattern))

    a_song.patterns = patterns

    assert file_index == len(sng_bytes), "Error: bytes parsed didn't match file bytes length"
    return a_song


# Convert the orderlist and patterns into three channels of note on/off events in time (ticks)
def convert_to_note_events(sng_data, subtune_num):
    # init state holders for each channel
    GtChannelState.set_song(sng_data)
    channels_state = [GtChannelState(i+1, sng_data.subtune_orderlists[subtune_num][i]) for i in range(3)]
    channels_time_events = [SortedDict() for i in range(3)]

    global_tick = -1
    while not all(cs.restarted for cs in channels_state):
        # When not using multispeed, tempo = ticks per row = screen refreshes per row.
        # 'Ticks' on C64 are also 'frames' or 'jiffies'.  Each tick in PAL is around 20ms,
        # and ~16.7‬ms on NTSC.
        # For a multispeed of 2, there would be two music updates per frame.
        # For our purposes, the multispeed multiplier doesn't matter, since ticks in
        # our music intermediate format (as well as in midi are unitless (not tied to ms
        # or frames).
        global_tick += 1
        global_tempo_change = None

        for i, channel_state in enumerate(channels_state):
            channel_time_events = channels_time_events[i]

            row = channel_state.next_tick()
            if row is None:  # if we didn't advance to a new row
                continue

            # KeyOff (and there's a curr_note defined)
            if channel_state.row_has_key_off:
                channel_time_events.setdefault(global_tick, TimeEntry()).note = channel_state.curr_note
                channel_time_events[global_tick].note_on = False

            # KeyOn (and there's a curr_note defined)
            if channel_state.row_has_key_on:
                channel_time_events.setdefault(global_tick, TimeEntry()).note = channel_state.curr_note
                channel_time_events[global_tick].note_on = True

            # if note_data is an actual note
            elif channel_state.row_has_note:
                channel_time_events.setdefault(global_tick, TimeEntry()).note = channel_state.curr_note
                channel_time_events[global_tick].note_on = True
            
            # process tempo changes

            if channel_state.local_tempo_update is not None:
                channel_time_events.setdefault(global_tick, TimeEntry()).tempo = channel_state.local_tempo_update

            elif channel_state.global_tempo_update is not None:
                global_tempo_change = channel_state.global_tempo_update

        # By this point, we've passed through all three channels for this particular tick
        # If more than one channel made a tempo change, the global tempo change on the highest
        # voice/channel number wins (based on testing in gt)
        if global_tempo_change is not None:
            for j, cs in enumerate(channels_state):
                # If a row is in progress, leave it's remaining ticks alone.  But if it's the start of a
                # new row, then override with new global tempo
                if cs.first_tick_of_row:
                    assert cs.row_ticks_left == cs.curr_tempo \
                        , "Error: unexpected number of ticks left on row prior to global tempo override"
                    cs.row_ticks_left = global_tempo_change

                cs.curr_tempo = global_tempo_change
                channels_time_events[j].setdefault(global_tick, TimeEntry()).tempo = global_tempo_change

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
                channels_time_events[i].setdefault(global_tick, TimeEntry()).note = \
                    channels_time_events[i][index].note
                channels_time_events[i][global_tick].note_on = False
                break

    return channels_time_events


def note_time_data_str(channels_time_events):
    max_tick = max(max(channels_time_events[i].keys()) for i in range(3))
    #max_tick = min(max_tick, 500) # for testing

    ret_val = []
    for tick in range(max_tick+1):
        if any(tick in channels_time_events[ch] for ch in range(3)):
            output = "%d: " % tick
            for i in range(3):
                if tick in channels_time_events[i]:
                    output += "V%d N%s On?%s, " % (i, channels_time_events[i][tick].note, channels_time_events[i][tick].note_on)
                else:
                    output += "V%d N-- On?None, " % i
            ret_val.append(output)
    return '\n'.join(ret_val)


def convert_to_chirp(channels_time_events, song_name):
    def tick_to_midi(tick, offset=0, factor=1):
        return (tick - offset) * factor

    song = ctsSong.Song()
    song.ppq = 960
    song.name = song_name

    # print_note_time_data(channels_time_events)
    all_ticks = sorted(set(int(t) for i in range(3) for t in channels_time_events[i].keys()))
    note_ticks = sorted([t for t in all_ticks if any(channels_time_events[ch].get(t, None) 
                                                 and (channels_time_events[ch][t].note_on is not None) for ch in range(3))])
    notes_offset = note_ticks[0]
    ticks_per_note = reduce(math.gcd, (note_ticks[i] - notes_offset for i in range(100)))
    if ticks_per_note < 3:  # no decent gcd for this data
        ticks_per_note = 6
    notes_per_minute = 60 * 60 / ticks_per_note
    tmp = notes_per_minute // 100
    tempo = int(notes_per_minute // tmp)
    tick_factor = int(song.ppq // tempo * tmp)

    tick_to_miditick = partial(tick_to_midi, offset=notes_offset, factor=tick_factor)

    midi_tick = 0
    for it, channel_data in enumerate(channels_time_events):
        track = ctsSong.SongTrack(song)
        track.name = 'Track %d' % (it + 1)
        track.channel = it
        current_note = None
        for tick, event in channel_data.items():
            midi_tick = tick_to_miditick(tick)
            if event.note_on:
                if current_note:
                    new_note = ctsSong.Note(
                        current_note.start_time, current_note.note_num, midi_tick - current_note.start_time
                    )
                    if new_note.duration > 0:
                        track.notes.append(new_note)
                current_note = ctsSong.Note(midi_tick, event.note, 1)
            elif event.note_on is False:
                if current_note:
                    new_note = ctsSong.Note(
                        current_note.start_time, current_note.note_num, midi_tick - current_note.start_time
                    )
                    if new_note.duration > 0:
                        track.notes.append(new_note)
                current_note = None
        if current_note:
            new_note = ctsSong.Note(
                current_note.start_time, current_note.note_num, midi_tick - current_note.start_time
            )
            if new_note.duration > 0:
                track.notes.append(new_note)
        song.tracks.append(track)

    return song


# Here for debugging, remove later
def main():
    pass


if __name__ == "__main__":
    main()
