# Parse SID header information
#
# TODO:
# - search all the SIDs to see if they contain the KERNAL or BASIC ROMs


from ctsBytesUtil import big_endian_int, little_endian_int
from ctsConstants import project_to_absolute_path
from ctsErrors import ChiptuneSAKValueError

class SidFile:
    def __init__(self):
        self.magic_id = None            #: PSID or RSID
        self.version = None             #: 1 to 4
        self.data_offset = None         #: start of the C64 payload
        self.load_address = None        #: often the starting memory location
        self.init_address = None        #: often the init address
        self.play_address = None        #: often the play address
        self.num_subtunes = None        #: number of songs
        self.start_song = None          #: starting song
        self.speed = None               #: bitfield for each subtune indicating playback considerations
        self.name = None                #: SID name
        self.author = None              #: SID author
        self.released = None            #: SID release details
        self.c64_payload = None         #: The C64 payload
        self.load_addr_preamble = False #: True if payload begins with 16-bit load addr        
        self.flags = 0                  #: Collection of flags
        self.flag_0 = 0                 #: bit 0 from flags
        self.flag_1 = 0                 #: bit 1 from flags
        self.clock = 0                  #: video clock
        self.sid_model = 0              #: SID1 chip type
        self.sid2_model = 0             #: SID2 chip type
        self.sid3_model = 0             #: SID3 chip type
        self.start_page = 0             #: helps indicate where SID writes to memory
        self.page_length = 0            #: helps indicate where SID writes to memory
        self.sid2_address = 0           #: SID2 I/O starting address
        self.sid3_address = 0           #: SID3 I/O starting address
        self.sid_count = 1              #: Number of SIDs used (1 to 3)

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
        if self.magic_id == 'RSID' and self.load_address < 2024: # < $07E8
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
            elif (self.sid2_address % 2 == 1) or \
                not ((0x42 <= self.sid2_address <= 0x7f) or (0xe0 <= self.sid2_address <= 0xfe)):
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
            elif (self.sid3_address % 2 == 1) or \
                not ((0x42 <= self.sid3_address <= 0x7f) or (0xe0 <= self.sid3_address <= 0xfe)):
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


# Debugging stub
if __name__ == "__main__":
    sid = SidFile()
    sid.parse_file(project_to_absolute_path('test/sid/Master_of_the_Lamps_PAL.sid'))
    print("Load addr $%s" % (hex(sid.get_load_addr_from_payload()))[2:].upper())
