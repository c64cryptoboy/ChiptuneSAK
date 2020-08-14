# Adds C64-specific behaviors atop the emulator_6502.py code
# Hopefully, other thin layers like this will be created for extracting NES and Atari 8-bit music
#
# Notes:
# - All bank switching logic assumes the EXROM and GAME are both 1 (since not emulating
#   cartridges)
#
# TODO:
# - More generalization will be needed for 2SID and 3SID

from chiptunesak import constants
from chiptunesak.byte_util import read_binary_file
from chiptunesak.errors import ChiptuneSAKContentError, ChiptuneSAKValueError
from chiptunesak import emulator_6502

# KERNAL ROM $FDDD-FDF3 gives these CIA#1 timer A cycle counts:
CIA_TIMER_NTSC = 17045
CIA_TIMER_PAL = 16421


class ThinC64Emulator(emulator_6502.Cpu6502Emulator):
    def __init__(self, arch=constants.DEFAULT_ARCH):
        super().__init__()

        # True if C64 ROM loaded, if False, all zeros
        self.has_basic = False
        self.has_kernal = False
        self.has_char = False

        self.set_mem_callback = None  # optional callback for processing memory writes

        self.rom_kernal = [0] * 8192    # KERNAL ROM 57344-65535 ($E000-$FFFF)
        self.rom_basic = [0] * 8192     # BASIC ROM 40960-49151 ($A000-$BFFF)
        self.rom_char = [0] * 4096      # Character set ROM 53248-57343 ($D000-$DFFF)
        self.registers_io = [0] * 4096  # Pretending I/O ($D000-$DFFF) are all registers

        self.is_ntsc = arch.startswith("NTSC")  # False if PAL

        self.see_basic = None
        self.see_kernal = None
        self.see_char = None
        self.see_io = None
        # bank in BASIC, KERNAL, and I/O (not char)
        self.set_mem(0x0001, 0b00110111)  # Sets the above four booleans

        # SID file specs say setting $02A6 is required
        if self.is_ntsc:
            self.memory[0x02a6] = 0x00  # NTSC
            self.set_le_word(0xdc04, CIA_TIMER_NTSC)
        else:
            self.memory[0x02a6] = 0x01  # PAL
            self.set_le_word(0xdc04, CIA_TIMER_PAL)

        # set kernal ROM hardware vectors to their kernal entry points
        # - $FFFA non-maskable interrupt vector points to NMI routine at $FE43
        # - $FFFC system reset vector points to power-on routine $FCE2
        # - $FFFE maskable interrupt request and break vector points to main IRQ handler $FF48
        self.patch_kernal(65530, [0x43, 0xfe, 0xe2, 0xfc, 0x48, 0xff])

        # set RAM interrupt routine vectors
        # - $0314 (CINV) IRQ interrupt routine vector, defaults to $EA31
        # - $0316 (CBINV) BRK instruction interrupt vector, defaults to $FE66
        # - $0318 (NMINV) Non-maskable interrupt vector, default to $FE47
        self.inject_bytes(788, [0x31, 0xea, 0x66, 0xfe, 0x47, 0xfe])

        # cartridge vectors
        # - $A000, basic cold start vector, points to $E394
        # = $A002, basic warm start / NMI entry vector, points to $E37B
        self.patch_basic(0xa000, [0x94, 0xe3, 0x7b, 0xe3])

        # inject into $EA81 (instructions PLA, TAY, PLA, TAX, PLA, RTI)
        self.patch_kernal(59953, [0x68, 0xa8, 0x68, 0xa4, 0x68, 0x40])

        # inject into $FF48 (ROM IRQ/BRK Interrupt Entry routine)
        # FF48  48        PHA         ; put accumulator, x, and y on stack
        # FF49  8A        TXA
        # FF4A  48        PHA
        # FF4B  98        TYA
        # FF4C  48        PHA
        # FF4D  BA        TSX         ; look at flags put on the stack
        # FF4E  BD 04 01  LDA $0104,X
        # FF51  29 10     AND #$10
        # FF53  F0 03     BEQ $FF58
        # FF55  6C 16 03  JMP ($0316) ; if software irq (break flag set)
        # FF58  6C 14 03  JMP ($0314) ; if hardware irq
        self.patch_kernal(65352, [
            0x48, 0x8a, 0x48, 0x98, 0x48, 0xba, 0xbd, 0x04, 0x01, 0x29,
            0x10, 0xf0, 0x03, 0x6c, 0x16, 0x03, 0x6c, 0x14, 0x03
        ])

    def get_mem(self, loc):
        self.mem_usage[loc] |= emulator_6502.MEM_USAGE_READ

        if loc < 0xa000 or (0xc000 <= loc <= 0xcfff):
            return self.memory[loc]

        if loc >= 0xe000:
            if self.see_kernal:
                return self.rom_kernal[loc - 0xe000]
            else:
                return self.memory[loc]

        if 0xa000 <= loc <= 0xbfff:
            if self.see_basic:
                return self.rom_basic[loc - 0xa000]
            else:
                return self.memory[loc]

        # only $D000 to $DFFF left to process:
        if self.see_char:
            return self.rom_char[loc - 0xd000]

        # Normally, for a given memory location, you can write to RAM, or read from either RAM
        # or what's banked in instead.  But it's more complicated in the $D000 to $DFFF range:
        #
        # When RAM is banked in:
        # - $D000-$DFFF: reads and writes go to RAM
        #
        # When character ROM banked in:
        # - $D000-$DFFF: reads from Character ROM, writes go to RAM
        #
        # When I/O banked in:
        # - $D000-$D02E: reads/writes go to VIC-II chip registers
        # - $D02F-$D03F: In a real C64, always read as $FF, and cannot be altered
        # - $D040-$D3FF: In a real C64, every 64-byte block here is a "mirror" of VIC-II
        #                registers at $D000
        # - $D400-$D418: Write-only SID registers (read value is not SID register or the
        #                RAM underneath)
        # - $D419-$D41C: Read-only SID registers
        # - $D41D-$D41F: In a real C64, always read as $FF, and cannot be altered
        # - $D420-$D4FF: In a real C64, every 32-bytes block here is a "mirror" of the SID
        #                registers at $D400
        # - $D800-$DBFF: reads/writes go to Color RAM
        # - $DC00-$DC0F: reads/writes go to CIA #1
        # - $DC10-$DCFF: In a real C64, every 16-bytes block here is a "mirror" of the CIA
        #                registers at $DC00
        # - $DD00-$DD0F: reads/writes go to CIA #2
        # - $DD10-$DDFF: In a real C64, every 16-bytes block here is a "mirror" of the CIA
        #                registers at $DD00
        # - $DE00-$DFFF: When no cart present, read/write behavior here is undefined

        if self.see_io:  # If the I/O is banked in
            if 0xd02f <= loc <= 0xd03f or 0xd41d <= loc <= 0xd41f:
                return 0xff

            if 0xd040 <= loc <= 0xd3ff:  # VIC-II mirroring
                return self.registers_io[((loc - 0xd040) % 64) + 0x040]

            # TODO: This will need to be modified for 2SID and 3SID emulation
            if 0xd420 <= loc <= 0xd4ff:  # SID mirroring
                return self.registers_io[((loc - 0xd420) % 32) + 0x420]

            if 0xdc10 <= loc <= 0xdcff:  # CIA1 mirroring
                return self.registers_io[((loc - 0xdc10) % 16) + 0xc10]

            if 0xdd10 <= loc <= 0xddff:  # CIA2 mirroring
                return self.registers_io[((loc - 0xdd10) % 16) + 0xd10]

            # Note: no special treatment for $D400-$D418
            #    In this low-fidelity emulator, you can read anything that was stored in a
            #    write-only SID register, which is used when we sample regs after a play call
            return self.registers_io[loc - 0xd000]

        return self.memory[loc]

    def set_mem(self, loc, val):
        self.mem_usage[loc] |= emulator_6502.MEM_USAGE_WRITE

        if not (0 <= val <= 255):
            exit("Error: POKE(%d),%d out of range" % (loc, val))

        if self.set_mem_callback is not None:
            self.set_mem_callback(loc, val)  # ignore the pylint "not callable" error

        if (0xd000 < loc < 0xdfff) and self.see_io:
            if 0xd02f <= loc <= 0xd03f or 0xd41d <= loc <= 0xd41f:
                return  # unsettable

            if 0xd040 <= loc <= 0xd3ff:  # VIC-II mirror set
                self.registers_io[((loc - 0xd040) % 64) + 0x040] = val
                return

            if 0xd420 <= loc <= 0xd4ff:  # SID mirror set
                self.registers_io[((loc - 0xd420) % 32) + 0x420] = val
                return

            if 0xdc10 <= loc <= 0xdcff:  # CIA1 mirror set
                self.registers_io[((loc - 0xdc10) % 16) + 0xc10] = val
                return

            if 0xdd10 <= loc <= 0xddff:  # CIA2 mirror set
                self.registers_io[((loc - 0xdd10) % 16) + 0xd10] = val
                return

            self.registers_io[loc - 0xd000] = val
            return

        self.memory[loc] = val  # Set RAM

        if loc == 1:  # hook writes to loc $0001 to update memory banking
            # Assuming that loc $0000 is always xxxxx111
            self.see_basic = self.see_kernal = self.see_io = self.see_char = False

            # From https://www.c64-wiki.com/wiki/Bank_Switching  (Validated)
            # Assumming the EXROM and GAME are both 1 (since not emulating cartridges),
            # here's the banks for the other three PLA latch states:

            # m1:b2   m1:b1   m1:b0   $1000-  $8000-  $A000-  $C000-  $D000-  $E000-
            # CHAREN  HIRAM   LORAM   $7FFF   $9FFF   $BFFF   $CFFF   $DFFF   $FFFF
            # 1       1       1       RAM     RAM     BASIC   RAM     I/O     KERNAL
            # 1       1       0       RAM     RAM     RAM     RAM     I/O     KERNAL
            # 1       0       1       RAM     RAM     RAM     RAM     I/O     RAM
            # 1       0       0       RAM     RAM     RAM     RAM     RAM     RAM
            # 0       1       1       RAM     RAM     BASIC   RAM     CHAR    KERNAL
            # 0       1       0       RAM     RAM     RAM     RAM     CHAR    KERNAL
            # 0       0       1       RAM     RAM     RAM     RAM     CHAR    RAM
            # 0       0       0       RAM     RAM     RAM     RAM     RAM     RAM
            # (I/O = VIC-II, SID, Color, CIA-1, CIA-2)

            banks = self.memory[0x0001] & 0b00000111
            if banks & 0b00000011 == 0b00000011:
                self.see_basic = True
            if banks & 0b00000010:
                self.see_kernal = True
            if 5 <= banks <= 7:
                self.see_io = True
            if 1 <= banks <= 3:
                self.see_char = True

    def bank_in_IO(self):
        """
        Will bank in the IO (if not already banked in)
        """
        banks = self.memory[0x0001] & 0b00000111

        #       m1:b2   m1:b1   m1:b0   $1000-  $8000-  $A000-  $C000-  $D000-  $E000-
        #       CHAREN  HIRAM   LORAM   $7FFF   $9FFF   $BFFF   $CFFF   $DFFF   $FFFF
        #
        # From  1       0       0       RAM     RAM     RAM     RAM     RAM     RAM
        # To    1       0       1       RAM     RAM     RAM     RAM     I/O     RAM
        #
        # From  0       1       1       RAM     RAM     BASIC   RAM     CHAR    KERNAL
        # To    1       1       1       RAM     RAM     BASIC   RAM     I/O     KERNAL
        #
        # From  0       1       0       RAM     RAM     RAM     RAM     CHAR    KERNAL
        # To    1       1       0       RAM     RAM     RAM     RAM     I/O     KERNAL
        #
        # From  0       0       1       RAM     RAM     RAM     RAM     CHAR    RAM
        # To    1       0       1       RAM     RAM     RAM     RAM     I/O     RAM
        #
        # From  0       0       0       RAM     RAM     RAM     RAM     RAM     RAM
        # To    1       0       1       RAM     RAM     RAM     RAM     I/O     RAM

        if banks == 0b100 or banks == 0b001 or banks == 0b000:
            self.set_mem(0x0001, 0b101)
        elif banks == 0b011:
            self.set_mem(0x0001, 0b111)
        elif banks == 0b010:
            self.set_mem(0x0001, 0b110)
        else:
            pass  # I/O already banked in, nothing to change

    def load_rom(self, path_and_filename, expected_size):
        binary = read_binary_file(path_and_filename)
        if binary is None:
            print(f"Warning: could not find {path_and_filename}... have you run `python3 res/downdownloadTestResources.py` yet?")
        elif len(binary) != expected_size:
            raise ChiptuneSAKContentError("Error: %s had unexpected length" % path_and_filename)

        return binary

    def load_roms(self):
        binary = self.load_rom(constants.project_to_absolute_path('res/c64kernal.bin'), 8192)
        if binary is not None:
            self.rom_kernal = binary
            self.has_kernal = True

        binary = self.load_rom(constants.project_to_absolute_path('res/c64basic.bin'), 8192)
        if binary is not None:
            self.rom_basic = binary
            self.has_basic = True

        binary = self.load_rom(constants.project_to_absolute_path('res/c64char.bin'), 4096)
        if binary is not None:
            self.rom_char = binary
            self.has_char = True

    def patch_kernal(self, mem_loc, bytes):
        mem_loc -= 0xe000
        for i, a_byte in enumerate(bytes):
            self.rom_kernal[mem_loc + i] = a_byte

    def patch_basic(self, mem_loc, bytes):
        mem_loc -= 0xa000
        for i, a_byte in enumerate(bytes):
            self.rom_basic[mem_loc + i] = a_byte

    def get_timer_base_loc(self, cia_num, timer):
        """
        Get the base address for the given cia and cia timer

        :param cia_num: cia chip number
        :type cia_num: int
        :param timer: cia timer designation
        :type timer: str
        :return: base address of cia timer
        :rtype: int
        """
        if cia_num not in [1, 2]:
            raise ChiptuneSAKValueError("Error: Invalid cia number %s" % cia_num)
        timer = timer.lower()
        if timer not in ['a', 'b']:
            raise ChiptuneSAKValueError("Error: Invalid cia timer %s" % timer)
        if cia_num == 1:
            if timer == 'a':
                return 0xdc04  # $dc04/$dc05 cia 1 timer a lo/hi (IRQ)
            else:
                return 0xdc06  # $dc06/$dc07 cia 1 timer b lo/hi (IRQ)
        else:
            if timer == 'a':
                return 0xdd04  # $dd04/$dd05 cia 2 timer a lo/hi (NMI)
            else:
                return 0xdd06  # $dd06/$dd07 cia 2 timer b lo/hi (NMI)

    def get_cia_timer(self, cia_num, timer):
        """
        Get the requested 16 bit timer value

        :param cia_num: cia chip number
        :type cia_num: int
        :param timer: cia timer designation
        :type timer: str
        :return: 16-bit timer value
        :rtype: int
        """
        # get le word from 0xdc04 I/O reg without mem_usage noticing
        base_addr = self.get_timer_base_loc(cia_num, timer)
        return (self.registers_io[base_addr - 0xd000]
                | (self.registers_io[base_addr + 1 - 0xd000] << 8))

    def timer_was_updated(self, cia_num, timer):
        """
        Returns True if the timer setting was written to

        :param cia_num: cia chip number
        :type cia_num: int
        :param timer: cia timer designation
        :type timer: str
        :return: True if the timer setting was written to
        :rtype: bool
        """
        base_addr = self.get_timer_base_loc(cia_num, timer)
        return self.word_was_updated(base_addr)

    def word_was_updated(self, base_addr):
        """
        Returns true if the 16-bit value at base_addr was written to

        :param base_addr: lo byte of the 16-bit lo/hi value
        :type base_addr: int
        :return: True if value was written to
        :rtype: bool
        """
        return ((self.mem_usage[base_addr] & emulator_6502.MEM_USAGE_WRITE != 0)
                or (self.mem_usage[base_addr + 1] & emulator_6502.MEM_USAGE_WRITE != 0))


if __name__ == "__main__":
    test = ThinC64Emulator()
    print("nothing to do")
