# Tests of 6502 Emulation

import testingPath
import unittest
import cts6502Emulator
from ctsConstants import ARCH

cpuState = None

class Test6502Emulator(unittest.TestCase):
    def setUp(self):
        global cpuState
        cpuState = cts6502Emulator.Cpu6502Emulator()

    def test_C64_kernel_boot(self):
        global cpuState

        expected_screen_output = \
            "                                        \n" + \
            "    **** COMMODORE 64 BASIC V2 ****     \n" + \
            "                                        \n" + \
            " 64K RAM SYSTEM  38911 BASIC BYTES FREE \n" + \
            "                                        \n" + \
            "READY.                                  "

        # Looks like it's necessary to have unmodifiable memory in the BASIC ROM area.
        # The startup ram check only stops when, working its way up from $0801, it hits the
        # BASIC ROM and finds that it can't change it.
        # This method loads the ROM ranges and makes them immutable
        cpuState.inject_roms()

        # On a RESET, the CPU loads the vector from $FFFC/$FFFD into the program counter
        # then continues from there.  This will be 64738, as in the good ol' SYS64738.
        # It tests for an autostart cartridge (which it won't find).  Then
        # IOINIT, RAMTAS, RESTOR, and CINT are called.  Then BASIC entered through
        # cold start vector at $A000, and we get the start-up message.    
        reset = cpuState.get_addr_at_loc(65532)

        # I've seen others set the break flag on RESET, but VICE doesn't do that, and
        # pagetable says not to: https://www.pagetable.com/?p=410
        # so default flags as 0 here:
        cpuState.init_cpu(reset)

        last_raster = -1
        while cpuState.runcpu():
            # fake the raster
            raster = (cpuState.cpucycles // ARCH['NTSC-C64'].cycles_per_line) \
                % ARCH['NTSC-C64'].lines_per_frame
            if raster != last_raster:
                cpuState.memory[53266] = raster & 0xff
                high = cpuState.memory[53265] & 0b01111111
                if raster > 255:
                    high |= 0b10000000
                cpuState.memory[53265] = high
                last_raster = raster
            # A non-changing raster will cause an infinite loop here:
            # 65371 $FF5B CINT: "Initialize Screen Editor and VIC-Chip"
            #    FF5E   AD 12 D0   LDA $D012
            #    FF61   D0 FB      BNE $FF5E
            # Can't just hold the I/O mapped mem loc 53266 as a constant value for reading,
            # because it also gets set (to set IRQ triggers)
            # Could possible make it like an immutable value, but simulating raster instead.

            # When we reach $E5D4, we're in the loop waiting for keyboard input,
            # which shows we've finished booting
            if cpuState.pc == 58836:
                break

        # check what's written on the screen 1024-2023 ($0400-$07E7)
        screen_memory_loc = 1024
        rows_to_read = 6
        col_width = 40
        screen_output = []
        for i in range(rows_to_read * col_width):
            if i > 0 and i % col_width == 0:
                screen_output.append("\n")
            screen_code = cpuState.memory[screen_memory_loc + i]
            if 1 <= screen_code <= 26:
                screen_code += 64
            screen_code = chr(screen_code)
            #if not screen_code.isprintable:
            #    screen_code = '~'
            screen_output.append(screen_code) 
            #print("%s" % (screen_code), end='')
        actual_screen_output = ''.join(screen_output)

        self.assertTrue(actual_screen_output == expected_screen_output)

if __name__ == '__main__':
    # ctsTestingTools.env_to_stdout()
    unittest.main(failfast=False)

