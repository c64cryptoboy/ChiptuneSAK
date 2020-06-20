# Classes for SID processing (SID header parsing, SID note extraction, etc.)
#
# siddump.c was very helpful as a conceptual reference for SidImport:
# - https://csdb.dk/release/?id=152422
#
# Playback details for PSID/RSID ("The SID file environment")
# - https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt
#
# SidImport TODO:
# - generate note names using chiptunesak libraires
# - generate freq tables using chiptunesak libraries
# - docstring everything
# - siddump.c has an option -c for frequency recalibration, where the user can
#   manually supply a base frequency for better note matching.  We need to
#   automate tuning detection.  Two pass approach?
# - iterate over a collection a SIDs for code coverage testing
# - implement the SID header speed settings?
#
# SidFile TODO:
# - search all the SIDs to see if they contain the KERNAL or BASIC ROMs


import csv
import math
from functools import reduce
import copy
from dataclasses import dataclass
from typing import List
from ctsConstants import DEFAULT_ARCH, ARCH, freq_arch_to_freq
from ctsBytesUtil import big_endian_int, little_endian_int
from ctsBase import ChiptuneSAKIO
import ctsThinC64Emulator
from ctsErrors import ChiptuneSAKValueError
import ctsRChirp


class SID(ChiptuneSAKIO):

    @classmethod
    def cts_type(cls):
        return "SID"

    def __init__(self):
        ChiptuneSAKIO.__init__(self)

        self.options_with_defaults = dict(
            sid_in_filename=None,
            subtune=0,           # subtune to extract
            first_frame=0,
            old_note_factor=1,
            seconds=60,          # seconds to capture
            arch=DEFAULT_ARCH,   # architecture (for import to RChirp)
            gcf_row_reduce=True  # reduce rows based on greatest common factor of row-activity gaps
        )

        self.set_options(**self.options_with_defaults)

    def set_options(self, **kwargs):
        """
        Sets options for this module, with validation when required

        Note: set_options gets called on __init__ (setting defaults), and a 2nd
        time if options are to be set after object instantiation.

        :param kwargs: keyword arguments for options
        :type kwargs: keyword arguments
        """
        for op, val in kwargs.items():
            op = op.lower()  # All option names must be lowercase
            if op not in self.options_with_defaults:
                raise ChiptuneSAKValueError('Error: Unexpected option "%s"' % (op))

            if op == 'old_note_factor':
                if val < 1:
                    val = 1

            self._options[op] = val  # Accessed via ChiptuneSAKIO.get_option()

    def capture(self):
        importer = SidImport(self.get_option('arch'))
        sid_dump = importer.import_sid(
            filename=self.get_option('sid_in_filename'),
            subtune=self.get_option('subtune'),
            first_frame=self.get_option('first_frame'),
            old_note_factor=self.get_option('old_note_factor'),
            seconds=self.get_option('seconds')
        )
        return sid_dump

    def to_rchirp(self):
        sid_dump = self.capture()

        # create a more summarized representation by removing empty rows while maintaining structure
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

        rchirp_song = ctsRChirp.RChirpSong()

        rchirp_song.metadata.name = sid_dump.sid_file.name.decode("latin-1")
        rchirp_song.metadata.composer = sid_dump.sid_file.author.decode("latin-1")
        rchirp_song.metadata.copyright = sid_dump.sid_file.released.decode("latin-1")

        sid_count = sid_dump.sid_file.sid_count
        rchirp_song.voices = [
            ctsRChirp.RChirpVoice(rchirp_song) for _ in range(sid_count * 3)]
        rchirp_song.voice_groups = [(1, 2, 3), (4, 5, 6), (7, 8, 9)][:sid_count]

        for row_num, sd_row in enumerate(sid_dump.rows):
            for chip_num, chip in enumerate(sd_row.chips):
                for chn_num, chn in enumerate(chip.channels):
                    rc_row = ctsRChirp.RChirpRow()
                    rc_row.jiffy_num = row_num
                    rc_row.jiffy_len = 1

                    if chn.note is not None:
                        rc_row.note_num = chn.note  # TODO: convert to MIDI note number first
                        rc_row.instr_num = 1  # FUTURE: Do something with instruments?

                    if chn.gate_on is not None:
                        rc_row.gate = chn.gate_on

                    rc_voice_num = chn_num + (chip_num * 3)
                    rchirp_song.voices[rc_voice_num].append_row(rc_row)

        rchirp_song.set_row_delta_values()
        return rchirp_song

    def to_csv_file(self, filename):
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
        csv_row = ['Frame']
        for _ in range(sid_dump.sid_file.sid_count):
            # not going to include: no_sound_v3
            csv_row.extend(['Vol', 'Filters', 'FCutoff', 'FReson'])
            for i in range(1, 4):
                # not going to include: release_frame or oscil_on
                csv_row.extend([
                    'v%dFreq' % i, 'v%dDeltaFreq' % i,
                    'v%dNoteName' % i, 'v%dNote' % i,
                    'v%dTrueHz' % i, 'v%dGate' % i,
                    'v%dADSR' % i, 'v%dWFs' % i, 'v%dPWidth' % i,
                    'v%dUseFil' % i, 'v%dSync' % i, 'v%dRing' % i
                ])
        csv_rows = [csv_row]

        for row in sid_dump.rows:
            csv_row = ['{:05d}'.format(row.frame_num)]

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
                        csv_row.append(chn.df, '- {:d}')
                    else:
                        csv_row.append(chn.df, '+ {:d}')
                    csv_row.append(self.get_val(Channel.get_note_name(chn.note)))
                    csv_row.append(self.get_val(chn.note))  # TODO: Not yet a midi note?
                    if chn.freq is not None:
                        csv_row.append('{:.3f}'.format(
                            freq_arch_to_freq(chn.freq, self.get_option('arch'))))
                    else:
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

        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(csv_rows)

    def get_val(self, val, format=None):
        if val is None:
            return ''
        if format is None:
            return val
        else:
            return format.format(val)

    def get_bool(self, bool, true_str='on', false_str='off'):
        if bool is None:
            return ''
        if bool:
            return true_str
        else:
            return false_str

    # compute the greatest common divisor of the inactive row counts between active rows
    # and then eliminate unnecessary rows (while preserving rhythm structure)
    def reduce_rows(self, sid_dump, rows_with_activity):
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
                reduced_rows.append(sid_dump.rows[row_num])
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
        self.speed = None                   #: bitfield for each subtune indicating playback considerations
        self.name = None                    #: SID name
        self.author = None                  #: SID author
        self.released = None                #: SID release details
        self.c64_payload = None             #: The C64 payload
        self.load_addr_preamble = False     #: True if payload begins with 16-bit load addr
        self.flags = 0                      #: Collection of flags
        self.flag_0 = 0                     #: bit 0 from flags
        self.flag_1 = 0                     #: bit 1 from flags
        self.clock = 0                      #: video clock
        self.sid_model = 0                  #: SID1 chip type
        self.sid2_model = 0                 #: SID2 chip type
        self.sid3_model = 0                 #: SID3 chip type
        self.start_page = 0                 #: helps indicate where SID writes to memory
        self.page_length = 0                #: helps indicate where SID writes to memory
        self.sid2_address = 0               #: SID2 I/O starting address
        self.sid3_address = 0               #: SID3 I/O starting address
        self.sid_count = 1                  #: Number of SIDs used (1 to 3)

    def decode_clock(self):
        """
        Decode clock numerical value to string description

        :return: system clock description
        :rtype: string
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
        :rtype: string
        """
        if sid_model_inst == 1:
            return 'MOS6581'
        if sid_model_inst == 2:
            return 'MOS8580'
        if sid_model_inst == 3:
            return 'MOS6581 and MOS8580'
        return 'Unknown'

    def parse_file(self, sid_filename):
        with open(sid_filename, mode='rb') as in_file:
            sid_binary = in_file.read()

        self.parse_binary(sid_binary)

    def parse_binary(self, sid_binary):
        # Parser code based on documentation from:
        # - https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt
        # - http://unusedino.de/ec64/technical/formats/sidplay.html

        # 'PSID' or 'RSID'.  'PSID's are simple to emulate, while 'RSID's requires a higher level
        # of fidelity to play, up to a truer C64 environment.
        # From docs: "Tunes that are multi-speed and/or contain samples and/or use additional interrupt
        # sources or do busy looping will cause older SID emulators to lock up or play very wrongly (if
        # at all)."
        self.magic_id = sid_binary[0:4]
        if self.magic_id not in (b'PSID', b'RSID'):
            raise ChiptuneSAKValueError("Error: unexpected sid magic id")

        # version is 0x0001 to 0x0004.  IFF >= 0x0002 means PSID v2NG or RSID
        self.version = big_endian_int(sid_binary[4:6])
        if not (1 <= self.version <= 4):
            raise ChiptuneSAKValueError("Error: unexpected SID version number")
        if self.magic_id == 'RSID' and self.version == 1:
            raise ChiptuneSAKValueError("Error: RSID can't be SID version 1")

        # Offset from the start of the file to the C64 binary data area
        self.data_offset = big_endian_int(sid_binary[6:8])
        if self.version == 1 and self.data_offset != 0x76:
            raise ChiptuneSAKValueError("Error: invalid dataoffset for v1 SID")
        if self.version > 1 and self.data_offset != 0x7C:
            raise ChiptuneSAKValueError("Error: invalid dataoffset for v2+ SID")

        # load address is the starting memory location for the C64 payload.  0x0000 indicates
        # that the first two bytes of the payload contain the little-endian load address (which
        # is always true for RSID files, even though they can't specify 0x0000 as the load address).
        # If the first two bytes of the C64 payload are not the load address, this must not be zero.
        # Conversely, if this is a PSID with an loading address preamble to the C64 payload, this
        # must be zero.
        self.load_address = big_endian_int(sid_binary[8:10])
        if self.load_address == 0 or self.magic_id == b'RSID':
            self.load_addr_preamble = True
        if self.magic_id == 'RSID' and self.load_address < 2024:  # < $07E8
            raise ChiptuneSAKValueError("Error: invalid RSID load address")

        # init address is the entry point for the song initialization.
        # If PSID and 0, will be set to the loading address
        # When calling init, accumulo is set to the subtune number
        self.init_address = big_endian_int(sid_binary[10:12])

        # From documentation:
        # "The start address of the machine code subroutine that can be called frequently
        # to produce a continuous sound. 0 means the initialization subroutine is
        # expected to install an interrupt handler, which then calls the music player at
        # some place. This must always be true for RSID files.""
        self.play_address = big_endian_int(sid_binary[12:14])
        if self.magic_id == 'RSID' and self.play_address != 0:
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
        if self.magic_id == 'RSID' and self.speed != 0:
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
            self.flag_0 = self.flags & 0b00000001

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
            # the same time, initAddress must be 0.""
            self.flag_1 = (self.flags & 0b00000010) >> 1
            if self.magic_id == 'RSID':
                if self.init_address == 0:
                    if self.flag_1 == 0:
                        raise ChiptuneSAKValueError("Error: RSID can't have init address zero unless BASIC included")
                else:
                    if self.flag_1 == 1:
                        raise ChiptuneSAKValueError("Error: RSID flag 1 can't be set (BASIC) if init address != 0")
                    # Now we can finally confirm allowed RSID init address ranges ($07E8 - $9FFF, $C000 - $CFFF)
                    if not ((2024 <= self.init_address <= 40959) or (49152 <= self.init_address <= 53247)):
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

    def get_payload_length(self):
        return len(self.c64_payload)

    def get_load_addr_from_payload(self):
        return little_endian_int(self.c64_payload[0:2])


MAX_INSTR = 0x100000

# attack, decay, and release times in seconds (4-bit setting range)
# Values should be close enough: according to https://www.c64-wiki.com/wiki/ADSR
#     "these values assume a clock rate of 1MHz, while in fact the clock rate
#     of a C64 is either 985.248 kHz PAL or 1.022727 MHz NTSC"
attack_time = [0.002, 0.008, 0.016, 0.024, 0.038, 0.056, 0.068, 0.080,
               0.10, 0.25, 0.5, 0.8, 1, 3, 5, 8]
decay_release_time = [0.006, 0.024, 0.048, 0.072, 0.114, 0.168, 0.204,
                      0.240, 0.30, 0.75, 1.5, 2.4, 3, 9, 15, 24]


@dataclass
class Channel:
    freq: int = 0  # 16-bit
    note: int = 0
    adsr: int = 0  # 4 nibbles
    attack: int = 0
    decay: int = 0
    sustain: int = 0
    release: int = 0
    release_frame: int = None  # If release possibly still in progress, frame # when it started
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
    df: int = 0  # if no new note, record small delta in frequency (if any)

    def set_adsr_fields(self):
        self.attack = self.adsr >> 12
        self.decay = (self.adsr & 0x0f00) >> 8
        self.sustain = (self.adsr & 0x00f0) >> 4
        self.release = self.adsr & 0x000f

    def set_waveform_fields(self):
        self.triangle_on = self.waveforms & 0b0001 != 0  # noqa
        self.saw_on      = self.waveforms & 0b0010 != 0  # noqa    
        self.pulse_on    = self.waveforms & 0b0100 != 0  # noqa                 
        self.noise_on    = self.waveforms & 0b1000 != 0  # noqa 

    @classmethod
    def waveforms_str(cls, waveforms):
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

    # TODO: throw away this note naming code stub,
    #       use ctsBase.pitch_to_note_name(midi_num) instead
    # NOTE: note 0 is "C-0", it should be 12, if C-4 is to be 60 (ChiptuneSAK plumb line)
    @classmethod
    def get_note_name(cls, note_num):
        if note_num is None:
            return ''
        note_name = [
            "C-0", "C#0", "D-0", "D#0", "E-0", "F-0", "F#0", "G-0", "G#0", "A-0", "A#0", "B-0",
            "C-1", "C#1", "D-1", "D#1", "E-1", "F-1", "F#1", "G-1", "G#1", "A-1", "A#1", "B-1",
            "C-2", "C#2", "D-2", "D#2", "E-2", "F-2", "F#2", "G-2", "G#2", "A-2", "A#2", "B-2",
            "C-3", "C#3", "D-3", "D#3", "E-3", "F-3", "F#3", "G-3", "G#3", "A-3", "A#3", "B-3",
            "C-4", "C#4", "D-4", "D#4", "E-4", "F-4", "F#4", "G-4", "G#4", "A-4", "A#4", "B-4",
            "C-5", "C#5", "D-5", "D#5", "E-5", "F-5", "F#5", "G-5", "G#5", "A-5", "A#5", "B-5",
            "C-6", "C#6", "D-6", "D#6", "E-6", "F-6", "F#6", "G-6", "G#6", "A-6", "A#6", "B-6",
            "C-7", "C#7", "D-7", "D#7", "E-7", "F-7", "F#7", "G-7", "G#7", "A-7", "A#7", "B-7"]
        return note_name[note_num]


@dataclass
class Chip:
    vol: int = 0
    filters: int = 0  # 3 bits showing if hi, band, and/or lo filters enabled
    cutoff: int = 0  # 11-bit filter cutoff
    resonance: int = 0  # 4-bit filter resonance
    no_sound_v3: bool = False  # True = channel 3 doesn't produce sound
    channels: List[Channel] = None  # three Channel instances

    def __post_init__(self):
        self.channels = [Channel() for _ in range(3)]

    @classmethod
    def filters_str(cls, filters):
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
        self.frame_num = None
        self.chips = None
        self.num_chips = num_chips

        if not 1 <= self.num_chips <= 3:
            raise Exception("Error: Row must specify 1 to 3 SID chips")
        self.chips = [Chip() for _ in range(self.num_chips)]

    # this would have been easier to maintain had I got inspect.getmembers()
    # to work correctly
    def null_all(self):
        for chip in self.chips:
            chip.vol = chip.filters = chip.cutoff = chip.resonance = \
                chip.no_sound_v3 = None
            for chn in chip.channels:
                chn.freq = chn.note = chn.adsr = chn.attack = chn.decay = \
                    chn.sustain = chn.release = chn.release_frame = chn.gate_on = \
                    chn.sync_on = chn.ring_on = chn.oscil_on = chn.waveforms = \
                    chn.triangle_on = chn.saw_on = chn.pulse_on = chn.noise_on = \
                    chn.pulse_width = chn.filtered = chn.df = None  # Not chn.new_note


@dataclass
class Dump:
    sid_file: SidFile = None
    sid_base_addrs: List[int] = None  # ordered list of where SIDs are memory mapped
    rows: List[Row] = None


class SidImport:
    def __init__(self, arch=DEFAULT_ARCH):
        self.arch = arch

        self.cpu_state = ctsThinC64Emulator.ThinC64Emulator()
        self.cpu_state.exit_on_empty_stack = True
        self.first_frame = 0
        self.frame_cnt = 0

        # 8-octave range (Note: disdump.c used 440.11 tuning)
        # TODO: Generate these at runtime, as was done in tools/sidFreqs.py
        self.freq_lo = [
            0x17, 0x27, 0x39, 0x4b, 0x5f, 0x74, 0x8a, 0xa1, 0xba, 0xd4, 0xf0, 0x0e,
            0x2d, 0x4e, 0x71, 0x96, 0xbe, 0xe8, 0x14, 0x43, 0x74, 0xa9, 0xe1, 0x1c,
            0x5a, 0x9c, 0xe2, 0x2d, 0x7c, 0xcf, 0x28, 0x85, 0xe8, 0x52, 0xc1, 0x37,
            0xb4, 0x39, 0xc5, 0x5a, 0xf7, 0x9e, 0x4f, 0x0a, 0xd1, 0xa3, 0x82, 0x6e,
            0x68, 0x71, 0x8a, 0xb3, 0xee, 0x3c, 0x9e, 0x15, 0xa2, 0x46, 0x04, 0xdc,
            0xd0, 0xe2, 0x14, 0x67, 0xdd, 0x79, 0x3c, 0x29, 0x44, 0x8d, 0x08, 0xb8,
            0xa1, 0xc5, 0x28, 0xcd, 0xba, 0xf1, 0x78, 0x53, 0x87, 0x1a, 0x10, 0x71,
            0x42, 0x89, 0x4f, 0x9b, 0x74, 0xe2, 0xf0, 0xa6, 0x0e, 0x33, 0x20, 0xff]

        self.freq_hi = [
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x02,
            0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x03, 0x03, 0x03, 0x03, 0x03, 0x04,
            0x04, 0x04, 0x04, 0x05, 0x05, 0x05, 0x06, 0x06, 0x06, 0x07, 0x07, 0x08,
            0x08, 0x09, 0x09, 0x0a, 0x0a, 0x0b, 0x0c, 0x0d, 0x0d, 0x0e, 0x0f, 0x10,
            0x11, 0x12, 0x13, 0x14, 0x15, 0x17, 0x18, 0x1a, 0x1b, 0x1d, 0x1f, 0x20,
            0x22, 0x24, 0x27, 0x29, 0x2b, 0x2e, 0x31, 0x34, 0x37, 0x3a, 0x3e, 0x41,
            0x45, 0x49, 0x4e, 0x52, 0x57, 0x5c, 0x62, 0x68, 0x6e, 0x75, 0x7c, 0x83,
            0x8b, 0x93, 0x9c, 0xa5, 0xaf, 0xb9, 0xc4, 0xd0, 0xdd, 0xea, 0xf8, 0xff]

    @classmethod
    def get_note(cls, freq, prev_note, old_note_factor, freq_lo, freq_hi):
        # TODO:  This functionality might move out of this class when replaced
        # by Knapp logic
        #
        # Note: in combination with the frequency tables here, this code determines that
        # C64 freq 602 = C#1.  According to https://sta.c64.org/cbm64sndfreq.html
        # for 440 tuning, C#1 should be freq 587 which is 34.6Hz.
        # However, I think the webpage assume C0 is 0, not 12, and it's not clear if
        # freq -> Hz is for PAL or for NTSC (probably PAL)
        # In ChiptunesSAK C4 = note 60 = 261.63Hz
        #
        # siddump.c described the old_note_factor thusly:
        #     -o<value> "Oldnote-sticky" factor. Default 1, increase for better vibrato display
        #               (when increased, requires well calibrated frequencies)
        dist = 0x7fffffff
        return_note = None
        for d in range(96):
            cmp_freq = freq_lo[d] | freq_hi[d] << 8
            if abs(freq - cmp_freq) < dist:
                dist = abs(freq - cmp_freq)
                # Favor the old note to help ignore vibrato
                if prev_note == d:
                    dist /= old_note_factor
                return_note = d
        return return_note

    def call_sid_init(self, init_addr, subtune):
        self.cpu_state.init_cpu(init_addr, subtune)
        while self.cpu_state.runcpu():
            if self.cpu_state.pc > MAX_INSTR:
                raise Exception("CPU executed a high number of instructions in init routine")

    def call_sid_play(self, play_addr):
        # This resets the stack each time
        self.cpu_state.init_cpu(play_addr)

        # While loop to process play routine
        # Exits on BRK, on RTI or RTS if stack empty(ish), and any exit criteria in the
        #     while loop body (PC in certain memory ranges, etc.)
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
            #     e.g., $EA31, $EA73, and $EA81 exit attempts:
            if self.cpu_state.see_kernal and (0xea31 <= self.cpu_state.pc <= 0xea83):
                return  # done with play call

    def import_sid(self, filename, subtune=0, first_frame=0, old_note_factor=1, seconds=60):
        sid_dump = Dump()
        sid_dump.sid_file = SidFile()
        sid_dump.sid_file.parse_file(filename)
        sid_dump.rows = []

        # If 2SID or 3SID, note where the chips are memory mapped
        sid_dump.sid_base_addrs = [0xd400]
        if sid_dump.sid_file.sid_count > 1:
            sid_dump.sid_base_addrs.append(sid_dump.sid_file.sid2_address)
        if sid_dump.sid_file.sid_count > 2:
            sid_dump.sid_base_addrs.append(sid_dump.sid_file.sid3_address)

        # TODO: Implement this documentation (below)
        """
        From: https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt

        TODO: PSID/RSID: when speed flag set to CIA for the subtune, then 16,421 cycle
        delay for PAL, and 17,045 cycle delay for NTSC

        For PSID Files
        --------------

        The default C64 environment for PSID files is as follows:

        VIC           : IRQ set to any raster value less than 0x100. Enabled when
                    speed flag is 0, otherwise disabled.
        CIA 1 timer A : set to 60Hz (0x4025 for PAL and 0x4295 for NTSC) with the
                    counter running. IRQs active when speed flag is 1, otherwise
                    IRQs are disabled.
        Other timers  : disabled and loaded with 0xFFFF.

        When the init and play addresses are called the bank register value must be
        written for every call and the value is calculated as follows:

        if   address <  $A000 -> 0x37 // I/O, Kernal-ROM, Basic-ROM
        else address <  $D000 -> 0x36 // I/O, Kernal-ROM
        else address >= $E000 -> 0x35 // I/O only
        else                  -> 0x34 // RAM only

        For RSID Files
        --------------

        The default C64 environment for RSID files is as follows:

        VIC           : IRQ set to raster 0x137, but not enabled.
        CIA 1 timer A : set to 60Hz (0x4025 for PAL and 0x4295 for NTSC) with the
                    counter running and IRQs active.
        Other timers  : disabled and loaded with 0xFFFF.
        Bank register : 0x37

        A side effect of the bank register is that init MUST NOT be located under a
        ROM/IO memory area (addresses $A000-$BFFF and $D000-$FFFF) or outside the
        load image. Since every effort needs to be made to run the tune on a real
        C64 the load address of the image MUST NOT be set lower than $07E8.

        If the C64 BASIC flag is set, the value at $030C must be set with the song
        number to be played (0x00 for song 1).
        """

        if len(sid_dump.sid_file.c64_payload) + sid_dump.sid_file.load_address >= 0x10000:
            raise ChiptuneSAKValueError("Error: SID data continues past end of C64 memory")

        self.cpu_state.inject_bytes(sid_dump.sid_file.load_address, sid_dump.sid_file.c64_payload)

        self.cpu_state.set_mem(0x01, 0b00110111)  # set default memory banking

        self.cpu_state.debug = False
        self.call_sid_init(sid_dump.sid_file.init_address, subtune)

        # When play address is 0, the init routine installs an interrupt handler which calls
        # the music player (always the case with RSID files).  This attempts to get the play
        # address from the interrupt vector:
        # TODO? Could actually monitor memory to see which one(s) the init changed.
        if sid_dump.sid_file.play_address == 0:
            if self.cpu_state.see_kernal:
                # get play address from the pointer to the routine normally called by
                # the CIA #1 timer B ($0314 defaults to $EA31)
                sid_dump.sid_file.play_address = self.cpu_state.get_le_word(0x0314)
            else:
                # get play address from 6502-defined IRQ vector ($FFFE defaults to $FF48)
                sid_dump.sid_file.play_address = self.cpu_state.get_le_word(0xfffe)

        self.frame_cnt = 0  # TODO:  Not really frames if multi-speed, rename to play_call_cnt?

        frames_to_capture = int(seconds * ARCH[self.arch].frame_rate)

        row = Row(sid_dump.sid_file.sid_count)
        row.frame_num = self.frame_cnt

        prev_row = Row(sid_dump.sid_file.sid_count)
        prev_row.null_all()  # makes the initial delta_row work
        prev_row.frame_num = self.frame_cnt - 1

        delta_row = Row(sid_dump.sid_file.sid_count)
        delta_row.null_all()
        delta_row.frame_num = self.frame_cnt

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
        while self.frame_cnt < first_frame + frames_to_capture:
            self.call_sid_play(sid_dump.sid_file.play_address)

            # TODO: Temporarily make sure I/O is swapped in (in case end of play routine swaps
            # it out), then restore to what it was, since we're using get_mem to look at SID
            # registers

            # record the SID(s) state at the end of the frame

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
                    chn.freq = self.cpu_state.get_le_word(sid_addr + 7 * chn_num)

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
                    vcr = self.cpu_state.get_mem(sid_addr + 0x04 + 7 * chn_num)
                    chn.gate_on     = vcr & 0b00000001 != 0  # noqa
                    chn.sync_on     = vcr & 0b00000010 != 0  # noqa
                    chn.ring_on     = vcr & 0b00000100 != 0  # noqa
                    chn.oscil_on    = vcr & 0b00001000 == 0  # noqa
                    chn.waveforms = vcr >> 4
                    chn.set_waveform_fields()

                    if chn.gate_on:
                        chn.release_frame = None
                    elif prev_row.chips[chip_num].channels[chn_num].gate_on and not chn.gate_on:
                        chn.release_frame = self.frame_cnt

                    # ADSR as four nibbles
                    chn.adsr = ((self.cpu_state.get_mem(sid_addr + 0x05 + 7 * chn_num) << 8)
                                | self.cpu_state.get_mem(sid_addr + 0x06 + 7 * chn_num))
                    chn.set_adsr_fields()

                    # See comments on Filter Resonance Control Filter (above)
                    voices_filtered = filt_ctrl & 0b00000111
                    chn.filtered = (voices_filtered & (2 ** chn_num)) != 0

                    prev_chn = prev_row.chips[chip_num].channels[chn_num]

                    # is a released note still in the process of releasing?
                    within_release_window = (
                        chn.release_frame is not None
                        and (self.frame_cnt - chn.release_frame)
                        * ARCH[self.arch].ms_per_frame * 1000
                        < decay_release_time[chn.release])

                    # has sound been turned off for the channel?
                    channel_off = not chn.oscil_on
                    if (chn_num == 2) and row.chips[chip_num].no_sound_v3:
                        channel_off = True

                    # is a note playing?  (if so, it may or may not turn into a new note)
                    note_playing = (
                        chn.waveforms > 0 and not channel_off
                        and (chn.gate_on or within_release_window))

                    # was no note playing on the previous play routine invocation?
                    prev_note_off = not (prev_chn.gate_on and prev_chn.waveforms > 0)

                    chn.note = SidImport.get_note(
                        chn.freq, prev_chn.note, old_note_factor,
                        self.freq_lo, self.freq_hi)

                    # The following logic should allow for new notes to be asserted when
                    # - gate is on and one or more waveforms defined, but on the previous
                    #   frame, the gate was off or the waveform(s) undefined
                    # - or when waveform(s) on and frequency changed enough (more than mere
                    #   vibrato)
                    # - or (above) when gate is off but there's still enough time left on the
                    #   release that large changes in frequencies are worth turning into notes
                    make_new_note = (
                        note_playing and (prev_note_off or chn.note != prev_chn.note))

                    if (self.frame_cnt == first_frame or make_new_note):
                        chn.new_note = True

                    # if not a new note, but there's a small change in frequency...
                    if prev_chn.freq is not None:
                        delta = chn.freq - prev_chn.freq
                    else:
                        delta = 0
                    if not chn.new_note:
                        chn.df = delta
                    else:
                        chn.df = 0

            # Build delta_row (shows differences from previous row)

            # for each SID chip:
            for chip_num, chip in enumerate(row.chips):
                prev_chip = prev_row.chips[chip_num]
                delta_chip = delta_row.chips[chip_num]

                if chip.cutoff != prev_chip.cutoff:
                    delta_chip.cutoff = chip.cutoff

                if chip.filters != prev_chip.filters:
                    delta_chip.filters = chip.filters

                if chip.vol != prev_chip.vol:
                    delta_chip.vol = chip.vol

                if chip.resonance != prev_chip.resonance:
                    delta_chip.resonance = chip.resonance

                if chip.no_sound_v3 != prev_chip.no_sound_v3:
                    delta_chip.no_sound_v3 = chip.no_sound_v3

                # for each SID chip channel:
                for chn_num, chn in enumerate(row.chips[chip_num].channels):
                    prev_chn = prev_chip.channels[chn_num]
                    delta_chn = delta_chip.channels[chn_num]

                    if chn.new_note or chn.freq != prev_chn.freq:
                        delta_chn.freq = chn.freq

                    if chn.new_note:
                        delta_chn.note = chn.note

                    if chn.waveforms != prev_chn.waveforms:
                        delta_chn.waveforms = chn.waveforms
                        delta_chn.set_waveform_fields()

                    if chn.gate_on != prev_chn.gate_on:
                        delta_chn.gate_on = chn.gate_on

                    if chn.sync_on != prev_chn.sync_on:
                        delta_chn.sync_on = chn.sync_on

                    if chn.ring_on != prev_chn.ring_on:
                        delta_chn.ring_on = chn.ring_on

                    if chn.oscil_on != prev_chn.oscil_on:
                        delta_chn.oscil_on = chn.oscil_on

                    if chn.adsr != prev_chn.adsr:
                        delta_chn.adsr = chn.adsr
                        delta_chn.set_adsr_fields()

                    if chn.pulse_width != prev_chn.pulse_width:
                        delta_chn.pulse_width = chn.pulse_width

                    if chn.filtered != prev_chn.filtered:
                        delta_chn.filtered = chn.filtered

                    # no need to include release_frame or new_note

                    # end of per-channel loop

            if self.frame_cnt >= first_frame:
                sid_dump.rows.append(delta_row)

                # frames_with_activity

            # setup chips and channels for next iteration:

            self.frame_cnt += 1

            prev_row = copy.deepcopy(row)

            row = Row(sid_dump.sid_file.sid_count)
            row.frame_num = self.frame_cnt
            for chip_num, chip in enumerate(row.chips):
                for chn_num, chn in enumerate(chip.channels):
                    chn.release_frame = prev_row.chips[chip_num].channels[chn_num].release_frame

            delta_row = Row(sid_dump.sid_file.sid_count)
            delta_row.null_all()
            delta_row.frame_num = self.frame_cnt

        return sid_dump


if __name__ == "__main__":
    print("Nothing to do")
