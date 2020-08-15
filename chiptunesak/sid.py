# Classes for SID processing (SID header parsing, SID note extraction, etc.)
#
# SidDump class:
#    Playback details for PSID/RSID ("The SID file environment")
#    - https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt
#
#    This class supports many RSIDs.  From sid documentation concerning RSIDs:
#    "Tunes that are multi-speed and/or contain samples and/or use additional interrupt
#    sources or do busy looping will cause older SID emulators to lock up or play very
#    wrongly (if at all)."
#
#    siddump.c was very helpful as a conceptual reference for SidImport:
#    - https://csdb.dk/release/?id=152422
#    siddump has an option for "frequency recalibration", where a user specifies
#    a base frequency for better note matching (different from the siddump frequency
#    tables that were set to 440.11 tuning if running on a PAL).
#    Instead, we've implemented NTSC/PAL-specific automated tuning detection (by sampling
#    some or all notes in a subtune).  And instead of fixed frequency tables, we derive
#    tuning and architecture-based frequencies at runtime.
#
# TODO:
# - Only a small number of SIDs have been tested.  Improve code robustness by writing a 
#   driver program to test a 10 second extraction from every SID in HVSC, then autogather results.
# - SidImport:print warning if jmp or jsr to memory outside of modified memory
# - haven't tested processing of 2SID or 3SID yet
# - Fast-apeggio chord detection and reduction
# - would be nice when a note is predominately noise waveform, to mark it as percussion in the
#   RChirp.  Then when exported (say, musicXML some day), it can come out as a cross note.
#
# FUTURE:
# - According to Abbott, sid2midi created midi placeholders for digi content.  That might be useful
#   to add if the digi is, say, drums.

import csv
import math
from functools import reduce
import copy
from dataclasses import dataclass
from typing import List
from chiptunesak.constants import ARCH, DEFAULT_ARCH, CONCERT_A, freq_arch_to_freq, freq_arch_to_midi_num
from chiptunesak.byte_util import big_endian_int, little_endian_int
from chiptunesak.base import ChiptuneSAKIO, pitch_to_note_name
from chiptunesak import thin_c64_emulator
from chiptunesak.errors import ChiptuneSAKValueError, ChiptuneSAKContentError
from chiptunesak import rchirp


class SID(ChiptuneSAKIO):

    """
    Parses and imports SIDs into RChirp using 6502/6510 emulation with a thin C64 layer.

    This class is the import interface for ChiptuneSAK for SIDs.  It runs the SID in the emulator, using the
    information in the SID header to configure the driver, and captures information from the interaction of the code
    with the SID chip(s) following init and play calls.

    The resulting data can be converted to an RChirpSong object and/or written as a csv file that has a row for each
    invocation of the play routine. The csv file is useful for diagnosing how the play routine is modifying
    the SID chip and helps inform choices about the conversion of the SID music to the rchirp format.

    """

    @classmethod
    def cts_type(cls):
        return "SID"

    def __init__(self):
        ChiptuneSAKIO.__init__(self)

        self.options_with_defaults = dict(
            sid_in_filename=None,
            subtune=0,                       # subtune to extract (zero-indexed)
            vibrato_cents_margin=0,          # cents margin to control snapping to previous note
            tuning=CONCERT_A,
            seconds=60,                      # seconds to capture
            arch=DEFAULT_ARCH,               # note: overwritten if/when SID headers get parsed
            gcf_row_reduce=True,             # reduce rows via GCF of row-activity gaps
            create_gate_off_notes=True,      # allow new note starts when gate is off
            assert_gate_on_new_note=True,    # True = gate on event in delta rows with new notes
            always_include_freq=False,       # False = freq in delta rows only with new note
            verbose=True,                    # False = suppress stdout details
        )

        self.set_options(**self.options_with_defaults)

        self.sid_dump = None

    def set_options(self, **kwargs):
        """
        Sets options for this module, with validation when required

        Note: set_options gets called on __init__ (setting defaults), and a 2nd
        time if options are to be set after object instantiation.

        :param kwargs: keyword arguments for options
        :type kwargs: keyword arguments

        See to_rchirp() for possible options
        """
        for op, val in kwargs.items():
            op = op.lower()  # All option names must be lowercase
            if op not in self.options_with_defaults:
                raise ChiptuneSAKValueError('Error: Unexpected option "%s"' % (op))

            # FUTURE: May put parameter validations here

            self._options[op] = val  # Accessed via ChiptuneSAKIO.get_option()

    def capture(self):
        """
        Captures data by emulating the SID song execution

        This method calls internal methods that watch how the machine language program interacts with virtual
        SID chip(s), and records these interactions on a call-by-call basis (of the play routine).

        :return: captured SID data as a Dump object
        :rtype: Dump
        """
        importer = SidImport(self.get_option('arch'), self.get_option('tuning'))

        sid_dump = importer.import_sid(
            filename=self.get_option('sid_in_filename'),  # SID file to read in
            subtune=self.get_option('subtune'),
            vibrato_cents_margin=self.get_option('vibrato_cents_margin'),
            create_gate_off_notes=self.get_option('create_gate_off_notes'),
            assert_gate_on_new_note=self.get_option('assert_gate_on_new_note'),
            always_include_freq=self.get_option('always_include_freq'),
            seconds=self.get_option('seconds'),
            verbose=self.get_option('verbose')
        )
        self.sid_dump = sid_dump

        return sid_dump

    # def to_rchirp(self, sid_in_filename, /, **kwargs):  # 3.8...
    def to_rchirp(self, sid_in_filename, **kwargs):
        """
        Converts a SID subtune into an RChirpSong

        :param sid_in_filename: SID input filename
        :type sid_in_filename: str
        :return: SID converted to RChirpSong
        :rtype: RChirpSong

        :keyword options:
            * **subtune** (int = 0) - subtune to extract (zero-indexed)
            * **vibrato_cents_margin** (int = 0) - cents margin to control snapping to previous note
            * **tuning** (int = CONCERT_A) - tuning to use,
            * **seconds** (float = 60) -  seconds to capture
            * **arch** (string='NTSC-C64') - architecture. **Note:** overwritten if/when SID headers get parsed
            * **gcf_row_reduce** (bool = True) - reduce rows via GCF of row-activity gaps
            * **create_gate_off_notes** (bool = True) - allow new note starts when gate is off
            * **assert_gate_on_new_note** (bool = True)  - True => gate on event in delta rows with new notes
            * **always_include_freq** (bool = False) - False => freq in delta rows only with new note
            * **verbose** (bool = True) - print details to stdout
        """

        # If we don't have the SID import yet (via a prior capture() call) or if
        # the requested input filename is different than the one we used in
        # capture(), then import the SID file
        sid_dump = self.sid_dump
        if sid_dump is None or self.get_option('sid_in_filename') != sid_in_filename:
            kwargs['sid_in_filename'] = sid_in_filename
            self.set_options(**kwargs)
            sid_dump = self.capture()

        # create a more summarized representation by removing empty rows while
        # maintaining structure
        if self.get_option('gcf_row_reduce'):
            # determine which rows have activity that rchirp cares about
            rows_with_activity = [[] for _ in range(sid_dump.sid_file.sid_count)]
            for row_num, row in enumerate(sid_dump.rows):
                for chip_num, chip in enumerate(row.chips):
                    for chn in chip.channels:
                        if chn.note is not None or chn.gate_on is not None:
                            rows_with_activity[chip_num].append(row_num)
                            break
            self.reduce_rows(sid_dump, rows_with_activity)

        rchirp_song = rchirp.RChirpSong()

        rchirp_song.metadata.name = sid_dump.sid_file.name.decode("latin-1")
        rchirp_song.metadata.composer = sid_dump.sid_file.author.decode("latin-1")
        rchirp_song.metadata.copyright = sid_dump.sid_file.released.decode("latin-1")

        sid_count = sid_dump.sid_file.sid_count
        rchirp_song.voices = [
            rchirp.RChirpVoice(rchirp_song) for _ in range(sid_count * 3)]
        rchirp_song.voice_groups = [(1, 2, 3), (4, 5, 6), (7, 8, 9)][:sid_count]

        for row_num, sd_row in enumerate(sid_dump.rows):
            for chip_num, chip in enumerate(sd_row.chips):
                for chn_num, chn in enumerate(chip.channels):
                    rc_row = rchirp.RChirpRow()
                    rc_row.milliframe_num = sd_row.milliframe_num

                    if chn.note is not None:
                        rc_row.note_num = chn.note
                        rc_row.instr_num = 1  # FUTURE: Do something with instruments?

                    if chn.gate_on is not None:
                        rc_row.gate = chn.gate_on

                    rc_voice_num = chn_num + (chip_num * 3)
                    rchirp_song.voices[rc_voice_num].append_row(rc_row)

        rchirp_song.set_row_delta_values()
        return rchirp_song

    # def to_csv_file(self, output_filename, /, **kwargs):  # requires 3.8...
    def to_csv_file(self, output_filename, **kwargs):
        """
        Convert a SID subtune into a CSV file

        Each row of the csv file represents one call of the play routine.

        :param output_filename: output CSV filename
        :type output_filename: str
        """
        sid_dump = self.sid_dump
        if sid_dump is None:  # If not None, sid export already created by capture() call
            self.set_options(**kwargs)
            sid_dump = self.capture()

        # create a more summarized representation by removing empty rows while maintaining structure
        if self.get_option('gcf_row_reduce'):
            # determine which rows have activity that's important in the CSV
            rows_with_activity = [[] for _ in range(sid_dump.sid_file.sid_count)]
            for row_num, row in enumerate(sid_dump.rows):
                for chip_num, chip in enumerate(row.chips):
                    if chip.vol is not None or chip.filters is not None \
                            or chip.cutoff is not None or chip.resonance is not None:
                        rows_with_activity[chip_num].append(row_num)
                    else:
                        for chn in chip.channels:
                            if chn.freq is not None or chn.note is not None \
                                    or chn.gate_on is not None or chn.adsr is not None \
                                    or chn.waveforms is not None or chn.pulse_width is not None \
                                    or chn.filtered is not None or chn.sync_on is not None \
                                    or chn.ring_on is not None:
                                rows_with_activity[chip_num].append(row_num)
                                break
            self.reduce_rows(sid_dump, rows_with_activity)

        # create CSV
        csv_rows = []

        csv_row = ['playCall', 'Frame']
        for _ in range(sid_dump.sid_file.sid_count):
            # not going to include: no_sound_v3
            csv_row.extend(['Vol', 'Filters', 'FCutoff', 'FReson'])
            for i in range(1, 4):
                # not going to include: release_milliframe or oscil_on
                csv_row.extend([
                    'v%dFreq' % i, 'v%dDeltaFreq' % i,
                    'v%dNoteName' % i, 'v%dNote' % i, 'v%dCents' % i,
                    'v%dTrueHz' % i, 'v%dGate' % i,
                    'v%dADSR' % i, 'v%dWFs' % i, 'v%dPWidth' % i,
                    'v%dUseFilt' % i, 'v%dSync' % i, 'v%dRing' % i
                ])
        csv_rows = [csv_row]

        for row in sid_dump.rows:
            csv_row = ['%d' % row.play_call_num]
            csv_row.append('{:.3f}'.format(row.milliframe_num / 1000))

            for chip in row.chips:
                csv_row.append(self.get_val(chip.vol))
                csv_row.append(self.get_val(Chip.filters_str(chip.filters)))
                csv_row.append(self.get_val(chip.cutoff))
                csv_row.append(self.get_val(chip.resonance))

                for chn_num, chn in enumerate(chip.channels):
                    csv_row.append(self.get_val(chn.freq))
                    if chn.df is None:
                        csv_row.append('')
                    elif chn.df < 0:
                        csv_row.append('- {:d}'.format(chn.df))
                    else:
                        csv_row.append('+ {:d}'.format(chn.df))
                    csv_row.append(chn.get_note_name())
                    csv_row.append(self.get_val(chn.note))
                    if chn.freq is not None:
                        if chn.freq != 0:
                            (_, cents) = freq_arch_to_midi_num(chn.freq, sid_dump.arch, sid_dump.tuning)
                            csv_row.append('%d' % cents)
                        else:
                            csv_row.append('')
                        csv_row.append('{:.3f}'.format(
                            freq_arch_to_freq(chn.freq, sid_dump.arch)))
                    else:
                        csv_row.append('')
                        csv_row.append('')
                    csv_row.append(self.get_bool(chn.gate_on))
                    csv_row.append(self.get_val(chn.adsr, '{:04X}'))
                    csv_row.append(self.get_val(Channel.waveforms_str(chn.waveforms)))
                    csv_row.append(self.get_val(chn.pulse_width))
                    csv_row.append(self.get_bool(chn.filtered))
                    oscil = chn_num + 1  # change 0 offset to 1 offset for display
                    other_oscil = ((chn_num - 1) % 3) + 1  # same
                    csv_row.append(
                        self.get_bool(chn.sync_on, "sync%dWith%d" % (oscil, other_oscil)))
                    csv_row.append(
                        self.get_bool(chn.ring_on, "ring%dWith%d" % (oscil, other_oscil)))

            csv_rows.append(csv_row)

        with open(output_filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(csv_rows)

    def get_val(self, val, format=None):
        """
        Used to create CSV string values when not None

        :param val: str or int
        :type val: str or int
        :param format: format descriptor, defaults to None
        :type format: str, optional
        :return: empty string, passed in value (with possible formatting)
        :rtype: str or int
        """
        if val is None:
            return ''
        if format is None:
            return val
        else:
            return format.format(val)

    def get_bool(self, bool, true_str='on', false_str='off'):
        """
        Used to create CSV string values when not None

        :param bool: a boolean
        :type bool: bool
        :param true_str: string if true, defaults to 'on'
        :type true_str: str, optional
        :param false_str: string if false, defaults to 'off'
        :type false_str: str, optional
        :return: string description of boolean
        :rtype: str
        """
        if bool is None:
            return ''
        if bool:
            return true_str
        else:
            return false_str

    def reduce_rows(self, sid_dump, rows_with_activity):
        """
        The SidImport class samples SID chip state after each call to the play routine.
        This creates 1 row per play call.  For non-multispeed, in most trackers,
        this would require speed 1 playback (1 frame per row), which cannot be achieved
        (again, without multispeed).  So this method attempts to reduce the number of
        rows in the representaton.  It does so by computing the greatest common divisor
        for the count of inactive rows between active rows, and then eliminates the
        unnecessary rows (while preserving rhythm structure).

        # TODO: A row in cvs output contains all channels at a point in time.  A row
        # in rchirp contains only one channel.  When not making CVS output, better
        # results could be achieved by computing the GCD for each voice
        # independently.

        :param sid_dump: Capture of SID chip state from the subtune
        :type sid_dump: sid.Dump
        :param rows_with_activity: a list for each SID chip with a list of "active" row numbers
        :type rows_with_activity: list of lists
        :return: the row granularity (the largest common factor across all periods of inactivity)
        :rtype: int
        """

        # For each SID chip, find the min row num with activity, the max row num with
        # activity, and the minimum row granularity
        sid_row_gran = []
        sid_min_a_row = []
        sid_max_a_row = []
        for chip_num in range(sid_dump.sid_file.sid_count):
            a_rows = rows_with_activity[chip_num]
            sid_min_a_row.append(min(a_rows))
            sid_max_a_row.append(max(a_rows))
            sid_row_gran.append(reduce(math.gcd,
                (a_rows[i + 1] - a_rows[i] for i in range(len(a_rows) - 1))))  # noqa: E128

        # FUTURE coding: The Orchestrion had different metric modulations (different
        # minimum row granularities) on each SID, but this code is not yet
        # generalized enough to support this.  (As a temporary work around, if you have
        # a 2SID or 3SID and want different minimum row granularities for each
        # SID-voice grouping, then extract each SID chip output separately.)
        # Collapsing the stats across SIDs (if more than 1)...
        if len(sid_row_gran) > 1:
            row_gran = reduce(math.gcd,
                (sid_row_gran[i + 1] - sid_row_gran[i] for i in range(len(sid_row_gran) - 1)))  # noqa: E128
        else:
            row_gran = sid_row_gran[0]
        first_row = min(sid_min_a_row)
        last_row = max(sid_max_a_row)

        # reduce the rows
        i = 0
        reduced_rows = []
        for row_num in range(first_row, last_row + 1):
            if i % row_gran == 0:
                r = sid_dump.rows[row_num]
                reduced_rows.append(r)
            i += 1

        # TODO: If last_row contains a gate_on = True, may need to pad out with (row_gran-1) empty rows

        sid_dump.rows = reduced_rows
        return row_gran


class SidFile:
    def __init__(self):
        self.magic_id = None                #: PSID or RSID
        self.version = None                 #: 1 to 4
        self.data_offset = None             #: start of the C64 payload
        self.load_address = None            #: often the starting memory location
        self.init_address = None            #: often the init address
        self.play_address = None            #: often the play address
        self.num_subtunes = None            #: number of songs
        self.start_song = None              #: starting song
        self.speed = None                   #: driver type for each subtune's play routine
        self.name = None                    #: SID name
        self.author = None                  #: SID author
        self.released = None                #: SID release details
        self.c64_payload = None             #: The C64 payload
        self.load_addr_preamble = False     #: True if payload begins with 16-bit load addr
        self.flags = 0                      #: Collection of flags
        self.flag_0 = False                 #: bit 0 from flags, True = COMPUTE!'s Sidplayer MUS data
        self.flag_1 = False                 #: bit 1 from flags
        self.clock = 0                      #: video clock
        self.sid_model = 0                  #: SID1 chip type
        self.sid2_model = 0                 #: SID2 chip type
        self.sid3_model = 0                 #: SID3 chip type
        self.start_page = 0                 #: helps indicate where SID writes to memory
        self.page_length = 0                #: helps indicate where SID writes to memory
        self.sid2_address = 0               #: SID2 I/O starting address
        self.sid3_address = 0               #: SID3 I/O starting address
        self.sid_count = 1                  #: Number of SIDs used (1 to 3)
        self.is_rsid = None                 #: True if rsid, False if psid

    def contains_basic(self):
        # From documentation:
        # "If the C64 BASIC flag is set, the value at $030C must be set with the
        # song number to be played (0x00 for song 1)."
        return self.flag_1 and self.is_rsid

    def get_arch_from_headers(self):
        """
        Get ChiptuneSAK architecture type from SID headers

        :return: architecture type
        :rtype: str
        """
        if self.clock == 1:
            return 'PAL-C64'
        if self.clock == 2:
            return 'NTSC-C64'
        # for values 0 or 3:
        return DEFAULT_ARCH

    def decode_clock(self):
        """
        Decode clock numerical value to string description

        :return: system clock description
        :rtype: str
        """
        if self.clock == 1:
            return 'PAL'
        if self.clock == 2:
            return 'NTSC'
        if self.clock == 3:
            return 'NTSC and PAL'
        return 'Unknown'

    def decode_sid_model(self, sid_model_inst):
        """
        decode sid model numeric value to string description

        :param sid_model_inst: either sid_model, sid2_model, or sid3_model
        :type sid_model_inst: int
        :return: sid model description
        :rtype: str
        """
        if sid_model_inst == 1:
            return 'MOS6581'
        if sid_model_inst == 2:
            return 'MOS8580'
        if sid_model_inst == 3:
            return 'MOS6581 and MOS8580'
        return 'Unknown'

    def parse_file(self, sid_filename):
        """
        Parse the SID file header structure and extract the binary

        :param sid_filename: SID filename to parse
        :type sid_filename: str
        """
        with open(sid_filename, mode='rb') as in_file:
            sid_binary = in_file.read()

        self.parse_binary(sid_binary)

    def headers_specify_cia_timer(self, subtune):
        """
        Determines if headers specify if the if play routine will be driven by the
        CIA timer driver.  If so, speed is set by the init and/or play routine.

        :param subtune: subtune number (note: zero-indexed)
        :type subtune: int
        :return: True if speed bits designate CIA timer, None if rsid (headers don't specify)
        :rtype: bool
        """

        # FUTURE?  Assumed initial environment below (if we want to up the fidelity
        # of our emulation someday)
        #
        # PSID:
        # - if speed flag 0, raster IRQ on any value < 0x100
        # - if speed flag 1, CIA 1 timer A with NTSC/PAL KERNAL defaults with counter
        #   running and IRQs active
        #
        # RSID:
        # - raster IRQ set to 0x137, but not enabled
        # - CIA 1 timer A set to NTSC/PAL KERNAL defaults with counter running and
        #   IRQs active

        if self.is_rsid:
            return None

        if self.version == 1:
            return False

        if subtune > 31:
            if self.flag_1:     # PSID is PlaySid specific
                subtune %= 32
            else:               # C64 Compatable
                subtune = 31

        return self.speed & pow(2, subtune) != 0  # True if CIA IRQ, False if raster IRQ

    def parse_binary(self, sid_binary):
        """
        Parse a SID file binary

        Parser code based on specs from:
        - https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt
        - http://unusedino.de/ec64/technical/formats/sidplay.html

        # 'PSID' or 'RSID'.  'PSID's are simple to emulate, while 'RSID's requires a higher level
        # of fidelity to play, up to a truer C64 environment.

        :param sid_binary: a SID file binary
        :type sid_binary: bytes
        """
        self.magic_id = sid_binary[0:4]
        if self.magic_id not in (b'PSID', b'RSID'):
            raise ChiptuneSAKValueError("Error: unexpected sid magic id")
        self.is_rsid = (self.magic_id == b'RSID')

        # version is 0x0001 to 0x0004.  IFF >= 0x0002 means PSID v2NG or RSID
        self.version = big_endian_int(sid_binary[4:6])
        if not (1 <= self.version <= 4):
            raise ChiptuneSAKValueError("Error: unexpected SID version number")
        if self.is_rsid and self.version == 1:
            raise ChiptuneSAKValueError("Error: RSID can't be SID version 1")

        # Offset from the start of the file to the C64 binary data area
        self.data_offset = big_endian_int(sid_binary[6:8])
        if self.version == 1 and self.data_offset != 0x76:
            raise ChiptuneSAKValueError("Error: invalid dataoffset for v1 SID")
        if self.version > 1 and self.data_offset != 0x7C:
            raise ChiptuneSAKValueError("Error: invalid dataoffset for v2+ SID")

        # load address is the starting memory location for the C64 payload.  0x0000 indicates
        # that the first two bytes of the payload contain the little-endian load address (which
        # is always true for RSID files).
        # If the first two bytes of the C64 payload are not the load address, this must not be zero.
        # Conversely, if this is a PSID with an loading address preamble to the C64 payload, this
        # must be zero.
        self.load_address = big_endian_int(sid_binary[8:10])
        if self.load_address == 0 or self.is_rsid:
            self.load_addr_preamble = True

        # init address is the entry point for the song initialization.
        # If PSID and 0, will be set to the loading address
        # When calling init, accumulator is set to the subtune number
        self.init_address = big_endian_int(sid_binary[10:12])

        # From documentation:
        # "The start address of the machine code subroutine that can be called frequently
        # to produce a continuous sound. 0 means the initialization subroutine is
        # expected to install an interrupt handler, which then calls the music player at
        # some place. This must always be true for RSID files.""
        self.play_address = big_endian_int(sid_binary[12:14])
        if self.is_rsid and self.play_address != 0:
            raise ChiptuneSAKValueError("Error: RSIDs don't specify a play address")

        # From documentation:
        # The number of songs (or sound effects) that can be initialized by calling the
        # init address. The minimum is 1. The maximum is 256. (0x0001 - 0x0100)
        self.num_subtunes = big_endian_int(sid_binary[14:16])
        if not (1 <= self.num_subtunes <= 256):
            raise ChiptuneSAKValueError("Error: number of songs out of range")

        # the song number to be played by default
        self.start_song = big_endian_int(sid_binary[16:18])
        if not (1 <= self.start_song <= 256):
            raise ChiptuneSAKValueError("Error: starting song number out of range")

        # From documentation:
        # "For version 1 and 2 and for version 2NG, 3 and 4 with PlaySID specific flag
        # (+76) set, the 'speed' should be handled as follows:
        # Each bit in 'speed' specifies the speed for the corresponding tune number,
        # i.e. bit 0 specifies the speed for tune 1. If there are more than 32 tunes,
        # the speed specified for tune 32 is the same as tune 1, for tune 33 it is the
        # same as tune 2, etc.
        # For version 2NG, 3 and 4 with PlaySID specific flag (+76) cleared, the 'speed'
        # should be handled as follows:
        # Each bit in 'speed' specifies the speed for the corresponding tune number,
        # i.e. bit 0 specifies the speed for tune 1. If there are more than 32 tunes,
        # the speed specified for tune 32 is also used for all higher numbered tunes.
        #
        # For all version counts:
        # A 0 bit specifies vertical blank interrupt (50Hz PAL, 60Hz NTSC), and a 1 bit
        # specifies CIA 1 timer interrupt (default 60Hz).
        #
        # Surplus bits in 'speed' should be set to 0.
        # For RSID files 'speed' must always be set to 0.
        # Note that if 'play' = 0, the bits in 'speed' should still be set for backwards
        # compatibility with older SID players. New SID players running in a C64
        # environment will ignore the speed bits in this case.
        # WARNING: This field does not work in PlaySID for Amiga like it was intended,
        # therefore the above is a redefinition of the original 'speed' field in SID
        # v2NG! See also the 'clock' (video standard) field described below for 'flags'."

        self.speed = big_endian_int(sid_binary[18:22])
        if self.is_rsid and self.speed != 0:
            raise ChiptuneSAKValueError("Error: RSIDs don't specify a speed setting")

        # name, author, and released (formerally copyright) fields.  From the docs:
        # These are 32 byte long Extended ASCII encoded (Windows-1252 code page) character
        # strings. Upon evaluating the header, these fields may hold a character string of
        # 32 bytes which is not zero terminated. For less than 32 characters the string
        # should be zero terminated
        self.name = sid_binary[22:54].split(b'\x00')[0]
        self.author = sid_binary[54:86].split(b'\x00')[0]
        self.released = sid_binary[86:118].split(b'\x00')[0]

        if self.version == 1:
            self.c64_payload = sid_binary[118:]
            if self.load_addr_preamble:
                self.load_address = self.get_load_addr_from_payload()
            self.c64_payload = self.c64_payload[2:]
        else:
            self.flags = big_endian_int(sid_binary[118:120])

            # From documentation:
            # "- Bit 0 specifies format of the binary data (musPlayer):
            # 0 = built-in music player,
            # 1 = Compute!'s Sidplayer MUS data, music player must be merged.
            # If this bit is set, the appended binary data are in Compute!'s Sidplayer MUS
            # format, and does not contain a built-in music player. An external player
            # machine code must be merged to replay such a sidtune.""
            self.flag_0 = self.flags & 0b00000001 != 0

            # From documentation:
            # "- Bit 1 specifies whether the tune is PlaySID specific, e.g. uses PlaySID
            # samples (psidSpecific):
            # 0 = C64 compatible,
            # 1 = PlaySID specific (PSID v2NG, v3, v4)
            # 1 = C64 BASIC flag (RSID)
            # This is a v2NG and RSID specific field.
            # PlaySID samples were invented to facilitate playback of C64 volume register
            # samples with the original Amiga PlaySID software. PlaySID samples made samples
            # a reality on slow Amiga hardware with a player that was updated only once a
            # frame.
            # Unfortunately, converting C64 volume samples to PlaySID samples means that
            # they can no longer be played on a C64, and furthermore the conversion might
            # potentially break the non-sample part of a tune if the timing between writes
            # to the SID registers is at all altered. This follows from the ADSR bugs in the
            # SID chip.
            # Today, the speed of common hardware and the sophistication of the SID players
            # is such that there is little need for PlaySID samples. However, with all the
            # PlaySID sample PSIDs in existence there's a need to differentiate between SID
            # files containing only original C64 code and PSID files containing PlaySID
            # samples or having other PlaySID specific issues. As stated above, bit 1 in
            # 'flags' is reserved for this purpose.
            # Since RSID files do not have the need for PlaySID samples, this flag is used
            # for a different purpose: tunes that include a BASIC executable portion will
            # be played (with the BASIC portion executed) if the C64 BASIC flag is set. At
            # the same time, initAddress must be 0."
            self.flag_1 = (self.flags & 0b00000010) != 0
            if self.is_rsid:
                if self.init_address == 0:
                    if not self.flag_1:
                        raise ChiptuneSAKValueError("Error: RSID can't have init address zero unless BASIC included")
                else:
                    if self.flag_1:
                        raise ChiptuneSAKValueError("Error: RSID flag 1 can't be set (BASIC) if init address != 0")
                    # Now we can finally confirm allowed RSID init address ranges
                    # ($07E8 - $9FFF, $C000 - $CFFF)
                    if not ((2024 <= self.init_address <= 40959)
                            or (49152 <= self.init_address <= 53247)):
                        raise ChiptuneSAKValueError("Error: invalid RSID init address")

            # From documentation:
            # "- Bits 2-3 specify the video standard (clock):
            #   00 = Unknown,
            #   01 = PAL,
            #   10 = NTSC,
            #   11 = PAL and NTSC.
            # This is a v2NG specific field.
            # As can be seen from the 'speed' field, it is not possible to specify NTSC C64
            # playback. This is unfortunate, since the different clock speeds means that a
            # tune written for the NTSC C64 will be slightly detuned if played back on a PAL
            # C64. Furthermore, NTSC C64 tunes driven by a vertical blank interrupt have to
            # be converted to use the CIA 1 timer to fit into this scheme. This can cause
            # severe problems, as the NTSC refresh rate is once every 17045 cycles, while
            # the CIA 1 timer A is latched with 17095 cycles. Apart from the difference in
            # timing itself, the SID ADSR bugs can actually break the tune.
            # The 'clock' (video standard) field was introduced to circumvent this problem."
            self.clock = (self.flags & 0b0000000000001100) >> 2

            # From documentation:
            # "- Bits 4-5 specify the SID version (sidModel):
            #   00 = Unknown,
            #   01 = MOS6581,
            #   10 = MOS8580,
            #   11 = MOS6581 and MOS8580.
            # This is a v2NG specific field.""
            self.sid_model = (self.flags & 0b0000000000110000) >> 4

            # From documentation:
            # "- Bits 6-7 specify the SID version (sidModel) of the second SID:
            #   00 = Unknown,
            #   01 = MOS6581,
            #   10 = MOS8580,
            #   11 = MOS6581 and MOS8580.
            # This is a v3 specific field.
            # If bits 6-7 are set to Unknown then the second SID will be set to the same SID
            # model as the first SID."
            self.sid2_model = (self.flags & 0b0000000011000000) >> 6
            if self.sid2_model == 0:
                self.sid2_model = self.sid_model

            # From documentation:
            # "- Bits 8-9 specify the SID version (sidModel) of the third SID:
            #   00 = Unknown,
            #   01 = MOS6581,
            #   10 = MOS8580,
            #   11 = MOS6581 and MOS8580.
            # This is a v4 specific field.
            # If bits 8-9 are set to Unknown then the third SID will be set to the same SID
            # model as the first SID."
            self.sid3_model = (self.flags & 0b0000001100000000) >> 8
            if self.sid3_model == 0:
                self.sid3_model = self.sid_model

            if self.flags > 1023:
                print("Warning: bits 10-15 of flags reserved and expected to be 0")

            # From documentation:
            # "+78    BYTE startPage (relocStartPage)
            # This is a v2NG specific field.
            # This is an 8 bit number. If 'startPage' is 0, the SID file is clean, i.e. it
            # does not write outside its data range within the driver ranges. In this case
            # the largest free memory range can be determined from the start address and the
            # data length of the SID binary data. If 'startPage' is 0xFF, there is not even
            # a single free page, and driver relocation is impossible. Otherwise,
            # 'startPage' specifies the start page of the single largest free memory range
            # within the driver ranges. For example, if 'startPage' is 0x1E, this free
            # memory range starts at $1E00."
            self.start_page = sid_binary[120]

            # From documentation:
            # "+79    BYTE pageLength (relocPages)
            # This is a v2NG specific field.
            # This is an 8 bit number indicating the number of free pages after 'startPage'.
            # If 'startPage' is not 0 or 0xFF, 'pageLength' is set to the number of free
            # pages starting at 'startPage'. If 'startPage' is 0 or 0xFF, 'pageLength' must
            # be set to 0.
            # The relocation range indicated by 'startPage' and 'pageLength' should never
            # overlap or encompass the load range of the C64 data. For RSID files, the
            # relocation range should also not overlap or encompass any of the ROM areas
            # ($A000-$BFFF and $D000-$FFFF) or the reserved memory area ($0000-$03FF).
            self.page_length = sid_binary[121]
            # FUTURE: put in the checks mentioned above, generate a warning if violated

            # From documentation:
            # "+7A    BYTE secondSIDAddress
            # Valid values:
            # - 0x00 (PSID V2NG)
            # - 0x42 - 0x7F, 0xE0 - 0xFE Even values only (Version 3+)
            # This is a v3 specific field. For v2NG, it should be set to 0.
            # This is an 8 bit number indicating the address of the second SID. It specifies
            # the middle part of the address, $Dxx0, starting from value 0x42 for $D420 to
            # 0xFE for $DFE0). Only even values are valid. Ranges 0x00-0x41 ($D000-$D410) and
            # 0x80-0xDF ($D800-$DDF0) are invalid. Any invalid value means that no second SID
            # is used, like 0x00."
            self.sid2_address = sid_binary[122]
            if self.version == 2:
                if self.sid2_address > 0:
                    print("Warning: second SID address should not be defined for SID v2NG")
            elif (self.sid2_address % 2 == 1) or not ((0x42 <= self.sid2_address <= 0x7f) or (0xe0 <= self.sid2_address <= 0xfe)):
                print("Warning: invalid second SID address, therefore no 2nd SID")
                self.sid2_address = 0
            else:
                self.sid2_address = 53248 + (self.sid2_address * 16)

            # From documentation:
            # "+7B    BYTE thirdSIDAddress
            # Valid values:
            # - 0x00 (PSID V2NG, Version 3)
            # - 0x42 - 0x7F, 0xE0 - 0xFE Even values only (Version 4)
            # This is a v4 specific field. For v2NG and v3, it should be set to 0.
            # This is an 8 bit number indicating the address of the third SID. It specifies
            # the middle part of the address, $Dxx0, starting from value 0x42 for $D420 to
            # 0xFE for $DFE0). Only even values are valid. Ranges 0x00-0x41 ($D000-$D410) and
            # 0x80-0xDF ($D800-$DDF0) are invalid. Any invalid value means that no third SID
            # is used, like 0x00.
            # The address of the third SID cannot be the same as the second SID.
            self.sid3_address = sid_binary[123]
            if self.version < 4:
                if self.sid3_address > 0:
                    print("Warning: second SID address should not be defined for SID version <= 3")
            elif (self.sid3_address % 2 == 1) or not ((0x42 <= self.sid3_address <= 0x7f) or (0xe0 <= self.sid3_address <= 0xfe)):
                print("Warning: invalid third SID address, therefore no 3rd SID")
                self.sid3_address = 0
            elif self.sid2_address == self.sid3_address and self.sid3_address != 0:
                print("Warning: SID3 address cannot equal SID2 address")
                self.sid3_address = 0
            else:
                self.sid3_address = 53248 + (self.sid3_address * 16)

            if self.sid2_address > 0:
                self.sid_count += 1

            if self.sid3_address > 0:
                self.sid_count += 1

            self.c64_payload = sid_binary[124:]
            if self.load_addr_preamble:
                self.load_address = self.get_load_addr_from_payload()
                self.c64_payload = self.c64_payload[2:]

            if self.is_rsid and self.load_address < 2024:  # < $07E8
                raise ChiptuneSAKValueError("Error: invalid RSID load address")

    def get_payload_length(self):
        """
        Return the length of the C64 native code embedded in the SID file

        :return: length of SID executable binary
        :rtype: int
        """
        return len(self.c64_payload)

    def get_load_addr_from_payload(self):
        """
        Return the load address from the payload
        Note: Not all payloads begin with a 16-bit load address, see other
        documentation in this class

        :return: C64 binary starting memory location
        :rtype: int
        """
        return little_endian_int(self.c64_payload[0:2])


MAX_INSTR = 0x100000

# attack, decay, and release times in ms (4-bit setting range)
# Values should be close enough: according to https://www.c64-wiki.com/wiki/ADSR
#     "these values assume a clock rate of 1MHz, while in fact the clock rate
#     of a C64 is either 985.248 kHz PAL or 1.022727 MHz NTSC"
attack_time_ms = [2, 8, 16, 24, 38, 56, 68, 80, 100, 250, 500, 800, 1000, 3000,
                  5000, 8000]
decay_release_time_ms = [6, 24, 48, 72, 114, 168, 204, 240, 300, 750, 1500, 2400,
                         3000, 9000, 15000, 24000]


@dataclass
class Channel:
    freq: int = 0  # C64 16-bit frequency (not the true auditory frequency)
    note: int = 0  # midi note value
    adsr: int = 0  # 4 nibbles
    attack: int = 0
    decay: int = 0
    sustain: int = 0
    release: int = 0
    release_milliframe: int = None  # mf when release started, None if gate unchanged since last on
    gate_on: bool = False  # True = gate on
    sync_on: bool = False  # True = Synchronize c's Oscillator with (c-1)'s Oscillator frequency
    ring_on: bool = False  # True = c's triangle output becomes ring mod oscillators c and c-1
    oscil_on: bool = True  # False = oscillator off via test bit set (so no sound)
    waveforms: int = 0  # 4-bit waveform flags
    triangle_on: bool = False
    saw_on: bool = False
    pulse_on: bool = False
    noise_on: bool = False
    pulse_width: int = 0  # 12-bit
    filtered: bool = False  # True = channel passes through filter
    new_note: bool = False  # This state considered to be the start of a new note
    active_note: bool = False
    df: int = 0  # if no new note, record small delta in frequency (if any)

    def set_adsr_fields(self):
        """
        Set individual ADSR variables
        """
        self.attack = self.adsr >> 12
        self.decay = (self.adsr & 0x0f00) >> 8
        self.sustain = (self.adsr & 0x00f0) >> 4
        self.release = self.adsr & 0x000f

    def set_waveform_fields(self):
        """
        Set individual waveform flags (16 possible combinations)
        """
        self.triangle_on = self.waveforms & 0b0001 != 0  # noqa
        self.saw_on      = self.waveforms & 0b0010 != 0  # noqa
        self.pulse_on    = self.waveforms & 0b0100 != 0  # noqa
        self.noise_on    = self.waveforms & 0b1000 != 0  # noqa

    @classmethod
    def waveforms_str(cls, waveforms):
        """
        Create a text display of waveform flags

        :param waveforms: a 4-bit value
        :type waveforms: int
        :return: text display of waveform flags
        :rtype: str
        """
        result = ''
        if waveforms is None:
            return result
        if waveforms & 0b1000 != 0:
            result = 'n'
        else:
            result = '.'
        if waveforms & 0b0100 != 0:
            result += 'p'
        else:
            result += '.'
        if waveforms & 0b0010 != 0:
            result += 's'
        else:
            result += '.'
        if waveforms & 0b0001 != 0:
            result += 't'
        else:
            result += '.'
        return result

    def get_note_name(self):
        """
        Converts the midi note number to its string note name representation

        :return: note name
        :rtype: str
        """
        if self.note is None:
            return ''

        if self.note < 0:
            return str(self.note)  # out of range

        return pitch_to_note_name(self.note)


@dataclass
class Chip:
    vol: int = 0                    # 4-bit resolution
    filters: int = 0                # 3 bits showing if hi, band, and/or lo filters enabled
    cutoff: int = 0                 # 11-bit filter cutoff
    resonance: int = 0              # 4-bit filter resonance
    no_sound_v3: bool = False       # True = channel 3 doesn't produce sound
    channels: List[Channel] = None  # three Channel instances

    def __post_init__(self):
        self.channels = [Channel() for _ in range(3)]

    @classmethod
    def filters_str(cls, filters):
        """
        Create string representation of filter settings

        :param filters: 3-bit filter flags
        :type filters: int
        :return: string representation of filter settings
        :rtype: str
        """
        result = ''
        if filters is None:
            return result
        if filters & 0b00000100:
            result = 'h'
        else:
            result = '.'
        if filters & 0b00000010:
            result += 'b'
        else:
            result += '.'
        if filters & 0b00000001:
            result += 'l'
        else:
            result += '.'
        return result


class Row:
    def __init__(self, num_chips=1):
        self.play_call_num = None
        self.milliframe_num = None   # when the play call happened
        self.chips = None            # 1 to 3 Chip instances (2 for 2SID, 3 for 3SID)
        self.num_chips = num_chips   # Number of SID chips assumed by SID song

        if not 1 <= self.num_chips <= 3:
            raise Exception("Error: Row must specify 1 to 3 SID chips")
        self.chips = [Chip() for _ in range(self.num_chips)]

    def contains_new_note(self):
        for chip in self.chips:
            for channel in chip.channels:
                if channel.new_note and channel.note != 0:
                    return True
        return False

    def null_all(self):
        for chip in self.chips:
            chip.vol = chip.filters = chip.cutoff = chip.resonance = \
                chip.no_sound_v3 = None
            for chn in chip.channels:
                chn.freq = chn.note = chn.adsr = chn.attack = chn.decay = \
                    chn.sustain = chn.release = chn.release_milliframe = chn.gate_on = \
                    chn.sync_on = chn.ring_on = chn.oscil_on = chn.waveforms = \
                    chn.triangle_on = chn.saw_on = chn.pulse_on = chn.noise_on = \
                    chn.pulse_width = chn.filtered = chn.active_note = chn.df = \
                    chn.new_note = None


class Dump:
    def __init__(self):
        self.sid_file = None  # Contains the parsed SID file
        self.sid_base_addrs = []  # ordered list of where SIDs are memory mapped
        self.rows = []  # One row for each sample (after each call to the play routine)
        self.raw_freqs = []  # List of raw frequencies that can be used to derrive tuning
        self.arch = None  # Set by load_sid()
        self.first_row_with_note = None  # Row index for first row containing a note
        self.multispeed = 1  # 1/multispeed = num times play routine called per frame

    def is_multispeed(self):
        return self.multispeed != 1

    def load_sid(self, filename):
        """
        Load a SID file to be dumped.  Architecture will be set by SID headers.

        :param filename: [description]
        :type filename: [type]
        """
        self.sid_file = SidFile()
        self.sid_file.parse_file(filename)
        self.arch = self.sid_file.get_arch_from_headers()

    def get_tuning(self, tuning_override=CONCERT_A):
        """
        As a throw-away first pass, the sid dump can be given a small sample
        (e.g. seconds=5) from which to determine the tuning of the SID's
        frequency tables.  Using this tuning on the second full pass means
        that the cents deltas can be brought closer to 0 to make better note
        assignment decisions; especially helpful when there's wide vibrato.

        :return: tuple containing tuning, minimum_cents, and maximum_cents
        :rtype: (float, int, int)
        """
        all_cents = []
        for freq_arch in self.raw_freqs:
            if freq_arch == 0:
                continue
            if freq_arch_to_midi_num(freq_arch, self.arch, tuning_override)[0] < 0:
                continue  # ChiptuneSAK does not support midi note numbers < 0 (< C-1)
            (_, cents) = freq_arch_to_midi_num(freq_arch, self.arch, tuning=tuning_override)
            all_cents.append(cents)

        average_cents = sum(all_cents) / len(all_cents)
        maximum_cents = max(all_cents)
        minimum_cents = min(all_cents)
        assert (abs(minimum_cents) <= 50 and abs(maximum_cents) <= 50), \
            "Error: not expecting cents to deviate by more than 50 when already derrived from nearest note"

        # Check deviation from CONCERT_A
        tuning = CONCERT_A * 2**(average_cents / 1200)

        return (tuning, minimum_cents, maximum_cents)

    def trim_leading_rows(self, rows_to_remove):
        self.rows = self.rows[rows_to_remove:]


class timerHistograms:
    def __init__(self):
        self.timers = [{}, {}, {}, {}]

    def update_hist(self, timer_index, value):
        """
        Update histogram of counts for values set for the specified CIA timer

        :param timer_index: 0=cia1a, 1=cia1b, 2=cia2a, 3=cia2b
        :type timer_index: int
        :param value: the 16-bit cycle count written to the timer
        :type value: int
        """
        timer_hist = self.timers[timer_index]
        if value not in timer_hist:
            timer_hist[value] = 0
        timer_hist[value] += 1

    def print_results(self):
        labels = ['CIA 1 timer A', 'CIA 1 timer B', 'CIA 2 timer A', 'CIA 2 timer B']
        for i in range(4):
            if len(self.timers[i]) > 0:
                print("%s latch value written to %d times, histogram: %s"
                      % (labels[i], sum(self.timers[i].values()), self.timers[i]))


class SidImport:
    def __init__(self, arch=DEFAULT_ARCH, tuning=CONCERT_A):
        self.arch = arch      # Note, overwritten when SID file loaded
        self.tuning = tuning  # proper tuning can mean better vibrato note capture

        self.cpu_state = thin_c64_emulator.ThinC64Emulator()
        self.cpu_state.exit_on_empty_stack = True
        self.play_call_num = 0
        self.ordered_io_settings = []

        self.cia_event_display_count = 0

    def get_note(self, freq_arch, vibrato_cents_margin=0, prev_note=None):
        """
        For a given sound chip frequency, convert to a audio frequency
        and get the note.  If the frequency is within vibrato_cents_margin
        of the previous note, then snap to the previous note.

        :param freq_arch: A sound chip frequency
        :type freq_arch: int
        :param vibrato_cents_margin: snaps to previous note if within this margin, defaults to 0
        :type vibrato_cents_margin: int, optional
        :param prev_note: previous midi note number, defaults to None
        :type prev_note: int, optional
        :return: midi note number
        :rtype: int
        """

        MAX_CENTS_IN_NOTE = 50
        max_extent = 90  # nearly an entire note

        if not 0 <= vibrato_cents_margin < max_extent:
            raise ChiptuneSAKValueError(
                "ERROR: vibrato_cents_margin must be >= 0 and < %d" % max_extent)

        # C-1 is the lowest note ChiptuneSAK handles, and the low-end of C-1 (midi
        #     note 0) when A4=440 is ~8.0Hz
        # For frequencies to stay above 8.0Hz:
        # - NTSC C64, lowest allowed oscil freq is int(8.0*0x1000000/1022727) = 131
        # - PAL C64, lowest allowed is int(8.0*0x1000000/985248) = 136
        if freq_arch != 0 and freq_arch_to_midi_num(freq_arch, self.arch, self.tuning)[0] >= 0:
            (midi_num, cents_offset) = freq_arch_to_midi_num(freq_arch, self.arch, self.tuning)
        else:
            (midi_num, cents_offset) = (0, -MAX_CENTS_IN_NOTE + 1)  # for anything < 8Hz

        # cents scale: note-1, -45, -40, ... -10, -5, note, +5, +10, ... +40, +45, note+1
        if prev_note is not None and abs(midi_num - prev_note) == 1 \
                and cents_offset != 0 and vibrato_cents_margin != 0:

            if prev_note > midi_num:  # extend the margin into lower frequencies
                if cents_offset >= MAX_CENTS_IN_NOTE - vibrato_cents_margin:
                    midi_num = prev_note
            else:  # extend the margin into higher frequencies
                if cents_offset <= vibrato_cents_margin - MAX_CENTS_IN_NOTE:
                    midi_num = prev_note

        return midi_num

    def call_sid_init(self, init_addr, subtune):
        """
        Emulate the call to the SID's initialization routine

        Init routines do various things like relocate code/data in memory,
        setting up interrupts, etc.

        :param init_addr: The entry point for the initialization routine
        :type init_addr: int
        :param subtune: The subtune for which to initialize the playback
        :type subtune: int
        """
        self.cpu_state.init_cpu(init_addr, subtune)
        while self.cpu_state.runcpu():
            if self.cpu_state.pc > MAX_INSTR:
                raise Exception("CPU executed a high number of instructions in init routine")

        # This is often an indication of a problem
        if self.cpu_state.last_instruction == 0x00:
            print("Warning: SID init routine exited with a BRK")

    def call_sid_play(self, play_addr):
        """
        Emulate the call to the SID's play routine

        Will return once emulation:
        - hits a BRK
        - hits an RTI or RTS, if the stack is empty(ish)
        - any other criteria put into the while loop body (PC in certain
          memory ranges, etc.)

        :param play_addr: The entry point for the play routine
        :type play_addr: int
        """
        # This resets the stack each time
        self.cpu_state.init_cpu(play_addr)

        # While loop to process play routine
        while self.cpu_state.runcpu():
            if self.cpu_state.pc > MAX_INSTR:
                raise Exception("CPU executed a high number of instructions in play routine")

            # siddump.c (reference code) has an interesting bug that appears to be a feature.
            # It exits emulation on RTI and RTS if called when stack is exactly $FF (empty)
            # If the stack is nearly empty (the RTI or RTS will make it wrap) or if the stack
            # has already wrapped, it won't exit that way.  However, on the very next
            # instruction, it will exit with a BRK.  Here's how:
            # siddump.c calls the play routine with an empty stack (pointer $ff), so an RTI or
            # RTS can often cause a stack wrap.  For example:
            # the Master_of_the_Lamps_PAL.sid can exit the play routine this way:
            #     PC: 3e81 sp: ff instr: 68 PLA
            #     PC: 3e82 sp: 00 instr: a8 TAY
            #     PC: 3e83 sp: 00 instr: 68 PLA
            #     PC: 3e84 sp: 01 instr: aa TAX
            #     PC: 3e85 sp: 01 instr: 68 PLA
            #     PC: 3e86 sp: 02 instr: 40 RTI
            # This wrapped the stack all the way to x05.  This is a low-fidelity emulation, and
            # the 256-byte stack was initialized to zero, so the PC gets set to $0000
            #     PC: 0000 sp: 05 instr: 00 BRK
            # Again, low-fidelity emulation means location 0 contains a 0, and BRK is fetched
            # as the next instruction.  This exits the PLAY loop, and only one instruction past
            # the intended exit.
            # This python code base doesn't require SP to exactly == $FF for an RTS or RTI
            # to return, so we won't be using this bug/feature to exit play routines.

            # Test if exiting through KERNAL interrupt handler
            #     e.g., $EA31, $EA7E, and $EA81 exit attempts:
            if self.cpu_state.see_kernal and (0xea31 <= self.cpu_state.pc <= 0xea83):
                return  # done with play call

        # This is often an indication of a problem
        if self.cpu_state.last_instruction == 0x00:
            print("Warning: SID play routine exited with a BRK")

    def track_io_settings(self, loc, val):
        """
        Callback method that keeps track of each I/O address and what was
        written to it in the play routine.  Events are ordered.

        :param loc: [description]
        :type loc: [type]
        :param val: [description]
        :type val: [type]
        """
        if (0xd000 < loc < 0xdfff):
            self.ordered_io_settings.append((loc, val))

    def gate_was_set_for_voice(self, voice_ctrl_reg, gate_setting):
        """
        Returns True if the given voice control register was set in the play call
        with gate_setting True indicating gate was set on, or with gate_setting False
        indicating gate was set off.  Otherwise, False.

        :param voice_ctrl_reg: the voice control register location
        :type voice_ctrl_reg: int
        :param gate_setting: the gate setting to check for (True = set on, False = set off)
        :type gate_setting: bool
        :return: True if voice_ctrl_reg's gate was set to get_setting during play call
        :rtype: bool
        """
        for (io_loc, io_val) in self.ordered_io_settings:
            if io_loc == voice_ctrl_reg and (gate_setting == (io_val & 0b00000001 == 1)):
                return True
        return False

    def print_call_log_for_cia_activity(self, ordered_io_settings, play_call_num=None):
        MAX_DISPLAY_COUNT = 50

        for loc, val in ordered_io_settings:
            if self.cia_event_display_count > MAX_DISPLAY_COUNT:
                return

            if play_call_num is None:
                init_desc = 'during SID init'
            else:
                init_desc = 'on play call %d' % play_call_num

            if 0xdc00 <= loc <= 0xdcff:
                cia_desc = 'CIA 1'
            else:  # 0xdd--
                cia_desc = 'CIA 2'

            if loc in (0xdc04, 0xdc05, 0xdc0e, 0xdd04, 0xdd05, 0xdd0e):
                timer_desc = 'timer A'
            else:
                timer_desc = 'timer B'

            # process the two interrupt control registers' activity
            if loc in (0xdc0d, 0xdd0d):
                if val & 0b00000001 == 0:
                    print("%s timer A disabled %s" % (cia_desc, init_desc))
                else:
                    print("%s timer A enabled %s" % (cia_desc, init_desc))
                if val & 0b00000010 == 0:
                    print("%s timer B disabled %s" % (cia_desc, init_desc))
                else:
                    print("%s timer B enabled %s" % (cia_desc, init_desc))
            # process the four control registers' activity
            elif loc in (0xdc0e, 0xdc0f, 0xdd0e, 0xdd0f):
                if val & 0b00001000 == 0:
                    run_mode_desc = 'continuous'
                else:
                    run_mode_desc = 'one-shot'

                if val & 0b00000001 == 0:
                    print("%s %s stopped %s" % (cia_desc, timer_desc, init_desc))
                else:
                    print("%s %s started (%s run mode) %s" % (cia_desc, timer_desc, run_mode_desc, init_desc))

                if val & 0b00010000 != 0:
                    print("%s %s set by the latched timer value %s" % (cia_desc, timer_desc, init_desc))
            # process the timer latch setting activity:
            elif (0xdc04 <= loc <= 0xdc07) or (0xdd04 <= loc <= 0xdd07):
                if loc % 2 == 0:
                    byte_desc = 'lo'
                else:
                    byte_desc = 'hi'
                print("%s %s %s-byte timer latch value written %s"
                      % (cia_desc, timer_desc, byte_desc, init_desc))
            else:
                continue

            self.cia_event_display_count += 1
            if self.cia_event_display_count > MAX_DISPLAY_COUNT:
                print("etc. (too many CIA events to display)")

    def set_banks_before_psid_call(self, call_address):
        """
        Before any PSID init or play call, the bank settings must be reasserted
        (according to the expected SID environment settings, specified here
        https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt)
        This is not to be called for RSIDs.

        :param call_address: the PSID's init or play address
        :type call_address: int
        """

        if call_address < 0xa000:
            self.cpu_state.set_mem(0x0001, 0b00110111)  # 0x37: I/O, KERNAL, BASIC
        elif call_address < 0xd000:
            self.cpu_state.set_mem(0x0001, 0b00110110)  # 0x36: I/O, KERNAL
        elif call_address < 0xe000:
            self.cpu_state.set_mem(0x0001, 0b00110101)  # 0x35: I/O
        else:
            self.cpu_state.set_mem(0x0001, 0b00110100)  # 0x34: A full 64K of RAM exposed

    def import_sid(self, filename, subtune=0, vibrato_cents_margin=0, seconds=60,
                   create_gate_off_notes=True, assert_gate_on_new_note=True,
                   always_include_freq=False, verbose=True):
        """
        Emulates the SID song execution, watches how the machine language program
        interacts with the virtual SID chip(s), and records these interactions
        on a call-by-call basis (on the play routine).

        :param filename: The filename of the SID song to import
        :type filename: str
        :param subtune: the subtune to import, defaults to 0
        :type subtune: int, optional
        :param vibrato_cents_margin: if new note adjacent to old but within cents margin
                                     then, snap to old
        :type vibrato_cents_margin: int, optional
        :param seconds: seconds to capture, defaults to 60
        :type seconds: int, optional
        :param create_gate_off_notes: If True, can create new notes when gate is off
        :type bool
        :param assert_gate_on_new_note: If True, creates gate on event on new notes in
                                         delta rows
        :type bool
        :param always_include_freq: If False, only includes freq with new notes
        :type bool
        :param verbose: If False, stdout suppressed
        :type bool
        :return: A SID dump instance
        :rtype: Dump
        """

        sid_dump = Dump()
        sid_dump.load_sid(filename)

        if sid_dump.sid_file.contains_basic():
            raise ChiptuneSAKContentError("Error: BASIC code SIDs not yet supported")

        self.arch = sid_dump.arch  # override SidImport arch param to what's in the SID headers
        sid_dump.tuning = self.tuning

        sid_dump.rows = []

        # If 2SID or 3SID, note where the chips are memory mapped
        sid_dump.sid_base_addrs = [0xd400]
        if sid_dump.sid_file.sid_count > 1:
            sid_dump.sid_base_addrs.append(sid_dump.sid_file.sid2_address)
        if sid_dump.sid_file.sid_count > 2:
            sid_dump.sid_base_addrs.append(sid_dump.sid_file.sid3_address)

        if len(sid_dump.sid_file.c64_payload) + sid_dump.sid_file.load_address >= 0x10000:
            raise ChiptuneSAKValueError("Error: SID data continues past end of C64 memory")

        self.cpu_state.inject_bytes(sid_dump.sid_file.load_address, sid_dump.sid_file.c64_payload)
        self.cpu_state.set_mem_callback = self.track_io_settings

        if sid_dump.sid_file.is_rsid:
            # RSIDs only have the initial bank setup
            self.cpu_state.set_mem(0x0001, 0b00110111)  # 0x37: I/O, KERNAL, BASIC
        else:
            self.set_banks_before_psid_call(sid_dump.sid_file.init_address)

        # A clean PSID SID extraction is supposed to use either a VBI or CIA 1 timer A
        if verbose:
            if sid_dump.sid_file.is_rsid:
                print("SID type: RSID")
            else:
                print("SID type: PSID")
                if sid_dump.sid_file.headers_specify_cia_timer(subtune):
                    print("headers indicate CIA timer driven")
                else:
                    print("headers indicate VBI driven")

            if not sid_dump.sid_file.is_rsid and not sid_dump.sid_file.headers_specify_cia_timer(subtune):
                print("SID default environment assumption: all CIA timers disabled, loaded with 0xFFFF")
            else:
                print("SID default environment assumption: CIA 1 timer A active (continuous mode), "
                      + "all other off timers disabled and loaded with 0xFFFF")

        timer_hists = timerHistograms()
        self.cpu_state.debug = False

        # useful for seeing how init and play routines touch the SID
        self.cpu_state.clear_memory_usage()  # records if there was R or W activity per loc
        self.ordered_io_settings = []  # records multiple accesses to same loc
        zero_page_usage = set()  # across all init and play calls

        # Initialize the SID subtune
        self.call_sid_init(sid_dump.sid_file.init_address, subtune)

        # self.cpu_state.print_memory_usage()  # See what init touched
        self.cpu_state.update_zp_usage(zero_page_usage)
        if verbose:
            self.print_call_log_for_cia_activity(self.ordered_io_settings)

        # See if we're multispeed:
        # Note: this can't determine all RSID multispeed approaches, but should cover
        # PSID, which is supposed to use cia 1 timer a for multispeed
        if self.cpu_state.timer_was_updated(1, 'a'):
            cia_timer = self.cpu_state.get_cia_timer(1, 'a')
            timer_hists.update_hist(0, cia_timer)

            if self.arch == 'PAL-C64':
                expected_cia_timer = thin_c64_emulator.CIA_TIMER_PAL
            elif self.arch == 'NTSC-C64':
                expected_cia_timer = thin_c64_emulator.CIA_TIMER_NTSC
            else:
                raise Exception('Error: unexpected architecture type "%s"' % self.arch)

            # if not much change, multispeed will snap to 1 (actually, it'll stay at 1)
            if cia_timer != expected_cia_timer:
                if (max(cia_timer, expected_cia_timer) / min(cia_timer, expected_cia_timer) > 1.3):
                    sid_dump.multispeed = cia_timer / expected_cia_timer
                    if verbose:
                        print("multi-speed factor of x{:f}".format(
                            1 / sid_dump.multispeed))

        if self.cpu_state.timer_was_updated(1, 'b'):
            timer_hists.update_hist(1, self.cpu_state.get_cia_timer(1, 'b'))
        # FUTURE: If we want to develop this more, then check if new vector was
        # assigned to $FFFA/$FFFB (NMI) if ROMs banked out, or $0318/$0319 (NMI
        # handler) if ROMs banked in.
        if self.cpu_state.timer_was_updated(2, 'a'):
            timer_hists.update_hist(2, self.cpu_state.get_cia_timer(2, 'a'))
        if self.cpu_state.timer_was_updated(2, 'b'):
            timer_hists.update_hist(3, self.cpu_state.get_cia_timer(2, 'b'))

        # When play address is 0, the init routine installs an interrupt handler which calls
        # the music player (always the case with RSID files).  This code attempts to get the
        # play address from the interrupt vector, so we don't have to emulate the interrupt
        # driver, and instead, we can directly call the play routine.
        if sid_dump.sid_file.play_address == 0:
            if self.cpu_state.word_was_updated(0x0314):
                # get play address from the pointer to the KERNAL's standard interrupt
                # service routine ($0314 defaults to $EA31)
                sid_dump.sid_file.play_address = self.cpu_state.get_le_word(0x0314)
            elif self.cpu_state.word_was_updated(0xfffe):
                # get play address from 6502-defined IRQ vector ($FFFE defaults to $FF48)
                sid_dump.sid_file.play_address = self.cpu_state.get_le_word(0xfffe)
            else:
                raise ChiptuneSAKContentError("Error: unable to determine play address")

        max_play_calls = int(seconds * ARCH[self.arch].frame_rate * (1 / sid_dump.multispeed))

        row = Row(sid_dump.sid_file.sid_count)
        row.play_call_num = 0
        row.milliframe_num = 0

        prev_row = Row(sid_dump.sid_file.sid_count)
        prev_row.null_all()  # makes the initial delta_row work
        prev_row.play_call_num = 0
        prev_row.milliframe_num = -1  # Just as long as it's < 0

        delta_row = Row(sid_dump.sid_file.sid_count)
        delta_row.null_all()
        delta_row.play_call_num = 0
        delta_row.milliframe_num = 0

        # Note: We could set a reasonable stack pointer here if we wanted, but our
        # exit_on_empty_stack setting hopefully means we don't have to.
        # But if we did, a PSID is normally called with a JSR, so the stack pointer
        # would be $FD (only PC goes on stack) in our low-fidelity emulation when calling
        # the play routine.
        # However if play address was 0, the init routine is expected to set up an interrupt
        # to call it.  This is true for all 3,208 RSIDs in HVSC72, and for 103 of the PSIDs
        # as well.
        # On interrupt, the CPU will push the PC (hi/lo) and flags to stack.  The KERNAL
        # then pushes A, X, and Y if banked in.  If not banked in, generally user code
        # will take over that responsibility.  This means we could set the stack pointer
        # to $F9 when calling the play routine.

        self.cpu_state.debug = False

        while self.play_call_num < max_play_calls:
            if not sid_dump.sid_file.is_rsid:
                self.set_banks_before_psid_call(sid_dump.sid_file.play_address)

            self.cpu_state.clear_memory_usage()
            self.ordered_io_settings = []

            self.call_sid_play(sid_dump.sid_file.play_address)

            # self.cpu_state.print_memory_usage()  # See what play touched
            self.cpu_state.update_zp_usage(zero_page_usage)

            post_call_bank_settings = self.cpu_state.get_mem(0x0001)

            if verbose:
                self.print_call_log_for_cia_activity(self.ordered_io_settings, self.play_call_num)

            # FUTURE: Currently this code doesn't honor speed changes from the play routine
            # (e.g., accelerandos, ritardandos, etc., or digi), only the init routine.
            if self.cpu_state.timer_was_updated(1, 'a'):
                timer_hists.update_hist(0, self.cpu_state.get_cia_timer(1, 'a'))
            if self.cpu_state.timer_was_updated(1, 'b'):
                timer_hists.update_hist(1, self.cpu_state.get_cia_timer(1, 'b'))
            if self.cpu_state.timer_was_updated(2, 'a'):
                timer_hists.update_hist(2, self.cpu_state.get_cia_timer(2, 'a'))
            if self.cpu_state.timer_was_updated(2, 'b'):
                timer_hists.update_hist(3, self.cpu_state.get_cia_timer(2, 'b'))

            # need to have I/O banked in, in order to read it
            if not self.cpu_state.see_io:
                if self.play_call_num == 0 and verbose:
                    print("note: SID banks out IO after play calls")
                self.cpu_state.bank_in_IO()

            # record the SID(s) state

            # first, capture values that apply to all three channels
            for chip_num, sid_addr in enumerate(sid_dump.sid_base_addrs):
                # 11-bit filter
                # According to Leemon's Mapping the Commodore 64
                #     The range of cutoff frequencies stretches form 30Hz to ~12,000Hz
                #     frequency = (register value * 5.8) + 30Hz
                row.chips[chip_num].cutoff = (
                    (self.cpu_state.get_mem(sid_addr + 0x16) << 3)
                    | (self.cpu_state.get_mem(sid_addr + 0x15) & 0b00000111))

                # Filter Resonance Control Register
                #     Note: bits 0-2 parsed out later, bit 3 ignored
                # Bit 0: Filter the output of voice 1? 1=yes
                # Bit 1: Filter the output of voice 2? 1=yes
                # Bit 2: Filter the output of voice 3? 1=yes
                # Bit 3: Filter the output from the external input? 1=yes
                # Bit 4-7: Select filter resonance 0-15
                filt_ctrl = self.cpu_state.get_mem(sid_addr + 0x17)
                row.chips[chip_num].resonance = filt_ctrl >> 4

                # Volume and Filter Select Register
                # Bits 0-3: Select output volume (0-15)
                # Bit 4: Select low-pass filter, 1=low-pass on
                # Bit 5: Select band-pass filter, 1=band-pass on
                # Bit 6: Select high-pass filter, 1=high-pass on
                # Bit 7: Disconnect output of voice 3, 1=voice 3 off
                vol_filt_reg = self.cpu_state.get_mem(sid_addr + 0x18)
                row.chips[chip_num].vol = vol_filt_reg & 0b00001111
                row.chips[chip_num].filters = (vol_filt_reg >> 4) & 0b00000111
                row.chips[chip_num].no_sound_v3 = (vol_filt_reg & 0b10000000) != 0

                # Next, capture channel-specific values
                for chn_num, chn in enumerate(row.chips[chip_num].channels):
                    prev_chn = prev_row.chips[chip_num].channels[chn_num]

                    mem_freq = sid_addr + 7 * chn_num
                    chn.freq = self.cpu_state.get_le_word(mem_freq)
                    sid_dump.raw_freqs.append(chn.freq)

                    # 12-bit pulse
                    # According to Leemon's Mapping the Commodore 64
                    #     pulse width = (register value / 40.95)%
                    chn.pulse_width = \
                        self.cpu_state.get_le_word(sid_addr + 0x02 + 7 * chn_num) & 0xfff

                    # Voice Control Register
                    # Bit 0: Gate Bit: 1=Start attack/decay/sustain, 0=Start release
                    # Bit 1: Sync Bit: 1=Synchronize c's Oscillator with (c-1)'s Oscillator frequency
                    # Bit 2: Ring Modulation: 1=c's triangle output = ring mod oscillators c and c-1
                    # Bit 3: Test Bit: 1=Disable Oscillator (no sound)
                    # Bit 4: Select triangle waveform
                    # Bit 5: Select sawtooth waveform
                    # Bit 6: Select pulse waveform
                    # Bit 7: Select random noise waveform
                    ctrl_reg = sid_addr + 0x04 + 7 * chn_num
                    vcr = self.cpu_state.get_mem(ctrl_reg)
                    chn.gate_on     = vcr & 0b00000001 != 0  # noqa
                    chn.sync_on     = vcr & 0b00000010 != 0  # noqa
                    chn.ring_on     = vcr & 0b00000100 != 0  # noqa
                    chn.oscil_on    = vcr & 0b00001000 == 0  # noqa
                    chn.waveforms = vcr >> 4
                    chn.set_waveform_fields()

                    # ADSR as four nibbles
                    chn.adsr = ((self.cpu_state.get_mem(sid_addr + 0x05 + 7 * chn_num) << 8)
                                | self.cpu_state.get_mem(sid_addr + 0x06 + 7 * chn_num))
                    chn.set_adsr_fields()

                    voices_filtered = filt_ctrl & 0b00000111
                    # Determine if this channel is using the filter
                    chn.filtered = (voices_filtered & (2 ** chn_num)) != 0

                    # determine channel's envelope release status
                    if chn.gate_on or self.play_call_num == 0:
                        chn.release_milliframe = None  # No release in progress
                    else:  # if channel gate is off
                        if prev_chn.gate_on:  # If gate just turned off
                            # start of new release
                            chn.release_milliframe = row.milliframe_num
                        else:
                            # continue with previous value (may be None)
                            chn.release_milliframe = prev_chn.release_milliframe

                    # set within_release_window to True if envelope is still releasing
                    within_release_window = False
                    if chn.release_milliframe is not None:
                        ms_since_release = int((row.milliframe_num - chn.release_milliframe)
                                               * (ARCH[self.arch].ms_per_frame / 1000))
                        within_release_window = \
                            ms_since_release <= decay_release_time_ms[chn.release]

                    # has sound been turned off for the channel?
                    channel_off = not chn.oscil_on
                    if (chn_num == 2) and row.chips[chip_num].no_sound_v3:
                        channel_off = True

                    # True if the last (not necessarily previous) change in gate status was to on
                    gate_is_on = chn.release_milliframe is None
                    prev_gate_is_on = prev_chn.release_milliframe is None

                    # Is there an active (not released) note playing?
                    chn.active_note = (
                        not channel_off
                        and chn.waveforms != 0  # tri, saw, pulse, and/or noise active
                        and gate_is_on)

                    # what the note will or would be for the current frequency
                    chn.note = self.get_note(chn.freq, vibrato_cents_margin, prev_chn.note)

                    # Normally, we sample the state of the SID chip after a play call.
                    # However, this checks if a gate got breifly (microseconds) changed then
                    # restored in the play loop, but the note frequency was unchanged:
                    # - on->playLoop(off->on) means attack restarted on same note
                    # - off->playLoop(on->off) means restarting a note on its release phase
                    note_reasserted = (
                        chn.freq == prev_chn.freq
                        and gate_is_on == prev_gate_is_on  # if gate same before and after play call
                        and self.gate_was_set_for_voice(ctrl_reg, not prev_gate_is_on))

                    # The following logic asserts a new note when
                    # a) there's an active note (gate on with waveform) and on the previous
                    #    play call, there wasn't an active note, or
                    # b) the active note was assigned a different note value from the
                    #    previous play call's note value, or
                    # c) gate is off, but create_gate_off_notes is True, and
                    #    the note is different than the previous, and its release window
                    #    hasn't run out yet, or
                    # d) the freq is the same as the previous freq, but the voice's gate was
                    #    double toggled in the play routine
                    make_new_note = (
                        chn.active_note and (
                            not prev_chn.active_note
                            or chn.note != prev_chn.note
                            or note_reasserted
                        ) or (
                            create_gate_off_notes
                            and (chn.note != prev_chn.note or note_reasserted)
                            and within_release_window
                        )
                    )

                    chn.new_note = (self.play_call_num == 0 or make_new_note)

                    if self.play_call_num > 0:
                        delta = chn.freq - prev_chn.freq
                    else:
                        delta = 0
                    # if not a new note, but there's a change in frequency...
                    if not chn.new_note:
                        chn.df = delta
                    else:
                        chn.df = 0

            if sid_dump.first_row_with_note is None:
                if row.contains_new_note():
                    sid_dump.first_row_with_note = self.play_call_num

            # Build delta_row (shows differences from previous row)

            # for each SID chip:
            for chip_num, chip in enumerate(row.chips):
                prev_chip = prev_row.chips[chip_num]
                delta_chip = delta_row.chips[chip_num]

                include = (self.play_call_num == sid_dump.first_row_with_note)

                if include or chip.cutoff != prev_chip.cutoff:
                    delta_chip.cutoff = chip.cutoff

                if include or chip.filters != prev_chip.filters:
                    delta_chip.filters = chip.filters

                if include or chip.vol != prev_chip.vol:
                    delta_chip.vol = chip.vol

                if include or chip.resonance != prev_chip.resonance:
                    delta_chip.resonance = chip.resonance

                if include or chip.no_sound_v3 != prev_chip.no_sound_v3:
                    delta_chip.no_sound_v3 = chip.no_sound_v3

                # for each SID chip channel:
                for chn_num, chn in enumerate(row.chips[chip_num].channels):
                    prev_chn = prev_chip.channels[chn_num]
                    delta_chn = delta_chip.channels[chn_num]

                    if always_include_freq or chn.new_note:
                        delta_chn.freq = chn.freq

                    if chn.new_note:
                        delta_chn.note = chn.note

                    if chn.df > 0:
                        delta_chn.freq = chn.freq
                        delta_chn.df = chn.df

                    if chn.waveforms != prev_chn.waveforms:
                        delta_chn.waveforms = chn.waveforms
                        delta_chn.set_waveform_fields()

                    # sid2midi will (always?) fail to create new notes when the gate is simply
                    # left on (see Pool of Radiance).  This is why we have assert_gate_on_new_note.
                    if assert_gate_on_new_note and chn.new_note:
                        delta_chn.gate_on = True  # Used to influence RChirp->Chirp note creation
                    elif chn.gate_on != prev_chn.gate_on:
                        delta_chn.gate_on = chn.gate_on

                    if include or chn.sync_on != prev_chn.sync_on:
                        delta_chn.sync_on = chn.sync_on

                    if include or chn.ring_on != prev_chn.ring_on:
                        delta_chn.ring_on = chn.ring_on

                    if include or chn.oscil_on != prev_chn.oscil_on:
                        delta_chn.oscil_on = chn.oscil_on

                    if chn.adsr != prev_chn.adsr:
                        delta_chn.adsr = chn.adsr
                        delta_chn.set_adsr_fields()

                    if chn.pulse_width != prev_chn.pulse_width:
                        delta_chn.pulse_width = chn.pulse_width

                    if include or chn.filtered != prev_chn.filtered:
                        delta_chn.filtered = chn.filtered

                    # no need to include release_milliframe or new_note

                    # end of per-channel loop

            sid_dump.rows.append(delta_row)

            # setup chips and channels for next iteration:

            prev_row = copy.deepcopy(row)
            self.play_call_num += 1
            millframes_to_next_call = int(sid_dump.multispeed * 1000)

            row = Row(sid_dump.sid_file.sid_count)
            row.play_call_num = self.play_call_num
            row.milliframe_num = prev_row.milliframe_num + millframes_to_next_call

            delta_row = Row(sid_dump.sid_file.sid_count)
            delta_row.null_all()
            delta_row.play_call_num = self.play_call_num
            delta_row.milliframe_num = prev_row.milliframe_num + millframes_to_next_call

            self.cpu_state.set_mem(0x0001, post_call_bank_settings)  # possibly swap I/O back out

        if verbose:
            timer_hists.print_results()
            if len(zero_page_usage) == 0:
                print("no zero page usage!")
            else:
                print("zero page usage: %s" %
                      ', '.join(str(loc) for loc in sorted(zero_page_usage)))
        if sid_dump.first_row_with_note > 0:
            sid_dump.trim_leading_rows(sid_dump.first_row_with_note)

        return sid_dump


if __name__ == "__main__":
    print("Nothing to do")
