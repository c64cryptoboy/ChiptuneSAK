# Adds C64-specific behaviors to Cpu6502Emulator
#
# TODO:
# - get_mem and set_mem mirroring needs to be overriden (or just removed) when we start to support
#   2SID and 3SID

from ctsConstants import project_to_absolute_path
from ctsBytesUtil import read_binary_file
from ctsErrors import ChiptuneSAKContentError
import cts6502Emulator


class ThinC64Emulator(cts6502Emulator.Cpu6502Emulator):
    def __init__(self):
        super().__init__()

        # True if C64 ROM loaded, if False, all zeros
        self.has_basic = False
        self.has_kernal = False
        self.has_char = False

        # True if paged in
        self.see_basic = True
        self.see_kernal = True
        self.see_char = False        
        self.see_io = True

        self.rom_kernal = [0] * 8192   # KERNAL ROM 57344-65535 ($E000-$FFFF)
        self.rom_basic = [0] * 8192     # BASIC ROM 40960-49151 ($A000-$BFFF)
        self.rom_char = [0] * 4096      # Character set ROM 53248-57343 ($D000-$DFFF)
        self.registers_io = [0] * 4096  # Pretending I/O ($D000-$DFFF) are all registers

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
        # - $D040-$D3FF: In a real C64, every 64-byte block here is a "mirror" of VIC-II registers at $D000
        # - $D400-$D418: Write-only SID registers (read value is not SID register or the RAM underneath)
        # - $D419-$D41C: Read-only SID registers
        # - $D41D-$D41F: In a real C64, always read as $FF, and cannot be altered
        # - $D420-$D4FF: In a real C64, every 32-bytes block here is a "mirror" of the SID registers at $D400
        # - $D800-$DBFF: reads/writes go to Color RAM
        # - $DC00-$DC0F: reads/writes go to CIA #1
        # - $DC10-$DCFF: In a real C64, every 16-bytes block here is a "mirror" of the CIA registers at $DC00
        # - $DD00-$DD0F: reads/writes go to CIA #2
        # - $DD10-$DDFF: In a real C64, every 16-bytes block here is a "mirror" of the CIA registers at $DD00
        # - $DE00-$DEFF: TODO: When no cart present, read/write behavior here is confusing
        # - $DF00-$DFFF: TODO: When no cart present, read/write behavior here is confusing

        if self.see_io:  # If the I/O is banked in
            if 0xd02f <= loc <= 0xd03f or 0xd41d <= loc <= 0xd41f:
                return 0xff

            if 0xd040 <= loc <= 0xd3ff:  # VIC-II mirroring
                return self.registers_io[((loc - 0xd040) % 64) + 0x040]

            if 0xd420 <= loc <= 0xd4ff:  # SID mirroring
                return self.registers_io[((loc - 0xd420) % 32) + 0x420]

            if 0xdc10 <= loc <= 0xdcff:  # CIA1 mirroring
                return self.registers_io[((loc - 0xdc10) % 16) + 0xc10]

            if 0xdd10 <= loc <= 0xddff:  # CIA2 mirroring
                return self.registers_io[((loc - 0xdd10) % 16) + 0xd10]

            # Note: no special treatment for $D400-$D418
            #    In this low-fidelity emulator, you can read anything that was stored in a
            #    write-only SID register, which is useful for our capture of SID values
            return self.registers_io[loc - 0xd000]

        # nothing bad RAM here in the $Dxxx range...
        return self.memory[loc]

    def set_mem(self, loc, val):
        if not (0 <= val <= 255):
            exit("Error: POKE(%d),%d out of range" % (loc, val))

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

            # From https://www.c64-wiki.com/wiki/Bank_Switching
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

    def load_rom(self, path_and_filename, expected_size):
        binary = read_binary_file(path_and_filename)
        if binary is None:
            print("Warning: could not find %s" % (path_and_filename))
        elif len(binary) != expected_size:
            raise ChiptuneSAKContentError("Error: %s had unexpected length" % path_and_filename)

        return binary

    def load_roms(self):
        binary = self.load_rom(project_to_absolute_path('res/c64kernal.bin'), 8192)
        if binary is not None:
            self.rom_kernal = binary
            self.has_kernal = True

        binary = self.load_rom(project_to_absolute_path('res/c64basic.bin'), 8192)
        if binary is not None:
            self.rom_basic = binary
            self.has_basic = True

        binary = self.load_rom(project_to_absolute_path('res/c64char.bin'), 4096)
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


if __name__ == "__main__":
    test = ThinC64Emulator()
    print("nothing to do")
