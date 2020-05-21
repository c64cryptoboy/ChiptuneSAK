# This program runs Wolfgang Lorenz' C64 test suite (2002, public domain)
# This standard set of tests for C64 emulators can take a LONG time to run
# For now, I'm mostly ignoring C64-specific tests, and focusing on 6502
# instruction tests
#
# to run: python -m unittest -v tests
# On my machine, it ran 181 tests in 64 minutes

import wolfgangTestPath
import unittest
import cts6502Emulator
import string
from parameterized import parameterized, parameterized_class
from ctsBytesUtil import read_binary_file
from ctsConstants import project_to_absolute_path

cpuState = None

# psuedo-op docs taken from http://www.ffd2.com/fridge/docs/6502-NMOS.extra.opcodes
binary_file_tests = [
    # ADC tests
    ("adca",  "adc absolute"),
    ("adcax", "adc absolute,x"),
    ("adcay", "adc absolute,y"),
    ("adcb", "adc immediate"),
    ("adcix", "adc (indirect,x)"),
    ("adciy", "adc (indirect),y"),
    ("adcz", "adc zeropage"),
    ("adczx", "adc zeropage,x"),

    # illegal op  not yet supported in our emulator
    #
    # ALR    ***
    # This opcode ANDs the contents of the A register with an immediate value and 
    # then LSRs the result.
    # One supported mode:
    # ALR #ab         ;4B ab       ;No. Cycles= 2
    # Example:
    # ALR #$FE        ;4B FE
    # Equivalent instructions:
    # AND #$FE
    # LSR A
    #
    #("alrb", "alr immediate"),

    # illegal op  not yet supported in our emulator
    #
    # ANC    ***
    # ANC ANDs the contents of the A register with an immediate value and then 
    # moves bit 7 of A into the Carry flag.  This opcode works basically 
    # identically to AND #immed. except that the Carry flag is set to the same 
    # state that the Negative flag is set to.
    # One supported mode:
    # ANC #ab         ;2B ab       ;No. Cycles= 2
    # ANC #ab         ;0B ab
    #
    #("ancb", "anc immediate"),

    # AND tests
    ("anda", "and absolute"),
    ("andax", "and absolute,x"),
    ("anday", "and absolute,y"),
    ("andb", "and immediate"),
    ("andix", "and (indirect,x)"),
    ("andiy", "and (indirect),y"),
    ("andz", "and zeropage"),
    ("andzx", "and zeropage,x"),

    # illegal op  not yet supported in our emulator
    # Note: the aneb test fails repeatedly in VICE, which I trust more
    #
    # XAA    ***
    # XAA transfers the contents of the X register to the A register and then 
    # ANDs the A register with an immediate value.
    # One supported mode:
    # XAA #ab         ;8B ab       ;No. Cycles= 2
    #
    #("aneb", "xaa (aka ane) immediate"),

    # illegal op  not yet supported in our emulator
    # 
    # ARR    ***
    # This opcode ANDs the contents of the A register with an immediate value and 
    # then RORs the result.
    # One supported mode:
    # ARR #ab         ;6B ab       ;No. Cycles= 2
    # Here's an example of how you might write it in a program.
    # ARR #$7F        ;6B 7F
    # Here's the same code using equivalent instructions.
    # AND #$7F
    # ROR A
    #     
    # ("arrb", "arr immediate"),

    # test shifting (ASL, LSR)
    ("asla", "asl absolute"),
    ("aslax", "asl absolute,x"),
    ("asln", "asl"),
    ("aslz", "asl zeropage"),
    ("aslzx", "asl zeropage,x"),
    ("lsra", "lsr absolute"),
    ("lsrax", "lsr absolute,x"),
    ("lsrn", "lsr"),
    ("lsrz", "lsr zeropage"),
    ("lsrzx", "lsr zeropage,x"),

    # illegal op  not yet supported in our emulator
    # 
    # ASO    ***    (aka SLO)
    # This opcode ASLs the contents of a memory location and then ORs the result 
    # with the accumulator.  
    # Supported modes:
    # ASO abcd        ;0F cd ab    ;No. Cycles= 6
    # ASO abcd,X      ;1F cd ab    ;            7
    # ASO abcd,Y      ;1B cd ab    ;            7
    # ASO ab          ;07 ab       ;            5
    # ASO ab,X        ;17 ab       ;            6
    # ASO (ab,X)      ;03 ab       ;            8
    # ASO (ab),Y      ;13 ab       ;            8
    # (Sub-instructions: ORA, ASL)
    # Here is an example of how you might use this opcode:
    # ASO $C010       ;0F 10 C0
    # Here is the same code using equivalent instructions.
    # ASL $C010
    # ORA $C010
    # 
    #("asoa", "aso absolute"),
    #("asoax", "aso absolute,x"),
    #("asoay", "aso absolute,y"),
    #("asoix", "aso (indirect,x)"),
    #("asoiy", "aso (indirect),y"),
    #("asoz", "aso zeropage"),
    #("asozx", "aso zeropage,x"),

    # illegal op  not yet supported in our emulator
    # 
    # AXS    ***    (aka SAX)
    # AXS ANDs the contents of the A and X registers (without changing the 
    # contents of either register) and stores the result in memory.
    # AXS does not affect any flags in the processor status register.
    # Supported modes:
    # AXS abcd        ;8F cd ab    ;No. Cycles= 4
    # AXS ab          ;87 ab       ;            3
    # AXS ab,Y        ;97 ab       ;            4
    # AXS (ab,X)      ;83 ab       ;            6
    # (Sub-instructions: STA, STX)
    # Example:
    # AXS $FE         ;87 FE
    # Here's the same code using equivalent instructions.
    # STX $FE
    # PHA
    # AND $FE
    # STA $FE
    # PLA
    #
    #("axsa", "axs absolute"),
    #("axsix", "axs (indirect,x)"),
    #("axsz", "axs zeropage"),
    #("axszy", "axs zeropage,y"),

    # branch tests
    ("bccr", "bcc relative"),
    ("bcsr", "bcs relative"),
    ("beqr", "beq relative"),
    ("bmir", "bmi relative"),
    ("bner", "bne relative"),
    ("bplr", "bpl relative"),
    ("bvcr", "bvc relative"),
    ("bvsr", "bvs relative"),    
    ("branchwrap", "branchwrap"),

    # BRK tests
    # Test fills memory from $1100 to $1200 with BRKs, and JMPs to each in turn
    ("brkn", "brk"),

    # Going to skip these CIA tests for now, perhaps revisit them later
    #("cia1pb6", "cia1pb6"),
    #("cia1pb7", "cia1pb7"),
    #("cia1ta", "cia1ta"),
    #("cia1tab", "cia1tab"),
    #("cia1tb", "cia1tb"),
    #("cia1tb123", "cia1tb123"),
    #("cia2pb6", "cia2pb6"),
    #("cia2pb7", "cia2pb7"),
    #("cia2ta", "cia2ta"),
    #("cia2tb", "cia2tb"),
    #("cia2tb123", "cia2tb123"),
    #("cntdef", "cntdef"),
    #("cnto2", "cnto2"),
    #("flipos", "flipos"),
    #("icr01", "icr01"),
    #("imr", "imr"),
    #("irq", "irq"),
    #("loadth", "loadth"),
    #("nmi", "nmi"),
    #("oneshot", "oneshot"),

    # clear flag instruction tests
    ("clcn", "clc"),
    ("cldn", "cld"),
    ("clin", "cli"),
    ("clvn", "clv"),

    # compare tests (BIT, CMP, CPX, CPY)
    ("bita", "bit absolute"),
    ("bitz", "bit zeropage"),    
    ("cmpa", "cmp absolute"),
    ("cmpax", "cmp absolute,x"),
    ("cmpay", "cmp absolute,y"),
    ("cmpb", "cmp immediate"),
    ("cmpix", "cmp (indirect,x)"),
    ("cmpiy", "cmp (indirect),y"),
    ("cmpz", "cmp zeropage"),
    ("cmpzx", "cmp zeropage,x"),
    ("cpxa", "cpx absolute"),
    ("cpxb", "cpx immediate"),
    ("cpxz", "cpx zeropage"),
    ("cpya", "cpy absolute"),
    ("cpyb", "cpy immediate"),
    ("cpyz", "cpy zeropage"),

    # Test 6510 ports at mem loc 0 and 1
    # Skipping this for now
    #
    #("cpuport", "cpuport test, bits 0-7"),
    #("mmu", "mmu test, bits 0-2"), 
    #("mmufetch", "mmufetch"),    

    # Test various cycles consumed.  If there's a problem, you'll see this:
    # xx command byte
    # clocks  #measured
    # right   #2
    # #1  #2  command or addressing mode
    # --------------------------------------
    # 2   2   n
    # 2   2   b
    # 3   3   Rz/Wz
    # 5   5   Mz
    # 4   8   Rzx/Rzy/Wzx/Wzy
    # 6   10  Mzx/Mzy
    # 4   4   Ra/Wa
    # 6   6   Ma
    # 4   8   Rax/Ray (same page)
    # 5   9   Rax/Ray (different page)
    # 5   9   Wax/Way
    # 7   11  Max/May
    # 6   8   Rix/Wix
    # 8   10  Mix/Miy
    # 5   7   Riy (same page)
    # 6   8   Riy (different page)
    # 6   8   Wiy
    # 8   10  Miy
    # 2   18  r+00 same page not taken
    # 3   19  r+00 same page taken
    # 3   19  r+7F same page taken
    # 4   20  r+01 different page taken
    # 4   20  r+7F different page taken
    # 3   19  r-03 same page taken
    # 3   19  r-80 same page taken
    # 4   20  r-03 different page taken
    # 4   20  r-80 different page taken
    # 7   7   BRKn
    # 3   3   PHAn/PHPn
    # 4   4   PLAn/PLPn
    # 3   3   JMPw
    # 5   5   JMPi
    # 6   6   JSRw
    # 6   6   RTSn
    # 6   6   RTIn
    # #1 = command execution time without overhead
    # #2 = displayed value including overhead for measurement
    # R/W/M = Read/Write/Modify    
    ("cputiming", "cpu cycles-consumed tests"),

    # illegal op not yet supported in our emulator
    # 
    # DCM    ***    (aka DCP)
    # This opcode DECs the contents of a memory location and then CMPs the result 
    # with the A register.
    # Supported modes:
    # DCM abcd        ;CF cd ab    ;No. Cycles= 6
    # DCM abcd,X      ;DF cd ab    ;            7
    # DCM abcd,Y      ;DB cd ab    ;            7
    # DCM ab          ;C7 ab       ;            5
    # DCM ab,X        ;D7 ab       ;            6
    # DCM (ab,X)      ;C3 ab       ;            8
    # DCM (ab),Y      ;D3 ab       ;            8
    # (Sub-instructions: CMP, DEC)
    # Example:
    # DCM $FF         ;C7 FF
    # Equivalent instructions:
    # DEC $FF
    # CMP $FF
    # 
    #("dcma", "dcm absolute"),
    #("dcmax", "dcm absolute,x"),
    #("dcmay", "dcm absolute,y"),
    #("dcmix", "dcm (indirect,x)"),
    #("dcmiy", "dcm (indirect),y"),
    #("dcmz", "dcm zeropage"),
    #("dcmzx", "dcm zeropage,x"),

    # decrement tests (DEC, DEX, DEY)
    ("deca", "dec absolute"),
    ("decax", "dec absolute,x"),
    ("decz", "dec zeropage"),
    ("deczx", "dec zeropage,x"),
    ("dexn", "dex"),
    ("deyn", "dey"),

    # EOR tests
    ("eora", "eor absolute"),
    ("eorax", "eor absolute,x"),
    ("eoray", "eor absolute,y"),
    ("eorb", "eor immediate"),
    ("eorix", "eor (indirect,x)"),
    ("eoriy", "eor (indirect),y"),
    ("eorz", "eor zeropage"),
    ("eorzx", "eor zeropage,x"),

    # increment tests (INC, INX, INY)
    ("inca", "inc absolute"),
    ("incax", "inc absolute,x"),
    ("incz", "inc zeropage"),
    ("inczx", "inc zeropage,x"),
    ("inxn", "inx"),
    ("inyn", "iny"),

    # illegal op not yet supported in our emulator
    # 
    # INS    ***    (aka ISC)
    # This opcode INCs the contents of a memory location and then SBCs the result 
    # from the A register.
    # Supported modes:
    # INS abcd        ;EF cd ab    ;No. Cycles= 6
    # INS abcd,X      ;FF cd ab    ;            7
    # INS abcd,Y      ;FB cd ab    ;            7
    # INS ab          ;E7 ab       ;            5
    # INS ab,X        ;F7 ab       ;            6
    # INS (ab,X)      ;E3 ab       ;            8
    # INS (ab),Y      ;F3 ab       ;            8
    # (Sub-instructions: SBC, INC)
    # Example:
    # INS $FF         ;E7 FF
    # Equivalent instructions:
    # INC $FF
    # SBC $FF
    # 
    #("insa", "ins absolute"),
    #("insax", "ins absolute,x"),
    #("insay", "ins absolute,y"),
    #("insix", "ins (indirect,x)"),
    #("insiy", "ins (indirect),y"),
    #("insz", "ins zeropage"),
    #("inszx", "ins zeropage,x"),

    # jump tests (JMP, JSR)
    ("jmpi", "jmp indirect"),
    ("jmpw", "jmp absolute"),
    ("jsrw", "jsr absolute"),

    # illegal op, most of which has been implemented in our emulator
    # 
    # LAS    ***
    # This opcode ANDs the contents of a memory location with the contents of the 
    # stack pointer register and stores the result in the accumulator, the X 
    # register, and the stack pointer.  Affected flags: N Z.
    # One supported mode:
    # LAS abcd,Y      ;BB cd ab    ;No. Cycles= 4*
    #     
    #("lasay", "las absolute,y"),

    # illegal op not yet supported in our emulator
    # 
    # LAX    ***
    # This opcode loads both the accumulator and the X register with the contents 
    # of a memory location.
    # Supported modes:
    # LAX abcd        ;AF cd ab    ;No. Cycles= 4
    # LAX abcd,Y      ;BF cd ab    ;            4*
    # LAX ab          ;A7 ab       ;*=add 1     3
    # LAX ab,Y        ;B7 ab       ;if page     4
    # LAX (ab,X)      ;A3 ab       ;boundary    6
    # LAX (ab),Y      ;B3 ab       ;is crossed  5*
    # (Sub-instructions: LDA, LDX)
    # Example:
    # LAX $8400,Y     ;BF 00 84
    # Equivalent instructions:
    # LDA $8400,Y
    # LDX $8400,Y
    ("laxa", "lax absolute"),
    #("laxay", "lax absolute,y"), # not implemented yet
    ("laxix", "lax (indirect,x)"),
    ("laxiy", "lax (indirect),y"),
    ("laxz", "lax zeropage"),
    ("laxzy", "lax zeropage,y"),

    # load tests (LDA, LDX, LDY)
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

    # illegal op not yet supported in our emulator
    # 
    # LSE    ***   (aka SRE)
    # LSE LSRs the contents of a memory location and then EORs the result with 
    # the accumulator.
    # Supported modes:
    # LSE abcd        ;4F cd ab    ;No. Cycles= 6
    # LSE abcd,X      ;5F cd ab    ;            7
    # LSE abcd,Y      ;5B cd ab    ;            7
    # LSE ab          ;47 ab       ;            5
    # LSE ab,X        ;57 ab       ;            6
    # LSE (ab,X)      ;43 ab       ;            8
    # LSE (ab),Y      ;53 ab       ;            8
    # (Sub-instructions: EOR, LSR)
    # Example:
    # LSE $C100,X     ;5F 00 C1
    # Here's the same code using equivalent instructions.
    # LSR $C100,X
    # EOR $C100,X
    #
    #("lsea", "lse absolute"),
    #("lseax", "lse absolute,x"),
    #("lseay", "lse absolute,y"),
    #("lseix", "lse (indirect,x)"),
    #("lseiy", "lse (indirect),y"),
    #("lsez", "lse zeropage"),
    #("lsezx", "lse zeropage,x"),

    # OAL    *** (aka LXA)
    # This opcode ORs the A register with #$EE, ANDs the result with an immediate 
    # value, and then stores the result in both A and X.
    # One supported mode:
    # OAL #ab         ;AB ab       ;No. Cycles= 2
    # Here's an example of how you might use this opcode:
    # OAL #$AA        ;AB AA
    # Here's the same code using equivalent instructions:
    # ORA #$EE
    # AND #$AA
    # TAX
    #
    # The page goes on to say:
    # On my 128, xx may be EE,EF,FE, OR FF.  These possibilities appear to depend 
    # on three factors: the X register, PC, and the previous instruction 
    # executed.  Bit 0 is ORed from x, and also from PCH.  As for XAA, on my 128 
    # this opcode appears to work exactly as described in the list.
    # On my 64, OAL produces all sorts of values for xx: 00,04,06,80, etc... A 
    # rough scenario I worked out to explain this is here.  The constant value EE 
    # disappears entirely.  Instead of ORing with EE, the accumulator is ORed 
    # with certain bits of X and also ORed with certain bits of another 
    # "register" (nature unknown, whether it be the data bus, or something else).  
    # However, if OAL is preceded by certain other instructions like NOP, the 
    # constant value EE reappears and the foregoing does not take place.
    # 
    #("lxab", "lxa immediate"),

    # NOP tests
    ("nopn", "nop"),  # $ea

    # illegal op "NOP" tests
    ("nopa", "nop absolute"),  # $0c
    ("nopax", "nop absolute,x"),  # $1c
    ("nopb", "nop immediate"),  # $80
    ("nopz", "nop zeropage"),   # $04
    ("nopzx", "nop zeropage,x"),  # $14

    # ORA tests
    ("oraa", "ora absolute"),
    ("oraax", "ora absolute,x"),
    ("oraay", "ora absolute,y"),
    ("orab", "ora immediate"),
    ("oraix", "ora (indirect,x)"),
    ("oraiy", "ora (indirect),y"),
    ("oraz", "ora zeropage"),
    ("orazx", "ora zeropage,x"),

    # stack push/pull tests (PHA, PHP, PLA, PLP)
    ("phan", "pha"),
    ("phpn", "php"),
    ("plan", "pla"),
    ("plpn", "plp"),

    # illegal op not yet supported in our emulator
    # 
    # RLA    ***
    # RLA ROLs the contents of a memory location and then ANDs the result with 
    # the accumulator.
    # Supported modes:
    # RLA abcd        ;2F cd ab    ;No. Cycles= 6
    # RLA abcd,X      ;3F cd ab    ;            7
    # RLA abcd,Y      ;3B cd ab    ;            7
    # RLA ab          ;27 ab       ;            5
    # RLA ab,X        ;37 ab       ;            6
    # RLA (ab,X)      ;23 ab       ;            8
    # RLA (ab),Y      ;33 ab       ;            8
    # (Sub-instructions: AND, ROL)
    # Here's an example of how you might write it in a program.
    # RLA $FC,X       ;37 FC
    # Here's the same code using equivalent instructions.
    # ROL $FC,X
    # AND $FC,X
    # 
    #("rlaa", "rla absolute"),
    #("rlaax", "rla absolute,x"),
    #("rlaay", "rla absolute,y"),
    #("rlaix", "rla (indirect,x)"),
    #("rlaiy", "rla (indirect),y"),
    #("rlaz", "rla zeropage"),
    #("rlazx", "rla zeropage,x"),

    # rotate tests (ROL, ROR)
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

    # illegal op not yet supported in our emulator
    # 
    # RRA    ***
    # RRA RORs the contents of a memory location and then ADCs the result with 
    # the accumulator.
    # Supported modes:
    # RRA abcd        ;6F cd ab    ;No. Cycles= 6
    # RRA abcd,X      ;7F cd ab    ;            7
    # RRA abcd,Y      ;7B cd ab    ;            7
    # RRA ab          ;67 ab       ;            5
    # RRA ab,X        ;77 ab       ;            6
    # RRA (ab,X)      ;63 ab       ;            8
    # RRA (ab),Y      ;73 ab       ;            8
    # (Sub-instructions: ADC, ROR)
    # Example:
    # RRA $030C       ;6F 0C 03
    # Equivalent instructions:
    # ROR $030C
    # ADC $030C
    #("rraa", "rra absolute"),
    #("rraax", "rra absolute,x"),
    #("rraay", "rra absolute,y"),
    #("rraix", "rra (indirect,x)"),
    #("rraiy", "rra (indirect),y"),
    #("rraz", "rra zeropage"),
    #("rrazx", "rra zeropage,x"),

    # return tests (RTI, RTS)
    ("rtin", "rti"),
    ("rtsn", "rts"),

    # SBC tests
    ("sbca", "sbc absolute"),
    ("sbcax", "sbc absolute,x"),
    ("sbcay", "sbc absolute,y"),
    ("sbcb", "sbc immediate"),
    ("sbcix", "sbc (indirect,x)"),
    ("sbciy", "sbc (indirect),y"),
    ("sbcz", "sbc zeropage"),
    ("sbczx", "sbc zeropage,x"),

    # illegal op SBC $EB (equivalent to $E9)
    ("sbcb(eb)", "sbcb(eb)"),

    # illegal op not yet supported in our emulator
    # 
    # Note:  illegal op names aren't standardized, not just different naming, but
    # sometimes exchanged uses of the same names.  e.g., I've seen some flip
    # their "SAX" and "AXS" labels
    # 
    # SAX    *** (aka SBX, aka AXS)
    # SAX ANDs the contents of the A and X registers (leaving the contents of A 
    # intact), subtracts an immediate value, and then stores the result in X.
    # ... A few points might be made about the action of subtracting an immediate 
    # value.  It actually works just like the CMP instruction, except that CMP 
    # does not store the result of the subtraction it performs in any register.  
    # This subtract operation is not affected by the state of the Carry flag, 
    # though it does affect the Carry flag.  It does not affect the Overflow 
    # flag.
    # One supported mode:
    # SAX #ab         ;CB ab       ;No. Cycles= 2
    # Example:
    # SAX #$5A        ;CB 5A
    # Equivalent instructions:
    # STA $02
    # TXA
    # AND $02
    # SEC
    # SBC #$5A
    # TAX
    # LDA $02
    # Note: Memory location $02 would not be altered by the SAX opcode.
    # 
    #("sbxb", "sbx immediate"),

    # set flag instruction tests
    ("secn", "sec"),
    ("sedn", "sed"),
    ("sein", "sei"),

    # illegal op not yet supported in our emulator
    # 
    # AXA    ***  (aka SHA)
    # This opcode stores the result of A AND X AND the high byte of the target 
    # address of the operand +1 in memory.
    # Supported modes:
    # AXA abcd,Y      ;9F cd ab    ;No. Cycles= 5
    # AXA (ab),Y      ;93 ab       ;            6
    # Example:
    # AXA $7133,Y     ;9F 33 71
    # Equivalent instructions:
    # STX $02
    # PHA
    # AND $02
    # AND #$72
    # STA $7133,Y
    # PLA
    # LDX $02
    # Note: Memory location $02 would not be altered by the AXA opcode.
    #     
    #("shaay", "sha absolute,y"),
    #("shaiy", "sha (indirect),y"),

    # illegal op not yet supported in our emulator
    # 
    # TAS    *** (aka SHS)
    # This opcode ANDs the contents of the A and X registers (without changing 
    # the contents of either register) and transfers the result to the stack 
    # pointer.  It then ANDs that result with the contents of the high byte of 
    # the target address of the operand +1 and stores that final result in 
    # memory.  
    # One supported mode:
    # TAS abcd,Y      ;9B cd ab    ;No. Cycles= 5
    # (Sub-instructions: STA, TXS)
    # Here is an example of how you might use this opcode:
    # TAS $7700,Y     ;9B 00 77
    # Here is the same code using equivalent instructions.
    # STX $02
    # PHA
    # AND $02
    # TAX
    # TXS
    # AND #$78
    # STA $7700,Y
    # PLA
    # LDX $02
    # Note: Memory location $02 would not be altered by the TAS opcode.
    #
    #("shsay", "shs absolute,y"),

    # illegal op not yet supported in our emulator
    # 
    # XAS    *** (aka SHX)
    # This opcode ANDs the contents of the X register with <ab+1> and stores the 
    # result in memory.
    # One supported mode:
    # XAS abcd,Y      ;9E cd ab    ;No. Cycles= 5
    # Example:
    # XAS $6430,Y     ;9E 30 64
    # Equivalent instructions:
    # PHA
    # TXA
    # AND #$65
    # STA $6430,Y
    # PLA
    #
    # ("shxay", "shx absolute,y"),

    # illegal op not yet supported in our emulator
    # 
    # SAY    *** (aka SHY)
    # This opcode ANDs the contents of the Y register with <ab+1> and stores the 
    # result in memory.
    # One supported mode:
    # SAY abcd,X      ;9C cd ab    ;No. Cycles= 5
    # Example:
    # SAY $7700,X     ;9C 00 77
    # Equivalent instructions:
    # PHA
    # TYA
    # AND #$78
    # STA $7700,X
    # PLA
    #
    #("shyax", "shy absolute,x"),

    # store tests (STA, STX, STY)
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

    # register transfer tests (TXS, TXA, TXS, TYA, TAX, TAY)
    ("tsxn", "tsx"),
    ("txan", "txa"),
    ("txsn", "txs"),
    ("tyan", "tya"),
    ("taxn", "tax"),
    ("tayn", "tay"),

    # 6510 IO trap, page boundary, and wrap around tests
    # TODO: They don't say they're failing, but I don't think they're working either...
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
    ]

start_tests_at = 0 # start at the beginning
# when debugging, start at the named test:
start_tests_at = [a_tuple[0] for a_tuple in binary_file_tests].index('adca')

tests_to_run = binary_file_tests[start_tests_at:]


# translate alphabet from mixed-case (mode) petscii to ascii
# TODO:  This method is only complete enough for these tests, it's not yet general
# TODO:  Someday, all petscii tools will live in one place and be general
# We'll need ascii<->petscii upper case and ascii<->petscii mixed case converters
def mixed_case_petscii_to_ascii(petscii_string):
    result = []
    for c in petscii_string:
        c = ord(c)
        # only doing letter conversions
        if 193 <= c <= 218:
            c -= 96 # convert lowercase letters
        elif 65 <= c <= 90:
            c += 32 # convert uppercase letters
        elif chr(c) == '\r':
            c = ord('\n')
        elif chr(c) not in string.printable:
            c = ord('?')
        result.append(chr(c))
    return ''.join(result)


class TestWolfgangLorenzPrograms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("Skipping the first %d tests" % (start_tests_at))

    @classmethod
    def tearDownClass(cls):
        pass

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
        # FF4D  BA        TSX         ; look at flags put on the stack
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


    @parameterized.expand(tests_to_run)
    def test_wl(self, file_name, test_name):
        global cpuState

        print('\nRunning test "%s"' %(test_name))

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

        # Stack
        #
        # In VICE, this is how the stack looks after the BASIC's SYS call:
        # SP = f6 (which means $01f6)
        # $01f7 to $01ff: 46 E1 E9 A7 A7 79 A6 9C E3
        # - e146 return from SYS
        # - e9a7 return from start new basic code
        # - a7 some parameter?
        # - a679 return from restore
        # - e39c return from basic cold start
        #
        # The article did this:
        # cpuState.memory[0x01FE] = 0xff
        # cpuState.memory[0x01FF] = 0x7f  # $8000 minus 1
        # cpuState.sp = 0xfd  # points to next free position
        #
        # I'm just going to try this:
        cpuState.sp = 0xf6

        # No need to set the two cartridge basic reset vectors
        # $8000-$8001, 32768-32769: Execution address of cold reset.
        # $8002-$8003, 32770-32771: Execution address of non-maskable interrupt service routine.

        cpuState.memory[42100] = 0xea # Tests will sometimes exit to BASIC through $A474, trap it later

        # simulate getting a spacebar keypress from the keyboard buffer whenever $FFE4 is called
        cpuState.inject_bytes(0xffe4, [0xa9, 0x20, 0x60])  # LDA #$20, RTS

        output_text = ""
        passed_test = True
        while cpuState.runcpu():

            #debugging:
            #if cpuState.cpucycles == 3900:
            #    print("breakpoint")

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
            # It prints the error, and waits for a key press (which we stub in)
            if cpuState.pc == 0xffe4: # $FFE4
                passed_test = False
                #print("\nContext, data, accu, xreg, yreg, flags, sp")
                print('PRG output: "%s"' % (mixed_case_petscii_to_ascii(output_text)))
                output_text = ""
                #break

            if cpuState.pc == 59953: # $EA31
                print("DEBUG: software IRQ exit routine entered")

            if cpuState.pc == 64738:
                exit("DEBUG: We hit a reset?")

        if output_text != "":
            print(mixed_case_petscii_to_ascii(output_text))
        self.assertTrue(passed_test)


if __name__ == '__main__':
    # ctsTestingTools.env_to_stdout()
    unittest.main(failfast=False)
