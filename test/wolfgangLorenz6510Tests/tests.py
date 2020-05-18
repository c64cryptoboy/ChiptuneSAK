# This program runs Wolfgang Lorenz' C64 test suite (2002, public domain)
# This standard set of tests for C64 emulators can take a LONG time to run
#
# to run: python -m unittest -v tests
#
# TODO:
# - write code to load each test binary and run it.
# - will need to stub out:
# -- $E16F (so python unit tests can do the loading instead)
# -- $FFE4 (so that no there's no user keyboard interaction)
# -- $FFD2 (so I can tell status without looking at screen memory)

import wolfgangTestPath
import unittest
import cts6502Emulator
from parameterized import parameterized, parameterized_class
from ctsBytesUtil import read_binary_file
from ctsConstants import project_to_absolute_path

cpuState = None

binary_file_tests = [
    ("adca",  "adc absolute"),
    ("adcax", "adc absolute,x"),
    ("adcay", "adc absolute,y"),
    ("adcb", "adc immediate"),
    ("adcix", "adc (indirect,x)"),
    ("adciy", "adc (indirect),y"),
    ("adcz", "adc zeropage"),
    ("adczx", "adc zeropage,x"),
    ("alrb", "alr immediate"),
    ("ancb", "anc immediate"),
    ("anda", "and absolute"),
    ("andax", "and absolute,x"),
    ("anday", "and absolute,y"),
    ("andb", "and immediate"),
    ("andix", "and (indirect,x)"),
    ("andiy", "and (indirect),y"),
    ("andz", "and zeropage"),
    ("andzx", "and zeropage,x"),
    ("aneb", "ane immediate"),
    ("arrb", "arr immediate"),
    ("asla", "asl absolute"),
    ("aslax", "asl absolute,x"),
    ("asln", "asl"),
    ("aslz", "asl zeropage"),
    ("aslzx", "asl zeropage,x"),
    ("asoa", "aso absolute"),
    ("asoax", "aso absolute,x"),
    ("asoay", "aso absolute,y"),
    ("asoix", "aso (indirect,x)"),
    ("asoiy", "aso (indirect),y"),
    ("asoz", "aso zeropage"),
    ("asozx", "aso zeropage,x"),
    ("axsa", "axs absolute"),
    ("axsix", "axs (indirect,x)"),
    ("axsz", "axs zeropage"),
    ("axszy", "axs zeropage,y"),
    ("bccr", "bcc relative"),
    ("bcsr", "bcs relative"),
    ("beqr", "beq relative"),
    ("bita", "bit absolute"),
    ("bitz",	"bit zeropage"),
    ("bmir", "bmi relative"),
    ("bner", "bne relative"),
    ("bplr", "bpl relative"),
    ("branchwrap", "branchwrap"),
    ("brkn", "brk"),
    ("bvcr", "bvc relative"),
    ("bvsr", "bvs relative"),
    ("cia1pb6", "cia1pb6"),
    ("cia1pb7", "cia1pb7"),
    ("cia1ta", "cia1ta"),
    ("cia1tab", "cia1tab"),
    ("cia1tb", "cia1tb"),
    ("cia1tb123", "cia1tb123"),
    ("cia2pb6", "cia2pb6"),
    ("cia2pb7", "cia2pb7"),
    ("cia2ta", "cia2ta"),
    ("cia2tb", "cia2tb"),
    ("cia2tb123", "cia2tb123"),
    ("clcn", "clc"),
    ("cldn", "cld"),
    ("clin", "cli"),
    ("clvn", "clv"),
    ("cmpa", "cmp absolute"),
    ("cmpax", "cmp absolute,x"),
    ("cmpay", "cmp absolute,y"),
    ("cmpb", "cmp immediate"),
    ("cmpix", "cmp (indirect,x)"),
    ("cmpiy", "cmp (indirect),y"),
    ("cmpz", "cmp zeropage"),
    ("cmpzx", "cmp zeropage,x"),
    ("cntdef", "cntdef"),
    ("cnto2", "cnto2"),
    ("cpuport", "cpuport"),
    ("cputiming", "cputiming"),
    ("cpxa", "cpx absolute"),
    ("cpxb", "cpx immediate"),
    ("cpxz", "cpx zeropage"),
    ("cpya", "cpy absolute"),
    ("cpyb", "cpy immediate"),
    ("cpyz", "cpy zeropage"),
    ("dcma", "dcm absolute"),
    ("dcmax", "dcm absolute,x"),
    ("dcmay", "dcm absolute,y"),
    ("dcmix", "dcm (indirect,x)"),
    ("dcmiy", "dcm (indirect),y"),
    ("dcmz", "dcm zeropage"),
    ("dcmzx", "dcm zeropage,x"),
    ("deca", "dec absolute"),
    ("decax", "dec absolute,x"),
    ("decz", "dec zeropage"),
    ("deczx", "dec zeropage,x"),
    ("dexn", "dex"),
    ("deyn", "dey"),
    ("eora", "eor absolute"),
    ("eorax", "eor absolute,x"),
    ("eoray", "eor absolute,y"),
    ("eorb", "eor immediate"),
    ("eorix", "eor (indirect,x)"),
    ("eoriy", "eor (indirect),y"),
    ("eorz", "eor zeropage"),
    ("eorzx", "eor zeropage,x"),
    ("flipos", "flipos"),
    ("icr01", "icr01"),
    ("imr", "imr"),
    ("inca", "inc absolute"),
    ("incax", "inc absolute,x"),
    ("incz", "inc zeropage"),
    ("inczx", "inc zeropage,x"),
    ("insa", "ins absolute"),
    ("insax", "ins absolute,x"),
    ("insay", "ins absolute,y"),
    ("insix", "ins (indirect,x)"),
    ("insiy", "ins (indirect),y"),
    ("insz", "ins zeropage"),
    ("inszx", "ins zeropage,x"),
    ("inxn", "inx"),
    ("inyn", "iny"),
    ("irq", "irq"),
    ("jmpi", "jmp indirect"),
    ("jmpw", "jmp absolute"),
    ("jsrw", "jsr absolute"),
    ("lasay", "las absolute,y"),
    ("laxa", "lax absolute"),
    ("laxay", "lax absolute,y"),
    ("laxix", "lax (indirect,x)"),
    ("laxiy", "lax (indirect),y"),
    ("laxz", "lax zeropage"),
    ("laxzy", "lax zeropage,y"),
    ("ldaa", "lda absolute"),
    ("ldaax", "lda absolute,x"),
    ("ldaay", "lda absolute,y"),
    ("ldab", "lda immediate"),
    ("ldaix", "lda (indirect,x)"),
    ("ldaiy", "lda (indirect),y"),
    ("ldaz", "lda zeropage"),
    ("ldazx", "lda zeropage,x"),
    ("ldxa", "ldx absolute"),
    ("ldxay", "ldx absolute,y"),
    ("ldxb", "ldx immediate"),
    ("ldxz", "ldx zeropage"),
    ("ldxzy", "ldx zeropage,y"),
    ("ldya", "ldy absolute"),
    ("ldyax", "ldy absolute,x"),
    ("ldyb", "ldy immediate"),
    ("ldyz", "ldy zeropage"),
    ("ldyzx", "ldy zeropage,x"),
    ("loadth", "loadth"),
    ("lsea", "lse absolute"),
    ("lseax", "lse absolute,x"),
    ("lseay", "lse absolute,y"),
    ("lseix", "lse (indirect,x)"),
    ("lseiy", "lse (indirect),y"),
    ("lsez", "lse zeropage"),
    ("lsezx", "lse zeropage,x"),
    ("lsra", "lsr absolute"),
    ("lsrax", "lsr absolute,x"),
    ("lsrn", "lsr"),
    ("lsrz", "lsr zeropage"),
    ("lsrzx", "lsr zeropage,x"),
    ("lxab", "lxa immediate"),
    ("mmu", "mmu"),
    ("mmufetch", "mmufetch"),
    ("nmi", "nmi"),
    ("nopa", "nop absolute"),
    ("nopax", "nop absolute,x"),
    ("nopb", "nop immediate"),
    ("nopn", "nop"),
    ("nopz", "nop zeropage"),
    ("nopzx", "nop zeropage,x"),
    ("oneshot", "oneshot"),
    ("oraa", "ora absolute"),
    ("oraax", "ora absolute,x"),
    ("oraay", "ora absolute,y"),
    ("orab", "ora immediate"),
    ("oraix", "ora (indirect,x)"),
    ("oraiy", "ora (indirect),y"),
    ("oraz", "ora zeropage"),
    ("orazx", "ora zeropage,x"),
    ("phan", "pha"),
    ("phpn", "php"),
    ("plan", "pla"),
    ("plpn", "plp"),
    ("rlaa", "rla absolute"),
    ("rlaax", "rla absolute,x"),
    ("rlaay", "rla absolute,y"),
    ("rlaix", "rla (indirect,x)"),
    ("rlaiy", "rla (indirect),y"),
    ("rlaz", "rla zeropage"),
    ("rlazx", "rla zeropage,x"),
    ("rola", "rol absolute"),
    ("rolax", "rol absolute,x"),
    ("roln", "rol"),
    ("rolz", "rol zeropage"),
    ("rolzx", "rol zeropage,x"),
    ("rora", "ror absolute"),
    ("rorax", "ror absolute,x"),
    ("rorn", "ror"),
    ("rorz", "ror zeropage"),
    ("rorzx", "ror zeropage,x"),
    ("rraa", "rra absolute"),
    ("rraax", "rra absolute,x"),
    ("rraay", "rra absolute,y"),
    ("rraix", "rra (indirect,x)"),
    ("rraiy", "rra (indirect),y"),
    ("rraz", "rra zeropage"),
    ("rrazx", "rra zeropage,x"),
    ("rtin", "rti"),
    ("rtsn", "rts"),
    ("sbca", "sbc absolute"),
    ("sbcax", "sbc absolute,x"),
    ("sbcay", "sbc absolute,y"),
    ("sbcb", "sbc immediate"),
    ("sbcb(eb)", "sbcb(eb)"),
    ("sbcix", "sbc (indirect,x)"),
    ("sbciy", "sbc (indirect),y"),
    ("sbcz", "sbc zeropage"),
    ("sbczx", "sbc zeropage,x"),
    ("sbxb", "sbx immediate"),
    ("secn", "sec"),
    ("sedn", "sed"),
    ("sein", "sei"),
    ("shaay", "sha absolute,y"),
    ("shaiy", "sha (indirect),y"),
    ("shsay", "shs absolute,y"),
    ("shxay", "shx absolute,y"),
    ("shyax", "shy absolute,x"),
    ("staa", "sta absolute"),
    ("staax", "sta absolute,x"),
    ("staay", "sta absolute,y"),
    ("staix", "sta (indirect,x)"),
    ("staiy", "sta (indirect),y"),
    ("staz", "sta zeropage"),
    ("stazx", "sta zeropage,x"),
    ("stxa", "stx absolute"),
    ("stxz", "stx zeropage"),
    ("stxzy", "stx zeropage,y"),
    ("stya", "sty absolute"),
    ("styz", "sty zeropage"),
    ("styzx", "sty zeropage,x"),
    ("taxn", "tax"),
    ("tayn", "tay"),
    ("trap1", "trap1"),
    ("trap2", "trap2"),
    ("trap3", "trap3"),
    ("trap4", "trap4"),
    ("trap5", "trap5"),
    ("trap6", "trap6"),
    ("trap7", "trap7"),
    ("trap8", "trap8"),
    ("trap9", "trap9"),
    ("trap10", "trap10"),
    ("trap11", "trap11"),
    ("trap12", "trap12"),
    ("trap13", "trap13"),
    ("trap14", "trap14"),
    ("trap15", "trap15"),
    ("trap16", "trap16"),
    ("trap17", "trap17"),
    ("tsxn", "tsx"),
    ("txan", "txa"),
    ("txsn", "txs"),
    ("tyan", "tya")]


class TestWolfgangLorenzPrograms(unittest.TestCase):
    def setUp(self):
        global cpuState

        cpuState = cts6502Emulator.Cpu6502Emulator()

        # set kernal ROM hardware vectors to their kernal entry points
        # - $FFFA non-maskable interrupt vector points to NMI routine at $FE43
        # - $FFFC system reset vector points to power-on routine $FCE2
        # - $FFFE maskable interrupt request and break vector points to main IRQ handler $FF48
        cpuState.inject_bytes(65530, [0x43, 0xfe, 0xe2, 0xfc, 0x48, 0xff])

        # set RAM interrupt routine vectors
        cpuState.inject_bytes(788, [0x31, 0xea, 0x66, 0xfe, 0x47, 0xfe])
        # - $0314 (CINV) IRQ interrupt routine vector, defaults to $EA31
        # - $0316 (CBINV) BRK instruction interrupt vector, defaults to $FE66
        # - $0318 (NMINV) Non-maskable interrupt vector, default to $FE47

        # set yet more vectors
        # - $A000, basic cold start vector, points to $E394
        # = $A002, basic warm start / NMI entry vector, points to $E37B
        cpuState.inject_bytes(40960, [0x94, 0xe3, 0x7b, 0xe3])       

        # patch $EA31 to jump to $EA81
        cpuState.inject_bytes(59953, [0x4c, 0x81, 0xea])

        # inject original kernal snippet into $EA81 (instructions PLA, TAY, PLA, TAX, PLA, RTI)
        cpuState.inject_bytes(59953, [0x68, 0xa8, 0x68, 0xa4, 0x68, 0x40]) 

        # inject original kernal snippet into $FF48 (ROM IRQ/BRK Interrupt Entry routine)
        # FF48  48        PHA         ; put accumulator, x, and y on stack
        # FF49  8A        TXA
        # FF4A  48        PHA
        # FF4B  98        TYA
        # FF4C  48        PHA
        # FF4D  BA        TSX         ; test flags
        # FF4E  BD 04 01  LDA $0104,X
        # FF51  29 10     AND #$10 
        # FF53  F0 03     BEQ $FF58
        # FF55  6C 16 03  JMP ($0316) ; if software irq (break flag set)
        # FF58  6C 14 03  JMP ($0314) ; if hardware irq        
        cpuState.inject_bytes(65352,
            [0x48, 0x8a, 0x48, 0x98, 0x48, 0xba, 0xbd, 0x04, 0x01, 0x29,
            0x10, 0xf0, 0x03, 0x6c, 0x16, 0x03, 0x6c, 0x14, 0x03])

        # Replace some missing routines with RTS instructions (so they're not BRKs)
        cpuState.memory[65490] = 0x60 # $FFD2 CHROUT
        cpuState.memory[65091] = 0x60 # $FE43 NMI Interrupt Entry Point
        cpuState.memory[64738] = 0x60 # $FCE2 power-on reset routine
        cpuState.memory[65095] = 0x60 # $FE47 NMI handler
        cpuState.memory[65126] = 0x60 # $FE66 init things then BASIC warm start using vec $A002
        cpuState.memory[58260] = 0x60 # $E394 basic cold entry
        cpuState.memory[58235] = 0x60 # $E37B basic warm entry / NMI entry


    @parameterized.expand(binary_file_tests)
    def test_wl(self, file_name, test_name):
        global cpuState

        print('DEBUG: Running test "%s"' %(test_name))

        test_prg = read_binary_file(project_to_absolute_path('test/wolfgangLorenz6510Tests/'+file_name))
        test_prg = test_prg[2:]  # strip off load addr (it's always 2049)

        cpuState.inject_bytes(2049, test_prg)
        # skip the BASIC stub that starts at $801 (POKE2,0:SYS2070)
        # state gets reset between tests automaticlaly via each separate cpu instance
        cpuState.init_cpu(2070) # $816

        # This http://www.softwolves.com/arkiv/cbm-hackers/7/7114.html says when loading
        # a test yourself (instead of using test code's loader), do these settings:
        #    P to $04 (Set interrupt flag?  I'm going to ignore that)
        #    $0002 = $00 (done by default)
        #    $A002 = $00; $A003 = $80
        #    $FFFE = $48; $FFFF = $FF (done in setUp())
        #    As for the stack, set S to $FD and set $01FE = $FF and $01FF = $7F
        cpuState.inject_bytes(0xa002, [0x00, 0x80])  # override from setUp() 
        # put an address on the stack
        cpuState.sp = 0xfd
        cpuState.memory[0x01FE] = 0xff
        cpuState.memory[0x01FF] = 0x7f

        # TODO: should be no need to set the two cartridge basic reset vectors?
        # $8000-$8001, 32768-32769: Execution address of cold reset.
        # $8002-$8003, 32770-32771: Execution address of non-maskable interrupt service routine.

        cpuState.memory[42100] = 0xea # Tests will sometimes exit to BASIC through $A474, trap it later

        # simulate getting a spacebar keypress from the keyboard buffer whenever $FFE4 is called
        cpuState.inject_bytes(0xffe4, [0xa9, 0x20, 0x60])  # LDA #$20, RTS

        output_text = ""
        passed_test = True
        while cpuState.runcpu():

            # current debug point
            #if cpuState.cpucycles == 2149:
            #    if (1==1):
            #        pass

            # Capture petscii characters sent to screen print routine
            if cpuState.pc == 65490: # $FFD2
                output_text += chr(cpuState.a)

            # Don't need test to load the next test, as this python is managing the test loading
            if cpuState.pc == 57711: # load is $E168, skips entry point and jumps to $E16F
                # debugging: pointer to next test name string (zero-terminated) is
                #    mem($BC) << 8 | mem($BB)
                break # we're done with this test

            if cpuState.pc == 42100: # if exit to BASIC
                break

            # if test program is asking for keyboard input from GETIN, that means we hit an error.
            # we could stop, or we could gather up all the output text from all the errors for this case
            if cpuState.pc == 65508: # $FFE4
                passed_test = False

            if cpuState.pc == 59953: # $EA31
                print("DEBUG: software IRQ exit routine entered")

            if cpuState.pc == 64738:
                exit("DEBUG: We hit a reset?")

        # TODO:  Should look at the PC whenever a BRK was encountered to see what else needs
        # to be hooked.

        print("\ntest: %s, pass: %s, accumulated output: %s" %
            (test_name, passed_test, output_text))
        self.assertTrue(passed_test)


if __name__ == '__main__':
    # ctsTestingTools.env_to_stdout()
    unittest.main(failfast=True)
