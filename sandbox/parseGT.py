# Code to parse goattracker .sng files
# Currently in sandbox folder.  Will be ultimately be refactored into a generalized chiptune-sak importer
#
# Must first install recordtype
#    pip install recordtype
#

import sys
from recordtype import recordtype

"""
Style notes to self (delete later):

    You should only use StudlyCaps for class names.
    Constants should be IN_ALL_CAPS with underscores separating words.
    Variable, method, and function names should always be snake_case.
"""

debug = False

# Goat tracker uses the term "song" to mean a collection of indendently-playable subtunes
MAX_SUBTUNES_PER_SONG = 32 # Each subtune gets its own orderlist of patterns
MAX_ELM_PER_ORDERLIST = 255 # at minimum, must contain the endmark
MAX_INSTR_PER_SONG = 63
MAX_PATTERNS_PER_SONG = 208
MAX_ROWS_PER_PATTERN = 128


class GTSong:
    def __init__(self):
        self.headers = GtHeader()
        self.subtuneOrderLists = [] # list of GtSubtuneOrderList instances
        self.instruments = [] # list of GtInstrument instances
        self.wave_table = GtTable()
        self.pulse_table = GtTable()
        self.filter_table = GtTable()
        self.speed_table = GtTable()
        self.patterns = [[]] # list of patterns, each of which is an list of GtPatternRow instances

GtHeader = recordtype('GtHeader',
    [('id', ''), ('song_name', ''), ('author_name', ''), ('copyright', ''), ('num_subtunes', 0)])

GtSubtuneOrderList = recordtype('GtSubtuneOrderList',
    [('ch1OrderList', b''), ('ch2OrderList', b''), ('ch3OrderList', b'')])

GtInstrument = recordtype('GtInstrument',
    [('inst_num', 0), ('attack_decay', 0), ('sustain_release', 0), ('wave_ptr', 0), ('pulse_ptr', 0),
    ('filter_ptr', 0), ('vib_speetable_ptr', 0), ('vib_delay', 0), ('gateoff_timer', 0),
    ('hard_restart_1st_frame_wave', 0), ('inst_name', '')])

GtTable = recordtype('GtTable',
    [('row_cnt', 0), ('left_col', b''), ('right_col', b'')])

GtPatternRow = recordtype('GtPatternRow',
    [('note_data', 0), ('inst_num', 0), ('command', 0), ('command_data', 0)])


def get_chars(in_bytes, trim_nulls=True):
    result = in_bytes.decode('Latin-1')
    if trim_nulls:
        result = result.strip('\0')  # no interpretation, preserve encoding
    return result


def get_order_list(an_index, file_bytes):
    length = file_bytes[an_index] + 1  # add one, since restart position not counted for some reason
    an_index += 1

    orderlist = file_bytes[an_index:an_index + length]
    an_index += length
    # check that next-to-last byte is $FF
    assert file_bytes[an_index - 2] == 255, "Error: Did not find expected $FF RST endmark in channel's orderlist"

    return orderlist


def get_table(an_index, file_bytes):
    rows = file_bytes[an_index]
    an_index += 1

    left_entries = file_bytes[an_index:an_index + rows]
    an_index += rows

    right_entries = file_bytes[an_index:an_index + rows]

    return GtTable(row_cnt=rows, left_col=left_entries, right_col=right_entries)


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

    file_index = 101
    a_song.headers = header
    
    if debug: print("\nDebug: %s" % header)

    """ From goattracker documentation:
    
    3.1 Orderlist data
    ------------------
    
    A song can consist of up to 32 subtunes. For each subtune's each channel, there
    is an orderlist which determines in what order patterns are to be played. In
    addition to pattern numbers, there can be TRANSPOSE & REPEAT commands and
    finally there is a RST (RESTART) endmark followed by restart position. The
    maximum length of an orderlist is 254 pattern numbers/commands + the endmark.

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

    orderlists = []
    for subtune_index in range(header.num_subtunes):
        order_list = GtSubtuneOrderList()

        order_list.ch1OrderList = get_order_list(file_index, sng_bytes)
        file_index += len(order_list.ch1OrderList) + 1

        order_list.ch2OrderList = get_order_list(file_index, sng_bytes)
        file_index += len(order_list.ch2OrderList) + 1

        order_list.ch3OrderList = get_order_list(file_index, sng_bytes)
        file_index += len(order_list.ch3OrderList) + 1

        orderlists.append(order_list)
    a_song.subtuneOrderLists = orderlists
    
    if debug: print("\nDebug: %s" % orderlists)

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
                                     vib_speetable_ptr=sng_bytes[file_index + 5], vib_delay=sng_bytes[file_index + 6],
                                     gateoff_timer=sng_bytes[file_index + 7],
                                     hard_restart_1st_frame_wave=sng_bytes[file_index + 8])
        file_index += 9

        an_instrument.inst_num = i + 1
        an_instrument.inst_name = get_chars(sng_bytes[file_index:file_index + 16])
        file_index += 16

        instruments.append(an_instrument)
    a_song.instruments = instruments

    if debug: print("\nDebug: %s" % instruments)

    """ From goattracker documentation:
    6.1.4 Tables
    ------------

    This structure repeats for each of the 4 tables (wavetable, pulsetable,
    filtertable, speedtable).

    Offset  Size    Description
    +0      byte    Amount n of rows in the table
    +1      n       Left side of the table
    +1+n    n       Right side of the table

    @endnode
    @node 6.1.5Patternsheader "6.1.5 Patterns header"

    """

    tables = []
    for i in range(4):
        a_table = get_table(file_index, sng_bytes)
        tables.append(a_table)
        file_index += a_table.row_cnt * 2 + 1

    if debug: print("\nDebug: %s" % tables)
    (a_song.wave_table, a_song.pulse_table, a_song.filter_table, a_song.speed_table) = tables

    """ From goattracker documentation:
    
    3.2 Pattern data
    ----------------
    
    Patterns are single-channel only for flexibility & low memory use. They contain
    the actual notes, instrument changes & sound commands. A pattern can have
    variable length, up to 128 rows. There can be 208 different patterns in a song.

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
                    
    Notes on tempo:  tracker processes one pattern row per tempo 'beat'
    Tempo is a divisor; lower means faster; 3 seems to be the fastest available
    - Probably a screen refresh divisor (60 Hz or 50 Hz)
    Different tracks can have different tempos
    
    3.6 Miscellaneous tips
    ----------------------
    
    - Patterns will take less memory the less there are command changes. When the
      song is packed/relocated, for example a long vibrato or portamento command
      needs to be stored only once as long as the parameter stays the same on
      subsequent pattern rows.

    """

    num_patterns = sng_bytes[file_index]
    file_index += 1
    patterns = []

    for pattern_num in range(num_patterns):
        a_pattern = []
        num_rows = sng_bytes[file_index]
        file_index += 1
        for row_num in range(num_rows):
            a_row = GtPatternRow(note_data=sng_bytes[file_index], inst_num=sng_bytes[file_index + 1],
                                 command=sng_bytes[file_index + 2], command_data=sng_bytes[file_index + 3])
            file_index += 4
            a_pattern.append(a_row)
        patterns.append(a_pattern)
        if debug:
            print("\nDebug: pattern num: %d, pattern rows: %d, content: %s" % (pattern_num, len(a_pattern), a_pattern))
    a_song.patterns = patterns

    assert file_index == len(sng_bytes), "Error: bytes parsed didn't match file bytes length"

    return a_song


def unroll_pattern(pattern_num, transpose):
    pass

    # range checking: up to transpose + 3 is allowed on a G#7 (creating B-7)

    # TODO: Turn documentation below into code:

    """
    In place of a normal note, there can also be one of these special "notes":
    ... Rest
    --- Key off (clear gatebit mask)
    +++ Key on (set gatebit mask)
    The actual state of the gatebit will be the gatebit mask ANDed with data from
    the wavetable. A key on cannot set the gatebit if it was explicitly cleared
    at the wavetable.

    Command 0XY: Do nothing. Databyte will always be $00.
    Command 1XY: Portamento up. XY is an index to a 16-bit speed value in the
    speedtable.
    Command 2XY: Portamento down. XY is an index to a 16-bit speed value in the
    speedtable.
    Command 3XY: Toneportamento. Raise or lower pitch until target note has been
    reached. XY is an index to a 16-bit speed value in the
    speedtable, or $00 for "tie-note" effect (move pitch instantly to
    target note)
    Command 4XY: Vibrato. XY is an index to the speed table, where left side
    determines how long until the direction changes (speed)
    and right side determines the amount of pitch change on each tick
    (depth).
    Command 5XY: Set attack/decay register to value XY.
    Command 6XY: Set sustain/release register to value XY.
    Command 7XY: Set waveform register to value XY. If a wavetable is actively
    changing the channel's waveform at the same time, will be
    ineffective.
    Command 8XY: Set wavetable pointer. $00 stops wavetable execution.
    Command 9XY: Set pulsetable pointer. $00 stops pulsetable execution.
    Command AXY: Set filtertable pointer. $00 stops filtertable execution.
    Command BXY: Set filter control. X is resonance and Y is channel bitmask.
    $00 turns filter off and also stops filtertable execution.
    Command CXY: Set filter cutoff to XY. Can be ineffective if the filtertable is
    active and also changing the cutoff.
    Command DXY: Set mastervolume to Y, if X is $0. If X is not $0, value XY is
    copied to the timing mark location, which is playeraddress+$3F.
    Command EXY: Funktempo. XY is an index to the speedtable, tempo will alternate
    between left side value and right side value on subsequent pattern
    steps. Sets the funktempo active on all channels, but you can use
    the next command to override this per-channel.
    Command FXY: Set tempo. Values $03-$7F set tempo on all channels, values $83-
    $FF only on current channel (subtract $80 to get actual tempo).
    Tempos $00-$01 recall the funktempo values set by EXY command.
    """
    

def unroll_orderlist(an_orderlist):
    transpose = 0
    repeat = 0
    for i in range(len(an_orderlist)):
        a_byte = an_orderlist[i]

        # process pattern number
        if repeat > 0 and a_byte > 207:
            sys.exit("error: repeat in orderlist should be immediatly followed by a pattern number")
        if a_byte <= 207:
            for i in range(repeat+1):  # loops anywhere from 1 to 17 times
                unroll_pattern(a_byte, transpose)
            repeat = 0
            continue

        # process RST + restart position
        if a_byte == 255:  # RST
            # TODO: understand if looping can be enabled or disabled with choice of restart position
            restart_position = an_orderlist[i+1]
            break

        # process transpose
        # Transpose is in half steps.  Transposes changes are absolute, not additive.
        #   If transpose combined with repeat, transpose must come before a repeat
        #   Testing shows transpose ranges from '-F' (225) to '+E' (254) in orderlist
        #     Bug in goattracker documentation: says range is $E0 (224) to $FE (254)
        #     So I assume byte 224 is never used in orderlists
        assert a_byte != 224, "I don't believe byte 224 should occur in the orderlist"
        if 225 <= a_byte <= 254:  # 240 = no transposition
            transpose = a_byte - 239  # transpose range is -15 to +14
            continue

        # process repeat
        # Repeat values 1 to 16.  Instead of R0..RF, it's R1..RF,R0
        #   i.e., 'R0'=223=16reps, 'RF'=222=15 reps, 'R1'=208=1rep
        if 208 <= a_byte <= 223:
            repeat = a_byte - 207  # repeat range is 1 to 16
            continue
            

def unroll(a_song):   
    tune = a_song.subtuneOrderLists[0]  # TODO: Only processing the first subtune for now...

    unroll_orderlist(tune.ch1OrderList)
    #unroll_orderlist(tune.ch2OrderList)
    #unroll_orderlist(tune.ch3OrderList)
    

def main():
    #a_song = import_sng("consultant.sng")
    a_song = import_sng("test.sng")
    unroll(a_song)
    
    exit("Done")


if __name__ == "__main__":
    main()
