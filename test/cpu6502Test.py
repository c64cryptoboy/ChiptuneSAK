# Tests of 6502 Emulation
#


import testingPath
import unittest
import cts6502Emulator
from ctsConstants import ARCH

VERBOSE = False

cpuState = None

class Test6502Emulator(unittest.TestCase):
    def setUp(self):
        global cpuState
        cpuState = cts6502Emulator.Cpu6502Emulator()

    #@unittest.skip("Debugging, so skipping this test for now")
    def test_stack_wrapping(self):
        global cpuState
        
        cpuState.inject_bytes(32768, [0x60]) # RTS 
        cpuState.stack_wrapping = False

        cpuState.init_cpu(32768)
        self.assertTrue(cpuState.sp == 0xff)
        # With wrapping suppressed, RTS on an empty stack terminates the execution
        # (without stack pops)        
        self.assertTrue(cpuState.runcpu() == 0) 

        cpuState.init_cpu(32768)
        cpuState.sp = 0xfe
        self.assertTrue(cpuState.runcpu() == 0)

        cpuState.init_cpu(32768)
        cpuState.sp = 0xfd
        self.assertTrue(cpuState.runcpu() == 1)
        self.assertTrue(cpuState.sp == 0xff)

        cpuState.inject_bytes(32768, [0x40]) # RTI 

        cpuState.init_cpu(32768)
        cpuState.sp = 0xfd
        self.assertTrue(cpuState.runcpu() == 0)

        cpuState.init_cpu(32768)
        cpuState.sp = 0xfc
        self.assertTrue(cpuState.runcpu() == 1)

        cpuState.inject_bytes(32768, [0x60]) # RTS 
        cpuState.stack_wrapping = True

        cpuState.init_cpu(32768)
        cpuState.sp = 0xfd
        self.assertTrue(cpuState.runcpu() == 1)
        self.assertTrue(cpuState.sp == 0xff)

        cpuState.init_cpu(32768)
        cpuState.sp = 0xfe
        self.assertTrue(cpuState.runcpu() == 1)
        self.assertTrue(cpuState.sp == 0x00)

        cpuState.inject_bytes(32768, [0x40]) # RTI 

        cpuState.init_cpu(32768)
        cpuState.sp = 0xfc
        self.assertTrue(cpuState.runcpu() == 1)
        self.assertTrue(cpuState.sp == 0xff)

        cpuState.init_cpu(32768)
        cpuState.sp = 0xfe
        self.assertTrue(cpuState.runcpu() == 1)
        self.assertTrue(cpuState.sp == 0x01)


    #@unittest.skip("Debugging, so skipping this test for now")
    def test_obfuscated_sig(self):
        # Emulate the ML portion of my lemon64 signature
        # Note: signature line is obfuscated by changing XOR mask
        
        """
        10 A=32768:FORB=ATOA+27:READC:POKEB,C:NEXT:SYSA
        20 DATA160,15,152,89,12,128,32,210,255,136,208,246,96
        30 DATA12,71,81,65,77,38,84,73,94,42,74,74,66,87,2

        .C:8000  A0 0F       LDY #$0F
        .C:8002  98          TYA
        .C:8003  59 0C 80    EOR $800C,Y
        .C:8006  20 D2 FF    JSR $FFD2
        .C:8009  88          DEY
        .C:800a  D0 F6       BNE $8002
        .C:800c  60          RTS
        """
        test_prog = [160, 15, 152, 89, 12, 128, 32, 210, 255, 136, 208, 246, 96, 12, 71,
            81, 65, 77, 38, 84, 73, 94, 42, 74, 74, 66, 87, 2]

        cpuState.inject_bytes(32768, test_prog)

        # Memory Patch:  Since kernal ROM not loaded, make $FFD2 just an RTS
        cpuState.patch_kernal(0xffd2, [0x60])

        cpuState.init_cpu(32768)
        
        output_text = ""
        while cpuState.runcpu():
            # Capture petscii characters sent to screen print routine
            if cpuState.pc == 0xffd2:
                output_text += chr(cpuState.a)

        self.assertTrue(output_text == '\rYOFA WAS HERE\r')

    """
        Stuff the Commodore 64 Kernal/BASIC boot do not test:

        def zeropage_y(self): 
            return (self.lo() + self.y) & 0xff 

        def indirect_x(self): 
            return self.memory[(self.lo() + self.x) & 0xff] | (self.memory[(self.lo() + self.x + 1) & 0xff] << 8) 

        BCD in ADC and SBC
        Setting the V flag in SBC (when not BCD)
        Settig the C flag in ASL

        And these instructions:
        $75/117 ADC zp,X        $6D/109 ADC abs     $7D/125 ADC abs,X       $61/97 ADC (zp,X) 
        $71/113 ADC (zp),Y      $25/37 AND zp       $35/53 AND zp,X         $2D/45 AND abs 
        $3D/61 AND abs,X        $39/57 AND abs,Y    $21/33 AND (zp,X)       $31/49 AND (zp),Y 
        $0A/10 ASL A            $0E/14 ASL abs      $1E/30 ASL abs,X        $2C/44 BIT abs 
        $50/80 BVC rel          $70/112 BVS rel     $B8/184 CLV             $D5/213 CMP zp,X
        $CD/205 CMP abs         $D9/217 CMP abs,Y   $C1/193 CMP (zp,X)      $EC/236 CPX abs
        $CC/204 CPY abs         $D6/214 DEC zp,X    $CE/206 DEC abs $DE/222 DEC abs,X
        $55/85 EOR zp,X         $4D/77 EOR abs      $5D/93 EOR abs,X        $41/65 EOR (zp,X) 
        $51/81 EOR (zp),Y       $F6/246 INC zp,X    $EE/238 INC abs         $FE/254 INC abs,X 
        $A1/161 LDA (zp,X)      $B6/182 LDX zp,Y    $BE/190 LDX abs,Y       $BC/188 LDY abs,X 
        $4A/74 LSR A            $4E/78 LSR abs      $5E/94 LSR abs,X        $EA/234 NOP 
        $15/21 ORA zp,X         $1D/29 ORA abs,X    $19/25 ORA abs,Y        $01/1 ORA (zp,X) 
        $11/17 ORA (zp),Y       $26/38 ROL zp       $36/54 ROL zp,X         $2E/46 ROL abs 
        $3E/62 ROL abs,X        $6E/110 ROR abs     $7E/126 ROR abs,X       $40/64 RTI 
        $F5/245 SBC zp,X        $ED/237 SBC abs     $FD/253 SBC abs,X       $F9/249 SBC abs,Y 
        $E1/225 SBC (zp,X)      $F1/241 SBC (zp),Y  $F8/248 SED 	        $81/129 STA (zp,X) 
        $96/150 STX zp,Y        $BA/186 TSX         $00/0 BRK 
    """

    #@unittest.skip("Debugging, so skipping this test for now")
    def test_C64_kernal_boot(self):
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
        cpuState.load_roms()

        if not cpuState.has_kernal:
            raise unittest.case.SkipTest("KERNAL ROM not loaded, skipping C64 boot test")
        if not cpuState.has_basic:
            raise unittest.case.SkipTest("BASIC ROM not loaded, skipping C64 boot test")

        # On a RESET, the CPU loads the vector from $FFFC/$FFFD into the program counter
        # then continues from there.  This will be 64738, as in the good ol' SYS64738.
        # It tests for an autostart cartridge (which it won't find).  Then
        # IOINIT, RAMTAS, RESTOR, and CINT are called.  Then BASIC entered through
        # cold start vector at $A000, and we get the start-up message.  
        reset = cpuState.get_le_word(0xfffc)

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

        if VERBOSE:
            print(actual_screen_output)
        self.assertTrue(actual_screen_output == expected_screen_output)

if __name__ == '__main__':
    # ctsTestingTools.env_to_stdout()
    unittest.main(failfast=False)

