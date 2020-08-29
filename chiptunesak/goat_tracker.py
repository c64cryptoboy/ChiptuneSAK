# Code to import and export goattracker .sng files (both regular and stereo)
#
# Notes:
# - This code ignores multispeed considerations (for now)

from os import path, listdir
from os.path import isfile, join
import copy
from dataclasses import dataclass
from chiptunesak import constants  # import ARCH, C0_MIDI_NUM, project_to_absolute_path
from chiptunesak import base
from chiptunesak.byte_util import read_binary_file
from chiptunesak import rchirp
from chiptunesak.errors import *


DEFAULT_INSTR_PATH = 'res/gtInstruments/'
DEFAULT_MAX_PAT_LEN = 126

# GoatTracker constants
GT_FILE_HEADER = b'GTS5'
GT_INSTR_BYTE_LEN = 25
GT_DEFAULT_TEMPO = 6
GT_DEFAULT_FUNKTEMPOS = [9, 6]  # default alternating tempos, from GT's gplay.c

# All these MAXes are the same for goattracker 2 (1SID) and goattracker 2 stereo (2SID)
# Most found in gcommon.h
GT_MAX_SUBTUNES_PER_SONG = 32  # Each subtune gets its own orderlist of patterns
# "song" means a collection of independently-playable subtunes
GT_MAX_ELM_PER_ORDERLIST = 255  # at minimum, it must contain the endmark and following byte
GT_MAX_INSTR_PER_SONG: int = 63
GT_MAX_PATTERNS_PER_SONG = 208  # patterns can be shared across channels and subtunes
# Can populate rows 0-127, 128 is end marker.  Min row count allowed is 1.
GT_MAX_ROWS_PER_PATTERN = 128
GT_MAX_TABLE_LEN = 255

GT_REST = 0xBD  # A rest in goattracker means NOP, not rest
GT_NOTE_OFFSET = 0x60  # Note value offset
GT_MAX_NOTE_VALUE = 0xBF  # Maximum possible value for note
GT_KEY_OFF = 0xBE
GT_KEY_ON = 0xBF
GT_OL_RST = 0xFF  # order list restart marker
GT_PAT_END = 0xFF  # pattern end
GT_TEMPO_CHNG_CMD = 0x0F


class GoatTracker(base.ChiptuneSAKIO):
    """
    The IO interface for GoatTracker and GoatTracker Stereo

    Supports conversions between RChirp and GoatTracker .sng format
    """
    @classmethod
    def cts_type(cls):
        return 'GoatTracker'

    def __init__(self):
        base.ChiptuneSAKIO.__init__(self)
        self.set_options(max_pattern_len=DEFAULT_MAX_PAT_LEN,   # max pattern length if no given patterns
                         instruments=[],          # gt instrument assignments, in order
                         end_with_repeat=False,   # default is to stop GoatTracker from repeating music
                         arch=constants.DEFAULT_ARCH)  # architecture (for import to RChirp)

    def set_options(self, **kwargs):
        """
        Sets options for this module, with validation when required

        :param kwargs: keyword arguments for options
        :type kwargs: keyword arguments
        """
        for op, val in kwargs.items():
            op = op.lower()  # All option names must be lowercase
            # Check for legal maximum pattern length
            if op == 'max_pattern_len':
                if not (1 <= val <= GT_MAX_ROWS_PER_PATTERN):
                    raise Exception("Error: max rows for a pattern out of range")
            elif op == 'instruments':
                # Check to be sure instrument names don't include extensions
                for i, ins_name in enumerate(val):
                    if ins_name[-4:] == '.ins':
                        val[i] = ins_name[:-4]
            elif op == 'arch':
                if val not in constants.ARCH:
                    raise ChiptuneSAKValueError(f'Error: Unknown architecture {val}')
            # Now set the option
            self._options[op] = val

    def to_bin(self, rchirp_song, **kwargs):
        """
        Convert an RChirpSong into a GoatTracker .sng file format

        :param rchirp_song: rchirp data
        :type rchirp_song: MChirpSong
        :return: sng binary file format
        :rtype: bytearray

        :keyword options:
            * **end_with_repeat** (bool) - True if song should repeat when finished
            * **max_pattern_len** (int) - Maximum pattern length to use. Must be <= 127
            * **instruments** (list of str) - Instrument names that will be extracted from GT instruments directory
                **Note**: These instruments are in instrument order, not in voice order!  Multiple voices may use the
                same instrument, or multiple instruments may be on a voice. The instrument numbers are assigned
                in the order instruments are processed on conversion to RChirp.
        """
        if rchirp_song.cts_type() != 'RChirp':
            raise Exception("Error: GoatTracker to_bin() only supports rchirp so far")

        self.set_options(**kwargs)

        self.append_instruments_to_rchirp(rchirp_song)

        parsed_gt = GTSong()
        parsed_gt.export_rchirp_to_parsed_gt(
            rchirp_song,
            self.get_option('end_with_repeat', False),
            self.get_option('max_pattern_len', DEFAULT_MAX_PAT_LEN))
        return parsed_gt.export_parsed_gt_to_gt_binary()

    def to_file(self, rchirp_song, filename, **kwargs):
        """
        Convert and save an RChirpSong as a GoatTracker sng file

        :param rchirp_song: rchirp data
        :type rchirp_song: RChirpSong
        :param filename: output path and file name
        :type filename: str

        :keyword options:  see `to_bin()`

        """
        with open(filename, 'wb') as f:
            f.write(self.to_bin(rchirp_song, **kwargs))

    def to_rchirp(self, filename, **kwargs):
        """
        Import a GoatTracker sng file to RChirp

        :param filename: File name of .sng file
        :type filename: str
        :return: rchirp song
        :rtype: RChirpSong

        :keyword options:
            * **subtune** (int) - The subtune numer to import.  Defaults to 0
            * **arch** (str) - architecture string. Must be one defined in constants.py
        """
        self.set_options(**kwargs)
        subtune = int(self.get_option('subtune', 0))
        arch = self.get_option('arch', constants.DEFAULT_ARCH)
        rchirp_song = import_sng_file_to_rchirp(filename, subtune_number=subtune)
        rchirp_song.arch = arch
        return rchirp_song

    def append_instruments_to_rchirp(self, rchirp_song):
        for instrument in list(self.get_option('instruments')):
            add_gt_instrument_to_rchirp(rchirp_song, instrument)


@dataclass
class GtHeader:
    id: str = GT_FILE_HEADER
    song_name: str = ''
    author_name: str = ''
    copyright: str = ''
    num_subtunes: int = 0

    def to_bytes(self):
        """
        Converts header information into GT bytes.
        :return: bytes that represet the header fields
        :rtype: bytes
        """
        result = bytearray()
        result += GT_FILE_HEADER
        result += pad_or_truncate(self.song_name, 32)
        result += pad_or_truncate(self.author_name, 32)
        result += pad_or_truncate(self.copyright, 32)
        result.append(self.num_subtunes)
        return result

    def __eq__(self, other):
        return self.to_bytes() == other.to_bytes()


@dataclass
class GtPatternRow:
    note_data: int = GT_REST
    instr_num: int = 0
    command: int = 0
    command_data: int = 0

    def to_bytes(self):
        """
        Converts a pattern row into GT bytes.
        :return: bytes that represet the pattern row
        :rtype: bytes
        """
        if self.note_data is not None \
                and not (GT_NOTE_OFFSET <= self.note_data <= GT_MAX_NOTE_VALUE) \
                and self.note_data != GT_PAT_END:
            raise ChiptuneSAKValueError(f'Error: Illegal GT note value number: {self.note_data:02X}')
        if self.note_data is None:
            self.note_data = GT_REST
        else:
            if self.instr_num is None:
                raise ChiptuneSAKContentError("Error: instrument number is None")
            return bytes([self.note_data, self.instr_num, self.command, self.command_data])


PATTERN_END_ROW = GtPatternRow(note_data=GT_PAT_END)
PATTERN_EMPTY_ROW = GtPatternRow(note_data=GT_REST)


@dataclass
class GtInstrument:
    """
    Holds the parsed values from the 25-byte instrument data

    Note: the wave, pulse, filter, and speed table pointers are 1-based indexing.
    0 is reserved to mean "not pointing to anything".  However, the table bytes
    to which they point are 0-based, except for in the GoatTracker GUI where they're
    displayed as 1-based.
    """
    instr_num: int = 0
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

    def to_bytes(self):
        """
        Converts an instrument instance into GT bytes.
        :return: bytes that represet the instrument
        :rtype: bytes
        """
        result = bytearray()
        result += bytes([self.attack_decay, self.sustain_release,
                        self.wave_ptr, self.pulse_ptr, self.filter_ptr,
                        self.vib_speedtable_ptr, self.vib_delay, self.gateoff_timer,
                        self.hard_restart_1st_frame_wave])
        result += pad_or_truncate(self.inst_name, 16)
        return result

    def __eq__(self, other):
        return self.to_bytes() == other.to_bytes()

    @classmethod
    def from_bytes(cls, instr_num, bytes, starting_index=0):
        """
        Constructor that builds instrument (not supporting tables) from GT bytes

        :param instr_num: The GTSong instrument number
        :type instr_num: int
        :param bytes: Raw GT bytes
        :type bytes: bytes
        :param starting_index: starting index in bytes from which to start parsing, defaults to 0
        :type starting_index: int, optional
        :return: new GtInstrument instance
        :rtype: GtInstrument
        """
        if starting_index + GT_INSTR_BYTE_LEN - 1 > len(bytes):
            raise ChiptuneSAKValueError("Error: index out of range when instantiating GTInstrument")

        result = cls()
        result.instr_num = instr_num
        result.attack_decay = bytes[starting_index + 0]
        result.sustain_release = bytes[starting_index + 1]
        result.wave_ptr = bytes[starting_index + 2]
        result.pulse_ptr = bytes[starting_index + 3]
        result.filter_ptr = bytes[starting_index + 4]
        result.vib_speedtable_ptr = bytes[starting_index + 5]
        result.vib_delay = bytes[starting_index + 6]
        result.gateoff_timer = bytes[starting_index + 7]
        result.hard_restart_1st_frame_wave = bytes[starting_index + 8]
        result.inst_name = get_chars(bytes[starting_index + 9: starting_index + GT_INSTR_BYTE_LEN])

        return result


@dataclass
class GtTable:
    row_cnt: int = 0
    left_col: bytes = b''
    right_col: bytes = b''

    def append_table(self, a_table):
        """
        Extend this table with another

        :param a_table: A GtTable instance of one of the four GT table types
        :type a_table: GtTable
        """
        self.row_cnt += a_table.row_cnt
        if self.row_cnt >= GT_MAX_TABLE_LEN:
            raise ChiptuneSAKValueError("Error: max goattracker table size exceeded")
        self.left_col += a_table.left_col
        self.right_col += a_table.right_col

    def to_bytes(self):
        """
        Converts a table into GT bytes.
        :return: bytes that represet the table
        :rtype: bytes
        """
        result = bytearray()
        result.append(self.row_cnt)
        result += self.left_col
        result += self.right_col
        return result

    @classmethod
    def from_bytes(cls, bytes):
        """
        Constructor that builds a table from GT bytes

        :param bytes: table in raw GT bytes format
        :type bytes: bytes
        :return: new GtTable instance
        :rtype: GtTable
        """
        col_len = bytes[0]
        if len(bytes) != (col_len * 2) + 1:
            raise ChiptuneSAKValueError("Error: malformed table bytes in construction of GtTable instance")

        result = cls()
        result.row_cnt = col_len
        result.left_col = bytes[1:col_len + 1]
        result.right_col = bytes[col_len + 1:]
        return result

    def __eq__(self, other):
        return self.to_bytes() == other.to_bytes()


def import_sng_file_to_rchirp(input_filename, subtune_number=0):
    """
    Convert a GoatTracker sng file (normal or stereo) into an RChirp song instance

    :param input_filename: sng input path and filename
    :type input_filename: str
    :param subtune_number: the subtune number, defaults to 0
    :type subtune_number: int, optional
    :return: An RChirp song for the subtune
    :rtype: RChirpSong
    """
    if not input_filename.lower().endswith('.sng'):
        raise ChiptuneSAKIOError('Error: Expecting input filename that ends in ".sng"')
    if not path.exists(input_filename):
        raise ChiptuneSAKIOError('Cannot find "%s"' % input_filename)

    parsed_gt = GTSong()

    parsed_gt.import_sng_file_to_parsed_gt(input_filename)
    max_subtune_number = len(parsed_gt.subtune_orderlists) - 1

    if subtune_number < 0:
        raise ChiptuneSAKValueError('Error: subtune_number must be >= 0')
    if subtune_number > max_subtune_number:
        raise ChiptuneSAKValueError('Error: subtune_number must be <= %d' % max_subtune_number)

    rchirp = parsed_gt.import_parsed_gt_to_rchirp(subtune_number)

    return rchirp


def pattern_note_to_midi_note(pattern_note_byte, octave_offset=0):
    """
    Convert pattern note byte value into midi note value

    :param pattern_note_byte:  GT note value
    :type pattern_note_byte: int
    :param octave_offset: Should always be zero unless some weird midi offset exists
    :type octave_offset: int
    :return: Midi note number
    :rtype: int
    """
    midi_note = pattern_note_byte - (GT_NOTE_OFFSET - constants.C0_MIDI_NUM) + (octave_offset * 12)
    if not (0 <= midi_note < 128):
        raise ChiptuneSAKValueError(f"Error: illegal midi note value {midi_note} from gt {pattern_note_byte}")
    return midi_note


def get_table(an_index, file_bytes):
    """
    Used to parse wave, pulse, filter, and speed tables from raw GT bytes

    :param an_index: index for where to start parsing the file_bytes
    :type an_index: int
    :param file_bytes: bytes containing table data
    :type file_bytes: bytes
    :return: A new GtTable instance
    :rtype: GtTable
    """
    rows = file_bytes[an_index]
    # no point in checking rows > GT_MAX_TABLE_LEN, since GT_MAX_TABLE_LEN is a $FF (max byte val)
    an_index += 1

    left_entries = file_bytes[an_index:an_index + rows]
    an_index += rows

    right_entries = file_bytes[an_index:an_index + rows]

    return GtTable(row_cnt=rows, left_col=left_entries, right_col=right_entries)


def pad_or_truncate(to_pad, length):
    """
    Truncate or pad (with zeros) a GT text field
    :param to_pad: text to pad
    :type to_pad: either string or bytes
    :param length: grow or shrink input to this length ("Procrustean bed")
    :type length: int
    :return: processed text field
    :rtype:
    """
    if isinstance(to_pad, str):
        to_pad = to_pad.encode('latin-1')
    return to_pad.ljust(length, b'\0')[0:length]


def get_chars(in_bytes, trim_nulls=True):
    """
    Convert zero-padded GT text field into string

    :param in_bytes: gt text field in bytes
    :type in_bytes: bytes
    :param trim_nulls: if true, trim off the zero-padding, defaults to True
    :type trim_nulls: bool, optional
    :return: String conversion
    :rtype: str
    """
    result = in_bytes.decode('Latin-1')
    if trim_nulls:
        result = result.strip('\0')  # no interpretation, preserve encoding
    return result


def get_ins_filenames():
    """
    Get the .ins GoatTracker instrument filenames

    :return: list of filenames
    :rtype: list
    """
    dir = constants.project_to_absolute_path(DEFAULT_INSTR_PATH)
    ins_files = [f for f in listdir(dir) if isfile(join(dir, f)) and f[-4:] == '.ins']
    return ins_files


def create_gt_metadata_if_missing(rchirp_song):
    """
    Create empty GoatTracker metadata structions on rchirp if they're not present

    :param rchirp_song: an rchirp song instance
    :type rchirp_song: RChirpSong
    """
    extensions = rchirp_song.metadata.extensions

    if "gt.instruments" not in extensions:
        extensions["gt.instruments"] = bytearray()

    # stub in tables with a single entry
    if "gt.wave_table" not in extensions:
        extensions["gt.wave_table"] = bytearray(b'\x00')
    if "gt.pulse_table" not in extensions:
        extensions["gt.pulse_table"] = bytearray(b'\x00')
    if "gt.filter_table" not in extensions:
        extensions["gt.filter_table"] = bytearray(b'\x00')
    if "gt.speed_table" not in extensions:
        extensions["gt.speed_table"] = bytearray(b'\x00')


def instrument_appender(
    gt_inst_name, new_instr_num, in_wave_table, in_pulse_table,
    in_filter_table, in_speed_table, path=DEFAULT_INSTR_PATH
):
    """
    Load the named instrument's ins file and generate updated wavetables
    """

    ins_bytes = read_binary_file(constants.project_to_absolute_path(path + gt_inst_name + '.ins'))

    if ins_bytes[0:4] != b'GTI5':
        raise ChiptuneSAKValueError("Error: Invalid instrument file structure")
    file_index = 4

    # Strange, the wave/pulse/filter/vib_speedtable pointers come in with unrelocated values,
    # (seems like they'd be set to zero or something) but that's ok, since they'll be relocated
    # later in this method
    an_instrument = GtInstrument.from_bytes(new_instr_num, ins_bytes, file_index)
    file_index += GT_INSTR_BYTE_LEN

    tables = []
    for _ in range(4):
        a_table = get_table(file_index, ins_bytes)
        tables.append(a_table)
        file_index += a_table.row_cnt * 2 + 1

    # FUTURE: processing updates to these four tables and table pointers could be
    # loop-generalized instead of processed separately
    if tables[0].row_cnt == 0:
        an_instrument.wave_ptr = 0
    else:
        an_instrument.wave_ptr = in_wave_table.row_cnt + 1
    in_wave_table.append_table(tables[0])

    if tables[1].row_cnt == 0:
        an_instrument.pulse_ptr = 0
    else:
        an_instrument.pulse_ptr = in_pulse_table.row_cnt + 1
    in_pulse_table.append_table(tables[1])

    if tables[2].row_cnt == 0:
        an_instrument.filter_ptr = 0
    else:
        an_instrument.filter_ptr = in_filter_table.row_cnt + 1
    in_filter_table.append_table(tables[2])

    if tables[3].row_cnt == 0:
        an_instrument.vib_speedtable_ptr = 0
    else:
        an_instrument.vib_speedtable_ptr = in_speed_table.row_cnt + 1
    in_speed_table.append_table(tables[3])

    return (an_instrument, in_wave_table, in_pulse_table, in_filter_table, in_speed_table)


# load GoatTracker v2 instrument (.ins file) and append to song
def add_gt_instrument_to_rchirp(rchirp_song, gt_inst_name, path=DEFAULT_INSTR_PATH):
    """
    Appends a instrument binary to the RChirp metadata extensions.

    Taking an "append-only" approach to adding instruments to RChirp metadata for
    the following reasons:
    1) If RChirp instruments were imported from a sng file, the four supporting tables
       can have code that is shared (entangled) between instruments.  It would be more work
       to allow mutations (delete, move, etc.) on individual instruments (unlike SID-Wizard
       which keeps each instrument data completely separate).
    2) In practice, GoatTracker composers tend to use instrument numbers in order, so
       an append-only approach is flexible enough.

    :param rchirp_song: An RChirpSong instance
    :type rchirp_song: RChirpSong
    :param gt_inst_name: Filename of GoatTracker instrument (without path or .ins extension)
    :type gt_inst_name: str
    :param path: path from project root, defaults to 'res/gtInstruments/'
    :type path: str, optional
    """
    create_gt_metadata_if_missing(rchirp_song)
    extensions = rchirp_song.metadata.extensions

    new_instr_num = (len(extensions["gt.instruments"]) // GT_INSTR_BYTE_LEN) + 1

    (instr, wt, pt, ft, st) = instrument_appender(
        gt_inst_name,
        new_instr_num,
        GtTable.from_bytes(extensions["gt.wave_table"]),
        GtTable.from_bytes(extensions["gt.pulse_table"]),
        GtTable.from_bytes(extensions["gt.filter_table"]),
        GtTable.from_bytes(extensions["gt.speed_table"]))

    # append instrument
    extensions["gt.instruments"] += instr.to_bytes()

    # assign updated wavetables
    extensions["gt.wave_table"] = wt.to_bytes()
    extensions["gt.pulse_table"] = pt.to_bytes()
    extensions["gt.filter_table"] = ft.to_bytes()
    extensions["gt.speed_table"] = st.to_bytes()


class GTSong:
    """
    Contains parsed version of .sng file binary data.
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
        :rtype: bool
        """
        return self.num_channels >= 4

    def get_instruments_bytes(self):
        """
        Create native GT bytes for all the instruments (not including supporting tables)

        :return: byte represtation of all instruments
        :rtype: bytes
        """

        result = bytearray()
        for i in range(1, len(self.instruments)):
            result += self.instruments[i].to_bytes()
        return result

    def set_instruments_from_bytes(self, bytes):
        """
        Set GTSong's instruments from raw bytes (not including supporting tables)

        :param bytes: bytes containing instruments' data
        :type bytes: bytes
        """
        if len(bytes) % GT_INSTR_BYTE_LEN != 0:
            raise ChiptuneSAKValueError("Error: malformed instrument bytes")

        instruments = [GtInstrument()]  # start with empty instrument number 0
        for i in range(len(bytes) // GT_INSTR_BYTE_LEN):
            an_instrument = GtInstrument.from_bytes(i + 1, bytes, i * GT_INSTR_BYTE_LEN)
            instruments.append(an_instrument)

        self.instruments = instruments

    def get_orderlist(self, an_index, file_bytes):
        """
        Parse out an orderlist from file_bytes starting at an_index

        Note: orderlist length byte is length -1
            e.g., orderlist CHN1: "00 04 07 0d 09 RST00" in file as 06 00 04 07 0d 09 FF 00
            length-1 (06), followed by 7 bytes

        :param an_index: index in file_bytes from which to start parsing
        :type an_index: int
        :param file_bytes: bytes containing orderlist
        :type file_bytes: bytes
        :return: an orderlist
        :rtype: bytes
        """
        length = file_bytes[an_index] + 1  # add one for restart
        an_index += 1

        orderlist = file_bytes[an_index:an_index + length]
        an_index += length
        # check that next-to-last byte is $FF
        if file_bytes[an_index - 2] != 255:
            raise ChiptuneSAKContentError(
                "Error: Did not find expected $FF RST endmark in channel's orderlist")

        return orderlist

    def is_2sid(self, index_at_start_of_orderlists, sng_bytes):
        """
        Heuristic to determine if .sng binary is 1SID or 2SID (aka "stereo")

        :param index_at_start_of_orderlists: index of start of orderlists in sng_bytes
        :type index_at_start_of_orderlists: int
        :param sng_bytes: bytes containing orderlists
        :type sng_bytes: bytes
        :return: True if 2SID, False if 1SID
        :rtype: bool
        """
        expected_num_orderlists_for_3sid = self.headers.num_subtunes * 3
        expected_num_orderlists_for_6sid = expected_num_orderlists_for_3sid * 2
        file_index = index_at_start_of_orderlists

        orderlist_count = 0
        while True:
            index_of_ff = sng_bytes[file_index]  # get length (minus 1) of orderlist for voice
            if sng_bytes[file_index + index_of_ff] != 0xff:  # if orderlist, will be $FF
                break
            orderlist_count += 1
            file_index += index_of_ff + 2  # account for the byte after the 0xff

        if orderlist_count == expected_num_orderlists_for_3sid:
            return False

        if orderlist_count == expected_num_orderlists_for_6sid:
            return True

        raise ChiptuneSAKContentError("Error: found %d orderlists (expected %d or %d)" \
                                      % (orderlist_count,
                                         expected_num_orderlists_for_3sid,
                                         expected_num_orderlists_for_6sid))

    def import_sng_file_to_parsed_gt(self, input_filename):
        """
        Parse a goat tracker '.sng' file and put it into a GTSong instance.
        Supports 1SID and 2SID (stereo) goattracker '.sng' files.

        :param input_filename: Filename for input .sng file
        :type input_filename: str
        """
        with open(input_filename, 'rb') as f:
            sng_bytes = f.read()

        self.import_sng_binary_to_parsed_gt(sng_bytes)

    def import_sng_binary_to_parsed_gt(self, sng_bytes):
        """
        Parse a goat tracker '.sng' binary and put it into a GTSong instance.
        Supports 1SID and 2SID (stereo) goattracker '.sng' file binaries.

        :param sng_bytes: Binary contents of a sng file
        :type sng_bytes: bytes
        """

        header = GtHeader()

        header.id = sng_bytes[0:4]

        if header.id != GT_FILE_HEADER:
            raise ChiptuneSAKContentError("Error: Did not find magic header")

        header.song_name = get_chars(sng_bytes[4:36])
        header.author_name = get_chars(sng_bytes[36:68])
        header.copyright = get_chars(sng_bytes[68:100])
        header.num_subtunes = sng_bytes[100]

        if header.num_subtunes > GT_MAX_SUBTUNES_PER_SONG:
            raise ChiptuneSAKContentError("Error:  too many subtunes")

        file_index = 101
        self.headers = header

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

        if self.is_2sid(file_index, sng_bytes):  # check if this is a "stereo" sid
            self.num_channels = 6

        subtune_orderlists = []
        for _ in range(header.num_subtunes):
            channels_order_list = []
            for i in range(self.num_channels):
                channel_order_list = self.get_orderlist(file_index, sng_bytes)
                file_index += len(channel_order_list) + 1
                channels_order_list.append(channel_order_list)
            subtune_orderlists.append(channels_order_list)
        self.subtune_orderlists = subtune_orderlists

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

        inst_count = sng_bytes[file_index]  # doesn't include the NOP instrument 0
        file_index += 1

        for i in range(inst_count):
            an_instrument = GtInstrument.from_bytes(i + 1, sng_bytes, file_index)
            instruments.append(an_instrument)
            file_index += GT_INSTR_BYTE_LEN

        self.instruments = instruments

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

        (self.wave_table, self.pulse_table, self.filter_table, self.speed_table) = tables

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
            if num_rows > GT_MAX_ROWS_PER_PATTERN:
                raise ChiptuneSAKContentError("Error: Too many rows in a pattern")
            file_index += 1
            for row_num in range(num_rows):
                a_row = GtPatternRow(
                    note_data=sng_bytes[file_index],
                    instr_num=sng_bytes[file_index + 1],
                    command=sng_bytes[file_index + 2],
                    command_data=sng_bytes[file_index + 3],
                )
                if not ((GT_NOTE_OFFSET <= a_row.note_data <= GT_MAX_NOTE_VALUE)
                        or a_row.note_data == GT_PAT_END):
                    raise ChiptuneSAKContentError("Error: unexpected note data value")
                if a_row.instr_num > GT_MAX_INSTR_PER_SONG:
                    raise ChiptuneSAKValueError("Error: instrument number out of range")
                if a_row.command > 0x0F:
                    raise ChiptuneSAKValueError("Error: command number out of range")
                file_index += 4
                a_pattern.append(a_row)
            patterns.append(a_pattern)

        self.patterns = patterns

        if file_index != len(sng_bytes):
            raise ChiptuneSAKContentError("Error: bytes parsed didn't match file bytes length")

    def midi_note_to_pattern_note(self, midi_note, octave_offset=0):
        """
        Convert midi note value to pattern note value

        :param midi_note: midi note number (Note: Lowest midi note allowed = 12 (C0_MIDI_NUM)
        :type midi_note: int
        :param octave_offset: Should always be zero unless some weird midi offset exists
        :type octave_offset: int
        :return: GT note value
        :rtype: int
        """
        gt_note_value = midi_note + (GT_NOTE_OFFSET - constants.C0_MIDI_NUM) + (-1 * octave_offset * 12)
        if not (GT_NOTE_OFFSET <= gt_note_value <= GT_MAX_NOTE_VALUE):
            raise ChiptuneSAKValueError(f"Error: illegal gt note data value {gt_note_value} from midi {midi_note}")
        return gt_note_value

    def make_orderlist_entry(self, pattern_number, transposition, repeats, prev_transposition):
        """
        Makes orderlist entries from a pattern number, a transposition, and a number of repeats.

        :param pattern_number: pattern number
        :type pattern_number: int
        :param transposition: transposition in semitones
        :type transposition: int
        :param repeats: Number of times to repeat
        :type repeats: int
        :param prev_transposition: Previous transposition
        :type prev_transposition: int
        :return: list of orderlist command
        :rtype: list of int
        """
        retval = []
        # Only insert transposition (absolute) when it changes
        if transposition == prev_transposition:
            transposition = None
        elif -15 <= transposition <= 14:  # Check that transposition is in allowed range
            transposition += 0xF0  # offset for transpositions
        else:  # Instead of dying, fix transpositions by doing octave offsets until it is within range.
            while transposition > 14:
                transposition -= 12
            while transposition < -15:
                transposition += 12
            if not (-15 <= transposition <= 14):
                raise ChiptuneSAKValueError("Error: bad transposition = %d" % transposition)
            transposition += 0xF0

        # Longest possible repeat is 16, so generate as many of those as needed
        while repeats >= 16:
            if transposition is not None:
                retval.append(transposition)  # If no transposition, leave it off.
                transposition = None  # Only add transposition once
            retval.append(0xD0)  # Repeat 16 times
            retval.append(pattern_number)
            repeats -= 16

        # Now do the last one if there are any left (usually this is the only part accessed)
        if repeats > 0:
            if transposition is not None:
                retval.append(transposition)
            if repeats != 1:  # If only one time, no need to put anything in.
                retval.append(repeats - 1 + 0xD0)  # Repeat N times
            retval.append(pattern_number)

        if not all(0 <= x <= 0xFF for x in retval):
            raise ChiptuneSAKValueError("Error: Byte value error in orderlist")
        return retval

    def export_parsed_gt_to_gt_binary(self):
        """
        Convert parsed_gt into a goattracker .sng binary.

        :return: a GoatTracker sng file binary
        :rtype: bytes
        """

        gt_binary = bytearray()

        gt_binary += self.headers.to_bytes()

        for subtune in self.subtune_orderlists:
            for channel_orderlist in subtune:
                # orderlist length minus 1, strange but true
                gt_binary.append(len(channel_orderlist) - 1)
                gt_binary += bytes(channel_orderlist)

        # number of instruments (not counting NOP instrument number 0)
        gt_binary.append(len(self.instruments) - 1)

        gt_binary += self.get_instruments_bytes()
        gt_binary += self.wave_table.to_bytes()
        gt_binary += self.pulse_table.to_bytes()
        gt_binary += self.filter_table.to_bytes()
        gt_binary += self.speed_table.to_bytes()

        gt_binary.append(len(self.patterns))  # number of patterns

        for pattern in self.patterns:
            gt_binary.append(len(pattern))
            for row in pattern:
                gt_binary += row.to_bytes()

        return gt_binary

    def import_parsed_gt_to_rchirp(self, subtune_num=0):
        """
        Convert the parsed GoatTracker file into rchirp

        In GoatTracker any channel can change all the channels' tempos or just its own tempo
        at any time.  This is too complex for RChirp representation.  So this code simulates
        the playback on a frame-by-frame (aka jiffy) basis, "unrolling" the tempos.
        What's left is only per-channel tempo changes, which can be different from the other
        channels (an important tracker feature worth preserving).

        The patterns and voice orderlists found in the original GoatTracker song cannot be
        mapped 1-to-1 with rchirp.patterns and rchirp.voices[].orderlist without all of this
        complex processing.  However, we expect many C64 game music engines to have patterns
        and orderlists that can be directly mapped without much effort.

        :param subtune_num: The subtune number to convert to rchirp, defaults to 0
        :type subtune_num: int, optional
        :return: rchirp song instance
        :rtype: RChirpSong
        """

        rchirp_song = rchirp.RChirpSong()

        rchirp_song.metadata.name = self.headers.song_name
        rchirp_song.metadata.composer = self.headers.author_name
        rchirp_song.metadata.copyright = self.headers.copyright

        # init state holders for each channel to use as we step through each tick (aka frame)
        channels_state = \
            [GtChannelState(i + 1, self.subtune_orderlists[subtune_num][i]) for i in range(self.num_channels)]

        rchirp_song.voices = [rchirp.RChirpVoice(rchirp_song) for i in range(self.num_channels)]

        # TODO: Make track assignment to SID groupings not hardcoded
        if self.is_stereo:
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
        if len(self.instruments) == GT_MAX_INSTR_PER_SONG:
            ad = self.instruments[GT_MAX_INSTR_PER_SONG - 1].attack_decay
            if 0x03 <= ad <= 0x7F:
                for cs in channels_state:
                    cs.curr_tempo = ad

        global_tick = -1
        # Step through each tick (frame).  For each tick, evaluate the state of each channel.
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
                gt_row = cs.next_tick(self)
                if gt_row is None:  # if we didn't advance to a new row...
                    continue

                rc_row = rchirp.RChirpRow()
                rc_row.milliframe_num = global_tick * 1000
                rc_row.milliframe_len = cs.curr_tempo * 1000

                # KeyOff (only recorded if there's a curr_note defined)
                if cs.row_has_key_off:
                    rc_row.note_num = cs.curr_note
                    rc_row.gate = False

                # KeyOn (only recorded if there's a curr_note defined)
                if cs.row_has_key_on:
                    rc_row.note_num = cs.curr_note
                    rc_row.instr_num = gt_row.instr_num  # Why not...
                    rc_row.gate = True

                # if note_data is an actual note, then cs.curr_note has been updated
                elif cs.row_has_note:
                    rc_row.note_num = cs.curr_note
                    rc_row.instr_num = gt_row.instr_num
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
                    rc_row.milliframe_len = cs.curr_tempo * 1000

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

                    current_rc_row = rchirp_song.voices[j].last_row

                    # If row state is in progress, leave its remaining ticks alone.
                    # But if it's the very start of a new row, then override with the new global tempo
                    if cs.first_tick_of_row:
                        cs.row_ticks_left = new_tempo
                        current_rc_row.milliframe_len = new_tempo * 1000

                    cs.curr_tempo = new_tempo

        # Create note offs once all channels have hit their orderlist restart one or more times
        #    Ok, cheesy hack here.  The loop above repeats until all tracks have had a chance to restart,
        #    but it allows each voice to load in one row after that point.  Taking advantage of that, we
        #    modify that row with note off events, looking backwards to previous rows to see what the last
        #    note was to use in the note off events.
        for i, cs in enumerate(channels_state):
            rows = rchirp_song.voices[i].rows
            reversed_index = list(reversed(list(rows.keys())))
            for seek_index in reversed_index[1:]:  # skip largest row num, and work backwards
                if rows[seek_index].note_num is not None:
                    rows[reversed_index[0]].note_num = rows[seek_index].note_num
                    rows[reversed_index[0]].gate = False  # gate off
                    break

        rchirp_song.set_row_delta_values()

        rchirp_song.metadata.extensions["gt.instruments"] = self.get_instruments_bytes()
        rchirp_song.metadata.extensions["gt.wave_table"] = self.wave_table.to_bytes()
        rchirp_song.metadata.extensions["gt.pulse_table"] = self.pulse_table.to_bytes()
        rchirp_song.metadata.extensions["gt.filter_table"] = self.filter_table.to_bytes()
        rchirp_song.metadata.extensions["gt.speed_table"] = self.speed_table.to_bytes()

        # Before returning the rchirp song, might as well make use of our test cases here
        rchirp_song.integrity_check()  # Will throw assertions if there are any problems
        assert rchirp_song.is_contiguous(), "Error: rchirp representation should not be sparse"

        return rchirp_song

    def add_gt_instrument_to_parsed_gt(self, gt_inst_name, path=DEFAULT_INSTR_PATH):
        """
        Append instrument to parsed gt instance.

        Recommend using add_gt_instrument_to_rchirp() when adding instruments
        outside of this module (not adding instruments directly to GTSong).

        :param gt_inst_name: Filename of GoatTracker instrument (without path or .ins extension)
        :type gt_inst_name: str
        :param path: path from project root, defaults to 'res/gtInstruments/'
        :type path: str, optional

        """
        new_instr_num = len(self.instruments)  # no +1 here

        (instr, self.wave_table, self.pulse_table, self.filter_table, self.speed_table) = \
            instrument_appender(gt_inst_name,
                                new_instr_num,
                                self.wave_table,
                                self.pulse_table,
                                self.filter_table,
                                self.speed_table)

        self.instruments.append(instr)

    def export_rchirp_to_parsed_gt(self, rchirp_song, end_with_repeat=False, max_pattern_len=DEFAULT_MAX_PAT_LEN):
        """
        Populate GTSong instance from RChirp data.

        Instrument assignments:
        Before calling this method, the rchirp can have GoatTracker instruments appended to it
        using add_gt_instrument_to_rchirp().  Any instrument numbers found in the RChirp for which
        there is no corresponding instrument in the rchirp_song.metadata.extensions["gt.instruments"]
        will cause this code to load "SimpleTriangle" for that instrument number.

        :param rchirp_song: The rchirp song to convert
        :type rchirp_song: RChirpSong
        :param end_with_repeat: True if song should repeat when finished, defaults to False
        :type end_with_repeat: bool, optional
        :param max_pattern_len: If creating orderlist/patterns, sets the maximum pattern lengths
        :type max_pattern_len: int, optional
        """

        TRUNCATE_IF_TOO_BIG = True

        self.__init__()  # clear out anything that might be in this GTSong instance

        headers = GtHeader(
            song_name=rchirp_song.metadata.name[:32],
            author_name=rchirp_song.metadata.composer[:32],
            copyright=rchirp_song.metadata.copyright[:32],
            num_subtunes=1)
        self.headers = headers

        is_stereo = len(rchirp_song.voices) >= 4
        if len(rchirp_song.voices) > 6:
            raise ChiptuneSAKContentError("Error: Stereo SID can only support up to 6 voices")

        if is_stereo:
            num_channels = 6
        else:
            num_channels = 3
        self.num_channels = num_channels

        patterns = []  # can be shared across all channels
        orderlists = [[] for _ in range(num_channels)]  # Note: this is bad: [[]] * len(tracknums)
        instrument_nums_seen = set()
        too_many_patterns = False

        # When lowering RChirp towards a native format, if orderlists/patterns are present,
        # those should be used.  These could have come about by chiptuneSAK compression (aka
        # pattern discovery), or from having created RChirp from a source that uses patterns.
        # If no orderlists/patterns are present, the lowerer will have to create them.
        if rchirp_song.has_patterns():
            # Convert the patterns to goattracker patterns
            for ip, p in enumerate(rchirp_song.patterns):
                pattern = []  # initialize new empty pattern
                for r in p.rows:
                    gt_row = GtPatternRow()  # make a new empty pattern row
                    if r.gate:
                        gt_row.note_data = self.midi_note_to_pattern_note(r.note_num)
                        gt_row.instr_num = r.instr_num
                        instrument_nums_seen.add(r.instr_num)
                    elif r.gate is False:  # if ending a note ('false' check because tri-state)
                        gt_row.note_data = GT_KEY_OFF
                        gt_row.instr_num = r.instr_num
                    if r.new_milliframe_tempo is not None:
                        gt_row.command = GT_TEMPO_CHNG_CMD
                        # insert local channel tempo change
                        gt_row.command_data = r.new_milliframe_tempo // 1000 + 0x80
                    pattern.append(gt_row)
                pattern.append(PATTERN_END_ROW)  # finish with end row marker
                patterns.append(pattern)

            for i, v in enumerate(rchirp_song.voices):
                prev_transposition = 0  # Start out each voice with default transposition of 0
                for entry in v.orderlist:
                    ol_entry = self.make_orderlist_entry(
                        entry.pattern_num,
                        entry.transposition,
                        entry.repeats,
                        prev_transposition,
                    )
                    orderlists[i].extend(ol_entry)
                    prev_transposition = entry.transposition

        # Must create our own orderlist
        else:
            curr_pattern_num = 0

            # for each channel, get its rows, and create patterns, adding them to the
            # channel's orderlist
            for i, rchirp_voice in enumerate(rchirp_song.voices):
                rchirp_rows = rchirp_voice.rows
                pattern_row_index = 0
                pattern = []  # create a new, empty pattern
                max_row = max(rchirp_rows)
                prev_instrument = 1

                # Iterate across row num span (inclusive).  Would normally iterated over
                # sorted rchirp_rows dict keys, but since rchirp is allowed to be sparse
                # we're being careful here to insert an empty row for missing row num keys
                for j in range(max_row + 1):

                    # Convert each rchirp_row into the gt_row (used for binary gt row representation)
                    if j in rchirp_rows:
                        rchirp_row = rchirp_rows[j]
                        gt_row = GtPatternRow()

                        if rchirp_row.gate:  # if starting a note
                            gt_row.note_data = self.midi_note_to_pattern_note(rchirp_row.note_num)
                            if not (GT_NOTE_OFFSET <= gt_row.note_data <= GT_MAX_NOTE_VALUE):
                                raise ChiptuneSAKValueError('Error: Illegal note number')

                            if rchirp_row.new_instrument is not None:
                                gt_row.instr_num = rchirp_row.new_instrument
                                prev_instrument = rchirp_row.new_instrument
                                instrument_nums_seen.add(rchirp_row.new_instrument)
                            else:
                                # unlike SID-Wizard which only asserts instrument changes (on any row),
                                # goattracker asserts the current instrument with every note
                                # (goattracker can assert instrument without note, but that's a NOP)
                                gt_row.instr_num = prev_instrument

                        elif rchirp_row.gate is False:  # if ending a note ('false' check because tri-state)
                            gt_row.note_data = GT_KEY_OFF

                        if rchirp_row.new_milliframe_tempo is not None:
                            gt_row.command = GT_TEMPO_CHNG_CMD
                            # insert local channel tempo change
                            gt_row.command_data = rchirp_row.new_milliframe_tempo // 1000 + 0x80
                        pattern.append(gt_row)
                    else:
                        pattern.append(PATTERN_EMPTY_ROW)

                    pattern_row_index += 1
                    # max_pattern_len notes: index 0 to len-1 for data, index len for 0xFF pattern end mark
                    if pattern_row_index == max_pattern_len:  # if pattern is full
                        pattern.append(PATTERN_END_ROW)  # finish with end row marker
                        patterns.append(pattern)
                        orderlists[i].append(curr_pattern_num)  # append to orderlist for this channel
                        curr_pattern_num += 1
                        if curr_pattern_num >= GT_MAX_PATTERNS_PER_SONG:
                            too_many_patterns = True
                            break
                        pattern = []
                        pattern_row_index = 0
                if too_many_patterns:
                    break
                if len(pattern) > 0:  # if there's a final partially-filled pattern, add it
                    pattern.append(PATTERN_END_ROW)
                    patterns.append(pattern)
                    orderlists[i].append(curr_pattern_num)
                    curr_pattern_num += 1
                    if curr_pattern_num >= GT_MAX_PATTERNS_PER_SONG:
                        too_many_patterns = True
            if too_many_patterns:
                if TRUNCATE_IF_TOO_BIG:
                    print("Warning: too much note data, truncated patterns")
                else:
                    raise ChiptuneSAKContentError("Error: More than %d goattracker patterns created" % GT_MAX_PATTERNS_PER_SONG)

        # Usually, songs repeat.  Each channel's orderlist ends with RST00, which means restart at the
        # 1st entry in that channel's pattern list (note: orderlist is normally full of pattern numbers,
        # but the number after RST is not a pattern number, but an index back into that channel's orderlist)
        # As far as I can tell, people create an infinite loop at the end when they don't want a song to
        # repeat, so that's what this code can do.
        #
        # end_with_repeat == False in no way implies that all tracks will restart at the same time
        #
        # Design note: Thought about moving the repeat-pattern injection (end_with_repeat) into a
        # GTSong-only method, but decided against it, since RChirp-related methods are where patterns
        # are created/modified.

        if not end_with_repeat and not too_many_patterns:
            # create a new empty pattern for all channels to loop on forever
            # and add to the end of each orderlist
            loop_pattern = []
            loop_pattern.append(GtPatternRow(note_data=GT_KEY_OFF))
            loop_pattern.append(PATTERN_END_ROW)
            patterns.append(loop_pattern)
            loop_pattern_num = len(patterns) - 1
            for i in range(num_channels):
                orderlists[i].append(loop_pattern_num)  # pattern caps all voices' orderlists

        for i in range(num_channels):
            orderlists[i].append(GT_OL_RST)  # all patterns end with restart indicator
            if end_with_repeat:  # if each voice starts completely over...
                orderlists[i].append(0)  # index of start of channel order list
            else:
                orderlists[i].append(len(orderlists[i]) - 2)  # index of the empty loop pattern

        self.patterns = patterns
        self.subtune_orderlists = [orderlists]  # only one subtune, so nested in a pair of list brackets

        create_gt_metadata_if_missing(rchirp_song)
        extensions = rchirp_song.metadata.extensions

        # See if there's any instrument data to import from the RChirp
        if "gt.instruments" in extensions:
            self.set_instruments_from_bytes(extensions["gt.instruments"])
            self.wave_table = GtTable.from_bytes(extensions["gt.wave_table"])
            self.pulse_table = GtTable.from_bytes(extensions["gt.pulse_table"])
            self.filter_table = GtTable.from_bytes(extensions["gt.filter_table"])
            self.speed_table = GtTable.from_bytes(extensions["gt.speed_table"])

        # special instrument number that can be used for global tempo settings (rarely seen):
        ignore = GT_MAX_INSTR_PER_SONG - 1

        # find all instrument numbers for which an instrument binary is not already defined
        # (defined from importing from an sng and/or using add_gt_instrument_to_rchirp() )
        rchirp_inst_count = len(rchirp_song.metadata.extensions["gt.instruments"])
        unmapped_inst_nums = [x for x in instrument_nums_seen if x > rchirp_inst_count and x != ignore]

        # since we're in an instrument append-only world (at least for now), just append
        # simple triangle instrument up to the max unmatched instrument
        # This can create a lot of redundant instruments, e.g., for a seen set like 6, 3, 9, it will
        # create the Simple Triangle up to 9 times (slots 1 through 9).  Currently, we don't think it's
        # the job of goat_tracker to map an arbitrary set of instrument numbers to a consecutive
        # list starting from 1 (e.g., 3->1, 6->2, 9->3) but perhaps later, that functionality will
        # exist here.
        if len(unmapped_inst_nums) > 0:
            for i in range(rchirp_inst_count, max(unmapped_inst_nums) + 1):
                self.add_gt_instrument_to_parsed_gt("SimpleTriangle")


# Used when "running" the channels to convert them to note on/off events in time
class GtChannelState:
    # The two funktable entries are shared by all channels using a funktempo, so we have it as a
    # class-side var.  Note, this approach won't work if we want GtChannelState instances belonging
    # to and processing different songs at the same time (seems unlikely).
    # FUTURE: add instrument handling
    # FUTURE: ignoring multispeed considerations for now (would act as a simple multiplier for each)
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
        if GT_NOTE_OFFSET <= row.note_data < GT_REST:  # range $60 (C0) to $BC (G#7)
            note = row.note_data + self.curr_transposition
            assert note >= GT_NOTE_OFFSET, "Error: transpose dropped note below midi C0"
            # According to docs, allowed to transpose +3 halfsteps above the highest note (G#7)
            #    that can be entered in the GT GUI, to create a B7
            assert note <= GT_MAX_NOTE_VALUE, "Error: transpose raised note above midi B7"
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

            if row.command_data in [0x02, 0x82]:
                raise ChiptuneSAKValueError(
                    "Unimplemented: Don't know how to support tempo change with value %d" % row.command_data)

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

        # FUTUREs: Possibly handle some of the (below) commands in the future?
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
            if a_byte == 0xE0:
                raise ChiptuneSAKValueError("Unimplemented: Don't believe byte E0 should occur in the orderlist")
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


# if __name__ == "__main__":
#    pass
