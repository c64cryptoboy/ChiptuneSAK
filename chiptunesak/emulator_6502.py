# 6502 instruction-level emulation
#
# This module emulates 6502 machine language program execution at an instruction-level
# of granularity (not a cycle-level).
#
# runcpu() can be called in a while loop.  (Non-error) Exit conditions:
# - BRK
# - RTI or RTS if exit_on_empty_stack is True and stack is empty or has already wrapped
#
# Code references used during development:
# 1) C code: SIDDump: https://csdb.dk/release/?id=152422
#    This started as a direct python adaptation of SIDDump.  At this time, the original
#    C code is still included in this file as reference.  It made heavy use of macros
#    (something python doesn't have) for register/value/address polymorphism.
# 2) python code: py65: https://github.com/eteran/pretendo/blob/master/doc/cpu/6502.txt
#    If I had just imported this library, I would have been done.  But then I wouldn't have
#    learned nearly as much while getting bugs out of this emulator.
# 3) python code: The Pretendo NES emulator:
#    Nice docs: https://github.com/eteran/pretendo/blob/master/doc/cpu/6502.txt
# 4) python code: pyc64, a C64 simulator in python, using py65
#    https://github.com/irmen/pyc64

# TODOs:
# - throw an exception if the break flag ever appears on flags

from chiptunesak.errors import ChiptuneSAKNotImplemented, ChiptuneSAKValueError
from chiptunesak.byte_util import hexdump

# 6502 vector locations
NMI = 0xfffa  # on C64, vector points to NMI routine at $FE43/65091
RESET = 0xfffc  # on C64, vector points to power-on routine $FCE2/64738
IRQ = 0xfffe  # on C64, vector points to IRQ handler routine at $FF48/65352

FN = 0b10000000  # Negative
FV = 0b01000000  # oVerflow
FU = 0b00100000  # Unused
FB = 0b00010000  # Break
FD = 0b00001000  # Decimal
FI = 0b00000100  # Interrupt
FZ = 0b00000010  # Zero
FC = 0b00000001  # Carry

# base cycle values for instructions (and pseudo-ops) 0 through 255:
cpucycles_table = [
    7, 6, 0, 8, 3, 3, 5, 5, 3, 2, 2, 2, 4, 4, 6, 6,
    2, 5, 0, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7,
    6, 6, 0, 8, 3, 3, 5, 5, 4, 2, 2, 2, 4, 4, 6, 6,
    2, 5, 0, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7,
    6, 6, 0, 8, 3, 3, 5, 5, 3, 2, 2, 2, 3, 4, 6, 6,
    2, 5, 0, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7,
    6, 6, 0, 8, 3, 3, 5, 5, 4, 2, 2, 2, 5, 4, 6, 6,
    2, 5, 0, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7,
    2, 6, 2, 6, 3, 3, 3, 3, 2, 2, 2, 2, 4, 4, 4, 4,
    2, 6, 0, 6, 4, 4, 4, 4, 2, 5, 2, 5, 5, 5, 5, 5,
    2, 6, 2, 6, 3, 3, 3, 3, 2, 2, 2, 2, 4, 4, 4, 4,
    2, 5, 0, 5, 4, 4, 4, 4, 2, 4, 2, 4, 4, 4, 4, 4,
    2, 6, 2, 8, 3, 3, 5, 5, 2, 2, 2, 2, 4, 4, 6, 6,
    2, 5, 0, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7,
    2, 6, 2, 8, 3, 3, 5, 5, 2, 2, 2, 2, 4, 4, 6, 6,
    2, 5, 0, 8, 4, 4, 6, 6, 2, 4, 2, 7, 4, 4, 7, 7]

# A cutoff point for determining if an RTI or RTS should exit emulation when the
# stack has wrapped (i.e. 0 <= SP < STACK_WRAP_AREA).
STACK_WRAP_AREA = 0x0f

MEM_USAGE_READ  = 0b00000001  # noqa:E221
MEM_USAGE_WRITE = 0b00000010


class Cpu6502Emulator:
    def __init__(self):
        self.memory = 0x10000 * [0x00]     # 64K memory as integers
        self.mem_usage = 0x10000 * [0x00]  # monitor a program's memory r/w usage
        self.a = 0                         # accumulator (byte)
        self.x = 0                         # x register (byte)
        self.y = 0                         # y register (byte)
        self.flags = FU                    # processor flags (byte)
        self.sp = 0                        # stack pointer (byte)
        self.pc = 0                        # program counter (16-bit)
        self.cpucycles = 0                 # count of cpu cycles processed
        self.last_instruction = None       # last instruction processed
        self.exit_on_empty_stack = False   # True = RTI/RTS exists on empty stack
        self.debug = False
        self.invocationCount = -1

    def get_mem(self, loc):
        return self.memory[loc]

    def set_mem(self, loc, val):
        if not (0 <= val <= 255):
            exit("Error: POKE(%d),%d out of range" % (loc, val))

        self.memory[loc] = val

    # define LO() (MEM(pc))
    def lo(self):
        return self.get_mem(self.pc)

    # define HI() (MEM(pc+1))
    def hi(self):
        return self.get_mem((self.pc + 1) & 0xffff)

    # define FETCH() (MEM(pc++))
    def fetch(self):
        self.pc &= 0xffff
        val = self.get_mem(self.pc)
        self.pc = (self.pc + 1) & 0xffff
        return val

    # define PUSH(data) (MEM(0x100 + (sp--)) = (data))
    def push(self, data):
        self.set_mem(0x100 + self.sp, data)
        self.sp -= 1
        self.sp &= 0xff  # this will wrap -1 to 255, as it should

    # define POP() (MEM(0x100 + (++sp)))
    def pop(self):
        self.sp += 1
        # If poping from an empty stack (sp == $FF), this must wrap to 0
        # http://forum.6502.org/viewtopic.php?f=8&t=1446
        self.sp &= 0xff
        result = self.get_mem(0x100 + self.sp)
        return result

    # define IMMEDIATE() (LO())
    def immediate(self):
        return self.lo()

    # define ABSOLUTE() (LO() | (HI() << 8))
    def absolute(self):
        return self.lo() | (self.hi() << 8)

    # define ABSOLUTEX() (((LO() | (HI() << 8)) + x) & 0xffff)
    def absolute_x(self):
        return (self.absolute() + self.x) & 0xffff

    # define ABSOLUTEY() (((LO() | (HI() << 8)) + y) & 0xffff)
    def absolute_y(self):
        return (self.absolute() + self.y) & 0xffff

    # define ZEROPAGE() (LO() & 0xff)
    def zeropage(self):
        return self.lo() & 0xff

    # define ZEROPAGEX() ((LO() + x) & 0xff)
    def zeropage_x(self):
        return (self.lo() + self.x) & 0xff

    # define ZEROPAGEY() ((LO() + y) & 0xff)
    def zeropage_y(self):
        return (self.lo() + self.y) & 0xff

    # define INDIRECTX() (MEM((LO() + x) & 0xff) | (MEM((LO() + x + 1) & 0xff) << 8))
    def indirect_x(self):
        return self.get_mem((self.lo() + self.x) & 0xff) | (self.get_mem((self.lo() + self.x + 1) & 0xff) << 8)

    # define INDIRECTY() (((MEM(LO()) | (MEM((LO() + 1) & 0xff) << 8)) + y) & 0xffff)
    def indirect_y(self):
        zp_vec = self.get_mem(self.pc)
        return ((self.get_mem(zp_vec) | (self.get_mem((zp_vec + 1) & 0xff) << 8)) + self.y) & 0xffff

    # define INDIRECTZP() (((MEM(LO()) | (MEM((LO() + 1) & 0xff) << 8)) + 0) & 0xffff)
    def indirect_zp(self):
        zp_vec = self.get_mem(self.pc)
        return ((self.get_mem(zp_vec) | (self.get_mem((zp_vec + 1) & 0xff) << 8)) + 0) & 0xffff

    # define EVALPAGECROSSING(baseaddr, realaddr) ((((baseaddr) ^ (realaddr)) & 0xff00) ? 1 : 0)
    def eval_page_crossing(self, baseaddr, realaddr):
        if (baseaddr ^ realaddr) & 0xff00 != 0:
            return 1
        return 0

    # define EVALPAGECROSSING_ABSOLUTEX() (EVALPAGECROSSING(ABSOLUTE(), ABSOLUTEX()))
    def eval_page_crossing_absolute_x(self):
        return self.eval_page_crossing(self.absolute(), self.absolute_x())

    # define EVALPAGECROSSING_ABSOLUTEY() (EVALPAGECROSSING(ABSOLUTE(), ABSOLUTEY()))
    def eval_page_crossing_absolute_y(self):
        return self.eval_page_crossing(self.absolute(), self.absolute_y())

    # define EVALPAGECROSSING_INDIRECTY() (EVALPAGECROSSING(INDIRECTZP(), INDIRECTY()))
    def eval_page_crossing_indirect_y(self):
        return self.eval_page_crossing(self.indirect_zp(), self.indirect_y())

    # #define BRANCH()                                          \
    # {                                                         \
    #   ++cpucycles;                                            \
    #   temp = FETCH();                                         \
    #   if (temp < 0x80)                                        \
    #   {                                                       \
    #     cpucycles += EVALPAGECROSSING(pc, pc + temp);         \
    #     SETPC(pc + temp);                                     \
    #   }                                                       \
    #   else                                                    \
    #   {                                                       \
    #     cpucycles += EVALPAGECROSSING(pc, pc + temp - 0x100); \
    #     SETPC(pc + temp - 0x100);                             \
    #   }                                                       \
    # }
    def branch(self):
        self.cpucycles += 1  # taking the branch adds a cycle
        temp = self.fetch()
        if temp < 0x80:  # if branching forward
            self.cpucycles += self.eval_page_crossing(self.pc, self.pc + temp)
            self.pc = self.pc + temp
        else:
            self.cpucycles += self.eval_page_crossing(self.pc, self.pc + temp - 0x100)
            self.pc = self.pc + temp - 0x100

    # #define SETFLAGS(data)                  \
    # {                                       \
    #   if (!(data))                          \
    #     flags = (flags & ~FN) | FZ;         \
    #   else                                  \
    #     flags = (flags & ~(FN|FZ)) |        \
    #     ((data) & FN);                      \
    # }
    # a_byte from a register value (i.e., a,x,y)
    def set_flags(self, a_byte):
        assert 0 <= a_byte <= 255, "Error: can't set flags using non-byte value"
        if a_byte == 0:
            self.flags = (self.flags & ~FN & 0xff) | FZ
        else:
            # turn off flag's N and Z, then add in a_byte's N
            self.flags = (self.flags & ~(FN | FZ) & 0xff) | (a_byte & FN)
        self.flags |= FU  # might not need this here, but being safe

    # #define ASSIGNSETFLAGS(dest, data)      \
    # {                                       \
    #   dest = data;                          \
    #   if (!dest)                            \
    #     flags = (flags & ~FN) | FZ;         \
    #   else                                  \
    #     flags = (flags & ~(FN|FZ)) |        \
    #     (dest & FN);                        \
    # }
    def assign_then_set_flags(self, dest_operand_ref, src_operand_ref):
        src_byte = src_operand_ref.get_byte(self)
        dest_operand_ref.set_byte(src_byte, self)
        self.set_flags(src_byte)

    # this is needed for the TXS command:
    def assign_no_flag_changes(self, dest_operand_ref, src_operand_ref):
        src_byte = src_operand_ref.get_byte(self)
        dest_operand_ref.set_byte(src_byte, self)

    # #define ADC(data)                                                        \
    # {                                                                        \
    #     unsigned tempval = data;                                             \
    #                                                                          \
    #     if (flags & FD)                                                      \
    #     {                                                                    \
    #         temp = (a & 0xf) + (tempval & 0xf) + (flags & FC);               \
    #         if (temp > 0x9)                                                  \
    #             temp += 0x6;                                                 \
    #         if (temp <= 0x0f)                                                \
    #             temp = (temp & 0xf) + (a & 0xf0) + (tempval & 0xf0);         \
    #         else                                                             \
    #             temp = (temp & 0xf) + (a & 0xf0) + (tempval & 0xf0) + 0x10;  \
    #         if (!((a + tempval + (flags & FC)) & 0xff))                      \
    #             flags |= FZ;                                                 \
    #         else                                                             \
    #             flags &= ~FZ;                                                \
    #         if (temp & 0x80)                                                 \
    #             flags |= FN;                                                 \
    #         else                                                             \
    #             flags &= ~FN;                                                \
    #         if (((a ^ temp) & 0x80) && !((a ^ tempval) & 0x80))              \
    #             flags |= FV;                                                 \
    #         else                                                             \
    #             flags &= ~FV;                                                \
    #         if ((temp & 0x1f0) > 0x90) temp += 0x60;                         \
    #         if ((temp & 0xff0) > 0xf0)                                       \
    #             flags |= FC;                                                 \
    #         else                                                             \
    #             flags &= ~FC;                                                \
    #     }                                                                    \
    #     else                                                                 \
    #     {                                                                    \
    #         temp = tempval + a + (flags & FC);                               \
    #         SETFLAGS(temp & 0xff);                                           \
    #         if (!((a ^ tempval) & 0x80) && ((a ^ temp) & 0x80))              \
    #             flags |= FV;                                                 \
    #         else                                                             \
    #             flags &= ~FV;                                                \
    #         if (temp > 0xff)                                                 \
    #             flags |= FC;                                                 \
    #         else                                                             \
    #             flags &= ~FC;                                                \
    #     }                                                                    \
    #     a = temp;                                                            \
    # }
    # I like the bit logic from here better https://github.com/eteran/pretendo/blob/master/doc/cpu/6502.txt
    def ADC(self, operand_ref):
        data = operand_ref.get_byte(self)
        if (self.flags & FD):
            temp = (self.a & 0xf) + (data & 0xf) + (self.flags & FC)  # not a byte
            if (temp > 0x9):
                temp += 0x6
            if (temp <= 0x0f):
                temp = (temp & 0xf) + (self.a & 0xf0) + (data & 0xf0)
            else:
                temp = (temp & 0xf) + (self.a & 0xf0) + (data & 0xf0) + 0x10
            if not ((self.a + data + (self.flags & FC)) & 0xff):
                self.flags |= FZ
            else:
                self.flags &= (~FZ & 0xff)
            if (temp & 0x80):
                self.flags |= FN
            else:
                self.flags &= (~FN & 0xff)
            if ((self.a ^ temp) & 0x80) and not ((self.a ^ data) & 0x80):
                self.flags |= FV
            else:
                self.flags &= (~FV & 0xff)
            if (temp & 0x1f0) > 0x90:
                temp += 0x60
            if (temp & 0xff0) > 0xf0:
                self.flags |= FC
            else:
                self.flags &= (~FC & 0xff)
        else:
            temp = data + self.a + (self.flags & FC)
            self.set_flags(temp & 0xff)
            if not ((self.a ^ data) & 0x80) and ((self.a ^ temp) & 0x80):
                self.flags |= FV
            else:
                self.flags &= (~FV & 0xff)
            if (temp > 0xff):
                self.flags |= FC
            else:
                self.flags &= (~FC & 0xff)
        self.a = temp & 0xff

    # #define SBC(data)                                                        \
    # {                                                                        \
    #     unsigned tempval = data;                                             \
    #     temp = a - tempval - ((flags & FC) ^ FC);                            \
    #                                                                          \
    #     if (flags & FD)                                                      \
    #     {                                                                    \
    #         unsigned tempval2;                                               \
    #         tempval2 = (a & 0xf) - (tempval & 0xf) - ((flags & FC) ^ FC);    \
    #         if (tempval2 & 0x10)                                             \
    #             tempval2 = ((tempval2 - 6) & 0xf) | ((a & 0xf0) - (tempval   \
    #             & 0xf0) - 0x10);                                             \
    #         else                                                             \
    #             tempval2 = (tempval2 & 0xf) | ((a & 0xf0) - (tempval         \
    #             & 0xf0));                                                    \
    #         if (tempval2 & 0x100)                                            \
    #             tempval2 -= 0x60;                                            \
    #         if (temp < 0x100)                                                \
    #             flags |= FC;                                                 \
    #         else                                                             \
    #             flags &= ~FC;                                                \
    #         SETFLAGS(temp & 0xff);                                           \
    #         if (((a ^ temp) & 0x80) && ((a ^ tempval) & 0x80))               \
    #             flags |= FV;                                                 \
    #         else                                                             \
    #             flags &= ~FV;                                                \
    #         a = tempval2;                                                    \
    #     }                                                                    \
    #     else                                                                 \
    #     {                                                                    \
    #         SETFLAGS(temp & 0xff);                                           \
    #         if (temp < 0x100)                                                \
    #             flags |= FC;                                                 \
    #         else                                                             \
    #             flags &= ~FC;                                                \
    #         if (((a ^ temp) & 0x80) && ((a ^ tempval) & 0x80))               \
    #             flags |= FV;                                                 \
    #         else                                                             \
    #             flags &= ~FV;                                                \
    #         a = temp;                                                        \
    #     }                                                                    \
    # }
    def SBC(self, operand_ref):
        tempval = operand_ref.get_byte(self)
        temp = (self.a - tempval - ((self.flags & FC) ^ FC)) & 0xffff  # not a byte

        if (self.flags & FD):
            tempval2 = ((self.a & 0xf) - (tempval & 0xf) - ((self.flags & FC) ^ FC)) & 0xffff  # not a byte
            if (tempval2 & 0x10):
                tempval2 = (((tempval2 - 6) & 0xf) | ((self.a & 0xf0) - (tempval & 0xf0) - 0x10)) & 0xffff
            else:
                tempval2 = ((tempval2 & 0xf) | ((self.a & 0xf0) - (tempval & 0xf0))) & 0xffff
            if (tempval2 & 0x100):
                tempval2 -= 0x60
                tempval2 &= 0xffff
            if (temp < 0x100):
                self.flags |= FC
            else:
                self.flags &= (~FC & 0xff)
            self.set_flags(temp & 0xff)
            if ((self.a ^ temp) & 0x80) and ((self.a ^ tempval) & 0x80):
                self.flags |= FV
            else:
                self.flags &= (~FV & 0xff)
            self.a = tempval2 & 0xff
        else:
            self.set_flags(temp & 0xff)
            if (temp < 0x100):
                self.flags |= FC
            else:
                self.flags &= (~FC & 0xff)
            if ((self.a ^ temp) & 0x80) and ((self.a ^ tempval) & 0x80):
                self.flags |= FV
            else:
                self.flags &= (~FV & 0xff)
            self.a = temp & 0xff

    # #define CMP(src, data)                  \
    # {                                       \
    #   temp = (src - data) & 0xff;           \
    #                                         \
    #   flags = (flags & ~(FC|FN|FZ)) |       \
    #           (temp & FN);                  \
    #                                         \
    #   if (!temp) flags |= FZ;               \
    #   if (src >= data) flags |= FC;         \
    # }

    # handles CMP, CPX, and CPY
    def CMP(self, reg_operand_ref, operand_ref):
        src = reg_operand_ref.get_byte(self)  # byte from a, x, or y
        data = operand_ref.get_byte(self)  # byte from immediate or memory lookup
        temp = (src - data) & 0xff
        self.flags = (self.flags & ~(FC | FN | FZ) & 0xff) | (temp & FN)
        if not temp:
            self.flags |= FZ
        if src >= data:
            self.flags |= FC

    # #define ASL(data)                       \
    # {                                       \
    #   temp = data;                          \
    #   temp <<= 1;                           \
    #   if (temp & 0x100) flags |= FC;        \
    #   else flags &= ~FC;                    \
    #   ASSIGNSETFLAGS(data, temp);           \
    # }
    def ASL(self, operand_ref):
        temp = operand_ref.get_byte(self)
        temp <<= 1
        if (temp & 0x100):
            self.flags |= FC
        else:
            self.flags &= (~FC & 0xff)
        temp &= 0xff
        self.assign_then_set_flags(operand_ref, OperandRef(BYTE_VAL, temp))

    # #define LSR(data)                       \
    # {                                       \
    #   temp = data;                          \
    #   if (temp & 1) flags |= FC;            \
    #   else flags &= ~FC;                    \
    #   temp >>= 1;                           \
    #   ASSIGNSETFLAGS(data, temp);           \
    # }
    def LSR(self, operand_ref):
        temp = operand_ref.get_byte(self)
        if (temp & 1):
            self.flags |= FC
        else:
            self.flags &= (~FC & 0xff)
        temp >>= 1
        self.assign_then_set_flags(operand_ref, OperandRef(BYTE_VAL, temp))

    # #define ROL(data)                       \
    # {                                       \
    #   temp = data;                          \
    #   temp <<= 1;                           \
    #   if (flags & FC) temp |= 1;            \
    #   if (temp & 0x100) flags |= FC;        \
    #   else flags &= ~FC;                    \
    #   ASSIGNSETFLAGS(data, temp);           \
    # }
    def ROL(self, operand_ref):
        temp = operand_ref.get_byte(self)
        temp <<= 1
        if (self.flags & FC):
            temp |= 1  # aka FC
        if (temp & 0x100):
            self.flags |= FC
        else:
            self.flags &= (~FC & 0xff)
        temp &= 0xff
        self.assign_then_set_flags(operand_ref, OperandRef(BYTE_VAL, temp))

    # #define ROR(data)                       \
    # {                                       \
    #   temp = data;                          \
    #   if (flags & FC) temp |= 0x100;        \
    #   if (temp & 1) flags |= FC;            \
    #   else flags &= ~FC;                    \
    #   temp >>= 1;                           \
    #   ASSIGNSETFLAGS(data, temp);           \
    # }
    def ROR(self, operand_ref):
        temp = operand_ref.get_byte(self)
        if (self.flags & FC):
            temp |= 0x100
        if (temp & 1):
            self.flags |= FC
        else:
            self.flags &= (~FC & 0xff)
        temp >>= 1
        self.assign_then_set_flags(operand_ref, OperandRef(BYTE_VAL, temp))

    # #define DEC(data)                       \
    # {                                       \
    #   temp = data - 1;                      \
    #   ASSIGNSETFLAGS(data, temp);           \
    # }
    def DEC(self, operand_ref):
        temp = operand_ref.get_byte(self) - 1
        temp &= 0xff
        self.assign_then_set_flags(operand_ref, OperandRef(BYTE_VAL, temp))

    # #define INC(data)                       \
    # {                                       \
    #   temp = data + 1;                      \
    #   ASSIGNSETFLAGS(data, temp);           \
    # }
    def INC(self, operand_ref):
        temp = operand_ref.get_byte(self) + 1
        temp &= 0xff
        self.assign_then_set_flags(operand_ref, OperandRef(BYTE_VAL, temp))

    # #define EOR(data)                       \
    # {                                       \
    #   a ^= data;                            \
    #   SETFLAGS(a);                          \
    # }
    def EOR(self, operand_ref):
        self.a ^= operand_ref.get_byte(self)
        self.set_flags(self.a)

    # #define ORA(data)                       \
    # {                                       \
    #   a |= data;                            \
    #   SETFLAGS(a);                          \
    # }
    def ORA(self, operand_ref):
        self.a |= operand_ref.get_byte(self)
        self.set_flags(self.a)

    # #define AND(data)                       \
    # {                                       \
    #   a &= data;                            \
    #   SETFLAGS(a)                           \
    # }
    def AND(self, operand_ref):
        self.a &= operand_ref.get_byte(self)
        self.set_flags(self.a)

    # #define BIT(data)                       \
    # {                                       \
    #   flags = (flags & ~(FN|FV)) |          \
    #           (data & (FN|FV));             \
    #   if (!(data & a)) flags |= FZ;         \
    #   else flags &= ~FZ;                    \
    # }
    def BIT(self, operand_ref):
        temp = operand_ref.get_byte(self)
        self.flags = (self.flags & ~(FN | FV) & 0xff) | (temp & (FN | FV))
        if not (temp & self.a):
            self.flags |= FZ
        else:
            self.flags &= (~FZ & 0xff)

    # void initcpu(unsigned short newpc, unsigned char newa, unsigned char newx, unsigned char newy)
    # {
    #   pc = newpc;
    #   a = newa;
    #   x = newx;
    #   y = newy;
    #   flags = 0;
    #   sp = 0xff;
    #   cpucycles = 0;
    # }
    def init_cpu(self, newpc, newa=0, newx=0, newy=0, flags=FU):
        self.pc = newpc
        self.a = newa
        self.x = newx
        self.y = newy
        self.flags = flags
        self.sp = 0xff
        self.cpucycles = 0
        self.invocationCount = -1

    # ---------------------------------------------------------------------------

    # int runcpu(void)
    # {
    #   unsigned temp;
    #
    #   unsigned char op = FETCH();
    #   /* printf("PC: %04x OP: %02x A:%02x X:%02x Y:%02x\n", pc-1, op, a, x, y); */
    #   cpucycles += cpucycles_table[op];
    #   switch(op)
    #   {
    def runcpu(self):
        # execute instruction.
        # If RTS/RTI (when stack empty) or BRK, return 0, else return 1
        # Throw exception on the not-yet-implemented pseduo-op codes
        if self.debug:
            self.invocationCount += 1
            output_str = "{:08d},PC=${:04x},A=${:02x},X=${:02x},Y=${:02x},SP=${:02x},P=%{:08b}" \
                .format(self.cpucycles, self.pc, self.a, self.x, self.y, self.sp, self.flags)

            print(output_str)

            # Useful for some of the Wolfgang Lorenz tests:
            """
            print("data     b a r ${:02x} ${:02x} ${:02x}".format(self.memory[0x08ec], self.memory[0x08f2], self.memory[0x08f8]))
            print("accum    b a r ${:02x} ${:02x} ${:02x}".format(self.memory[0x08ed], self.memory[0x08f3], self.memory[0x08f9]))
            print("x        b a r ${:02x} ${:02x} ${:02x}".format(self.memory[0x08ee], self.memory[0x08f4], self.memory[0x08fa]))
            print("y        b a r ${:02x} ${:02x} ${:02x}".format(self.memory[0x08ef], self.memory[0x08f5], self.memory[0x08fb]))
            print("flags    b a r ${:08b} ${:08b} ${:08b}".format(self.memory[0x08f0], self.memory[0x08f6], self.memory[0x08fc]))
            print("stackptr b a r ${:08b} ${:08b} ${:08b}".format(self.memory[0x08f1], self.memory[0x08f7], self.memory[0x08fd]))
            """

        instruction = self.fetch()
        self.last_instruction = instruction
        self.cpucycles += cpucycles_table[instruction]

        # Had converted the C case statement to a bunch of elif statements.  However, pylint can't handle
        # that many ("Maximum recursion depth exceeded"), so converted all to if statements with a return
        # after each one.

        # case 0x69:
        # ADC(IMMEDIATE());
        # pc++;
        # break;
        #
        # case 0x65:
        # ADC(MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0x75:
        # ADC(MEM(ZEROPAGEX()));
        # pc++;
        # break;
        #
        # case 0x6d:
        # ADC(MEM(ABSOLUTE()));
        # pc += 2;
        # break;
        #
        # case 0x7d:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEX();
        # ADC(MEM(ABSOLUTEX()));
        #  pc += 2;
        # break;
        #
        # case 0x79:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEY();
        # ADC(MEM(ABSOLUTEY()));
        # pc += 2;
        # break;
        #
        # case 0x61:
        # ADC(MEM(INDIRECTX()));
        # pc++;
        # break;
        #
        # case 0x71:
        # cpucycles += EVALPAGECROSSING_INDIRECTY();
        # ADC(MEM(INDIRECTY()));
        # pc++;
        # break;

        # ADC instructions
        if instruction == 0x69:  # $69/105 ADC #n
            self.ADC(OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0x65:  # $65/101 ADC zp
            self.ADC(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x75:  # $75/117 ADC zp,X
            self.ADC(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0x6d:  # $6D/109 ADC abs
            self.ADC(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x7d:  # $7D/125 ADC abs,X
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.ADC(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0x79:  # $79/121 ADC abs,Y
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.ADC(OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0x61:  # $61/97 ADC (zp,X)
            self.ADC(OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0x71:  # $71/113 ADC (zp),Y
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.ADC(OperandRef(LOC_VAL, self.indirect_y()))
            self.pc += 1
            return 1

        # case 0x29:
        # AND(IMMEDIATE());
        # pc++;
        # break;
        #
        # case 0x25:
        # AND(MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0x35:
        # AND(MEM(ZEROPAGEX()));
        # pc++;
        # break;
        #
        # case 0x2d:
        # AND(MEM(ABSOLUTE()));
        # pc += 2;
        # break;
        #
        # case 0x3d:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEX();
        # AND(MEM(ABSOLUTEX()));
        # pc += 2;
        # break;
        #
        # case 0x39:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEY();
        # AND(MEM(ABSOLUTEY()));
        # pc += 2;
        # break;
        #
        # case 0x21:
        # AND(MEM(INDIRECTX()));
        # pc++;
        # break;
        #
        # case 0x31:
        # cpucycles += EVALPAGECROSSING_INDIRECTY();
        # AND(MEM(INDIRECTY()));
        # pc++;
        # break;

        # AND instructions
        if instruction == 0x29:  # $29/41 AND #n
            self.AND(OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0x25:  # $25/37 AND zp
            self.AND(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x35:  # $35/53 AND zp,X
            self.AND(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0x2d:  # $2D/45 AND abs
            self.AND(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x3d:  # $3D/61 AND abs,X
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.AND(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0x39:  # $39/57 AND abs,Y
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.AND(OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0x21:  # $21/33 AND (zp,X)
            self.AND(OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0x31:  # $31/49 AND (zp),Y
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.AND(OperandRef(LOC_VAL, self.indirect_y()))
            self.pc += 1
            return 1

        # case 0x0a:
        # ASL(a);
        # break;
        #
        # case 0x06:
        # ASL(MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0x16:
        # ASL(MEM(ZEROPAGEX()));
        # pc++;
        # break;
        #
        # case 0x0e:
        # ASL(MEM(ABSOLUTE()));
        # pc += 2;
        # break;
        #
        # case 0x1e:
        # ASL(MEM(ABSOLUTEX()));
        # pc += 2;
        # break;

        # ASL instructions
        if instruction == 0x0a:  # $0A/10 ASL A
            self.ASL(A_OPREF)
            return 1

        if instruction == 0x06:  # $06/6 ASL zp
            self.ASL(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x16:  # $16/22 ASL zp,X
            self.ASL(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0x0e:  # $0E/14 ASL abs
            self.ASL(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x1e:  # $1E/30 ASL abs,X
            self.ASL(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        # case 0x90:
        # if (!(flags & FC)) BRANCH()
        # else pc++;
        # break;

        # BCC instruction
        if instruction == 0x90:  # $90/144 BCC rel
            if not (self.flags & FC):
                self.branch()
            else:
                self.pc += 1
            return 1

        # case 0xb0:
        # if (flags & FC) BRANCH()
        # else pc++;
        # break;

        # BCS instruction
        if instruction == 0xb0:  # $B0/176 BCS rel
            if (self.flags & FC):
                self.branch()
            else:
                self.pc += 1
            return 1

        # case 0xf0:
        # if (flags & FZ) BRANCH()
        # else pc++;
        # break;

        # BEQ instruction
        if instruction == 0xf0:  # $F0/240 BEQ rel
            if (self.flags & FZ):
                self.branch()
            else:
                self.pc += 1
            return 1

        # case 0x24:
        # BIT(MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0x2c:
        # BIT(MEM(ABSOLUTE()));
        # pc += 2;
        # break;

        # BIT instructions
        if instruction == 0x24:  # $24/36 BIT zp
            self.BIT(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x2c:  # $2C/44 BIT abs
            self.BIT(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        # case 0x30:
        # if (flags & FN) BRANCH()
        # else pc++;
        # break;

        # BMI instruction
        if instruction == 0x30:  # $30/48 BMI rel
            if (self.flags & FN):
                self.branch()
            else:
                self.pc += 1
            return 1

        # case 0xd0:
        # if (!(flags & FZ)) BRANCH()
        # else pc++;
        # break;

        # BNE instruction
        if instruction == 0xd0:  # $D0/208 BNE rel
            if not (self.flags & FZ):
                self.branch()
            else:
                self.pc += 1
            return 1

        # case 0x10:
        # if (!(flags & FN)) BRANCH()
        # else pc++;
        # break;

        # BPL instruction
        if instruction == 0x10:  # $10/16 BPL rel
            if not (self.flags & FN):
                self.branch()
            else:
                self.pc += 1
            return 1

        # case 0x50:
        # if (!(flags & FV)) BRANCH()
        # else pc++;
        # break;

        # BVC instruction
        if instruction == 0x50:  # $50/80 BVC rel
            if not (self.flags & FV):
                self.branch()
            else:
                self.pc += 1
            return 1

        # case 0x70:
        # if (flags & FV) BRANCH()
        # else pc++;
        # break;

        # BVS instruction
        if instruction == 0x70:  # $70/112 BVS rel
            if (self.flags & FV):
                self.branch()
            else:
                self.pc += 1
            return 1

        # case 0x18:
        # flags &= ~FC;
        # break;

        # CLC instruction
        if instruction == 0x18:  # $18/24 CLC
            self.flags &= (~FC & 0xff)
            return 1

        # case 0xd8:
        # flags &= ~FD;
        # break;

        # CLD instruction
        if instruction == 0xd8:  # $D8/216 CLD
            self.flags &= (~FD & 0xff)
            return 1

        # case 0x58:
        # flags &= ~FI;
        # break;

        # CLI instruction
        if instruction == 0x58:  # $58/88 CLI
            self.flags &= (~FI & 0xff)
            return 1

        # case 0xb8:
        # flags &= ~FV;
        # break;

        # CLV instruction
        if instruction == 0xb8:  # $B8/184 CLV
            self.flags &= (~FV & 0xff)
            return 1

        # case 0xc9:
        # CMP(a, IMMEDIATE());
        # pc++;
        # break;
        #
        # case 0xc5:
        # CMP(a, MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0xd5:
        # CMP(a, MEM(ZEROPAGEX()));
        # pc++;
        # break;
        #
        # case 0xcd:
        # CMP(a, MEM(ABSOLUTE()));
        # pc += 2;
        # break;
        #
        # case 0xdd:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEX();
        # CMP(a, MEM(ABSOLUTEX()));
        # pc += 2;
        # break;
        #
        # case 0xd9:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEY();
        # CMP(a, MEM(ABSOLUTEY()));
        # pc += 2;
        # break;
        #
        # case 0xc1:
        # CMP(a, MEM(INDIRECTX()));
        # pc++;
        # break;
        #
        # case 0xd1:
        # cpucycles += EVALPAGECROSSING_INDIRECTY();
        # CMP(a, MEM(INDIRECTY()));
        # pc++;
        # break;

        # CMP instructions
        if instruction == 0xc9:  # $C9/201 CMP #n
            self.CMP(A_OPREF, OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xc5:  # $C5/197 CMP zp
            self.CMP(A_OPREF, OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xd5:  # $D5/213 CMP zp,X
            self.CMP(A_OPREF, OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0xcd:  # $CD/205 CMP abs
            self.CMP(A_OPREF, OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xdd:  # $DD/221 CMP abs,X
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.CMP(A_OPREF, OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0xd9:  # $D9/217 CMP abs,Y
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.CMP(A_OPREF, OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0xc1:  # $C1/193 CMP (zp,X)
            self.CMP(A_OPREF, OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0xd1:  # $D1/209 CMP (zp),Y
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.CMP(A_OPREF, OperandRef(LOC_VAL, self.indirect_y()))
            self.pc += 1
            return 1

        # case 0xe0:
        # CMP(x, IMMEDIATE());
        # pc++;
        # break;
        #
        # case 0xe4:
        # CMP(x, MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0xec:
        # CMP(x, MEM(ABSOLUTE()));
        # pc += 2;
        # break;

        # CPX instructions
        if instruction == 0xe0:  # $E0/224 CPX #n
            self.CMP(X_OPREF, OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xe4:  # $E4/228 CPX zp
            self.CMP(X_OPREF, OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xec:  # $EC/236 CPX abs
            self.CMP(X_OPREF, OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        # case 0xc0:
        # CMP(y, IMMEDIATE());
        # pc++;
        # break;
        #
        # case 0xc4:
        # CMP(y, MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0xcc:
        # CMP(y, MEM(ABSOLUTE()));
        # pc += 2;
        # break;

        # CPY instructions
        if instruction == 0xc0:  # $C0/192 CPY #n
            self.CMP(Y_OPREF, OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xc4:  # $C4/196 CPY zp
            self.CMP(Y_OPREF, OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xcc:  # $CC/204 CPY abs
            self.CMP(Y_OPREF, OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        # case 0xc6:
        # DEC(MEM(ZEROPAGE()));
        # WRITE(ZEROPAGE());
        # pc++;
        # break;
        #
        # case 0xd6:
        # DEC(MEM(ZEROPAGEX()));
        # WRITE(ZEROPAGEX());
        # pc++;
        # break;
        #
        # case 0xce:
        # DEC(MEM(ABSOLUTE()));
        # WRITE(ABSOLUTE());
        # pc += 2;
        # break;
        #
        # case 0xde:
        # DEC(MEM(ABSOLUTEX()));
        # WRITE(ABSOLUTEX());
        # pc += 2;
        # break;

        # DEC instructions
        if instruction == 0xc6:  # $C6/198 DEC zp
            self.DEC(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xd6:  # $D6/214 DEC zp,X
            self.DEC(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0xce:  # $CE/206 DEC abs
            self.DEC(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xde:  # $DE/222 DEC abs,X
            self.DEC(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        # case 0xca:
        # x--;
        # SETFLAGS(x);
        # break;

        # DEX instruction
        if instruction == 0xca:  # $CA/202 DEX
            self.x -= 1
            self.x &= 0xff
            self.set_flags(self.x)
            return 1

        # case 0x88:
        # y--;
        # SETFLAGS(y);
        # break;

        # DEY instruction
        if instruction == 0x88:  # $88/136 DEY
            self.y -= 1
            self.y &= 0xff
            self.set_flags(self.y)
            return 1

        # case 0x49:
        # EOR(IMMEDIATE());
        # pc++;
        # break;
        #
        # case 0x45:
        # EOR(MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0x55:
        # EOR(MEM(ZEROPAGEX()));
        # pc++;
        # break;
        #
        # case 0x4d:
        # EOR(MEM(ABSOLUTE()));
        # pc += 2;
        # break;
        #
        # case 0x5d:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEX();
        # EOR(MEM(ABSOLUTEX()));
        # pc += 2;
        # break;
        #
        # case 0x59:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEY();
        # EOR(MEM(ABSOLUTEY()));
        # pc += 2;
        # break;
        #
        # case 0x41:
        # EOR(MEM(INDIRECTX()));
        # pc++;
        # break;
        #
        # case 0x51:
        # cpucycles += EVALPAGECROSSING_INDIRECTY();
        # EOR(MEM(INDIRECTY()));
        # pc++;
        # break;

        # EOR instructions
        if instruction == 0x49:  # $49/73 EOR #n
            self.EOR(OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0x45:  # $45/69 EOR zp
            self.EOR(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x55:  # $55/85 EOR zp,X
            self.EOR(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0x4d:  # $4D/77 EOR abs
            self.EOR(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x5d:  # $5D/93 EOR abs,X
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.EOR(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0x59:  # $59/89 EOR abs,Y
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.EOR(OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0x41:  # $41/65 EOR (zp,X)
            self.EOR(OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0x51:  # $51/81 EOR (zp),Y
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.EOR(OperandRef(LOC_VAL, self.indirect_y()))
            self.pc += 1
            return 1

        # case 0xe6:
        # INC(MEM(ZEROPAGE()));
        # WRITE(ZEROPAGE());
        # pc++;
        # break;
        #
        # case 0xf6:
        # INC(MEM(ZEROPAGEX()));
        # WRITE(ZEROPAGEX());
        # pc++;
        # break;
        #
        # case 0xee:
        # INC(MEM(ABSOLUTE()));
        # WRITE(ABSOLUTE());
        # pc += 2;
        # break;
        #
        # case 0xfe:
        # INC(MEM(ABSOLUTEX()));
        # WRITE(ABSOLUTEX());
        # pc += 2;
        # break;

        # INC instructions
        if instruction == 0xe6:  # $E6/230 INC zp
            self.INC(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xf6:  # $F6/246 INC zp,X
            self.INC(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0xee:  # $EE/238 INC abs
            self.INC(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xfe:  # $FE/254 INC abs,X
            self.INC(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        # case 0xe8:
        # x++;
        # SETFLAGS(x);
        # break;

        # INX instruction
        if instruction == 0xe8:  # $E8/232 INX
            self.x += 1
            self.x &= 0xff
            self.set_flags(self.x)
            return 1

        # case 0xc8:
        # y++;
        # SETFLAGS(y);
        # break;

        # INY instruction
        if instruction == 0xc8:  # $C8/200 INY
            self.y += 1
            self.y &= 0xff
            self.set_flags(self.y)
            return 1

        # case 0x20:
        # PUSH((pc+1) >> 8);
        # PUSH((pc+1) & 0xff);
        # pc = ABSOLUTE();
        # break;

        # JSR instruction
        if instruction == 0x20:  # $20/32 JSR abs
            self.push((self.pc + 1) >> 8)
            self.push((self.pc + 1) & 0xff)
            self.pc = self.absolute()
            return 1

        # case 0x4c:
        # pc = ABSOLUTE();
        # break;
        #
        # case 0x6c:
        # {
        #   unsigned short adr = ABSOLUTE();
        #   pc = (MEM(adr) | (MEM(((adr + 1) & 0xff) | (adr & 0xff00)) << 8));
        # }
        # break;

        # JMP instructions
        if instruction == 0x4c:  # $4C/76 JMP abs
            self.pc = self.absolute()
            return 1

        if instruction == 0x6c:  # $6C/108 JMP (abs)
            adr = self.absolute()
            # Yup, indirect JMP is bug compatible
            self.pc = (self.get_mem(adr) | (self.get_mem(((adr + 1) & 0xff) | (adr & 0xff00)) << 8))
            return 1

        # case 0xa9:
        # ASSIGNSETFLAGS(a, IMMEDIATE());
        # pc++;
        # break;
        #
        # case 0xa5:
        # ASSIGNSETFLAGS(a, MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0xb5:
        # ASSIGNSETFLAGS(a, MEM(ZEROPAGEX()));
        # pc++;
        # break;
        #
        # case 0xad:
        # ASSIGNSETFLAGS(a, MEM(ABSOLUTE()));
        # pc += 2;
        # break;
        #
        # case 0xbd:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEX();
        # ASSIGNSETFLAGS(a, MEM(ABSOLUTEX()));
        # pc += 2;
        # break;
        #
        # case 0xb9:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEY();
        # ASSIGNSETFLAGS(a, MEM(ABSOLUTEY()));
        # pc += 2;
        # break;
        #
        # case 0xa1:
        # ASSIGNSETFLAGS(a, MEM(INDIRECTX()));
        # pc++;
        # break;
        #
        # case 0xb1:
        # cpucycles += EVALPAGECROSSING_INDIRECTY();
        # ASSIGNSETFLAGS(a, MEM(INDIRECTY()));
        # pc++;
        # break;

        # LDA instructions
        if instruction == 0xa9:  # $A9/169 LDA #n
            self.assign_then_set_flags(A_OPREF, OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xa5:  # $A5/165 LDA zp
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xb5:  # $B5/181 LDA zp,X
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0xad:  # $AD/173 LDA abs
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xbd:  # $BD/189 LDA abs,X
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0xb9:  # $B9/185 LDA abs,Y
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0xa1:  # $A1/161 LDA (zp,X)
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0xb1:  # $B1/177 LDA (zp),Y
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.indirect_y()))
            self.pc += 1
            return 1

        # case 0xa2:
        # ASSIGNSETFLAGS(x, IMMEDIATE());
        # pc++;
        # break;
        #
        # case 0xa6:
        # ASSIGNSETFLAGS(x, MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0xb6:
        # ASSIGNSETFLAGS(x, MEM(ZEROPAGEY()));
        # pc++;
        # break;
        #
        # case 0xae:
        # ASSIGNSETFLAGS(x, MEM(ABSOLUTE()));
        # pc += 2;
        # break;
        #
        # case 0xbe:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEY();
        # ASSIGNSETFLAGS(x, MEM(ABSOLUTEY()));
        # pc += 2;
        # break;

        # LDX instructions
        if instruction == 0xa2:  # $A2/162 LDX #n
            self.assign_then_set_flags(X_OPREF, OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xa6:  # $A6/166 LDX zp
            self.assign_then_set_flags(X_OPREF, OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xb6:  # $B6/182 LDX zp,Y
            self.assign_then_set_flags(X_OPREF, OperandRef(LOC_VAL, self.zeropage_y()))
            self.pc += 1
            return 1

        if instruction == 0xae:  # $AE/174 LDX abs
            self.assign_then_set_flags(X_OPREF, OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xbe:  # $BE/190 LDX abs,Y
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.assign_then_set_flags(X_OPREF, OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        # case 0xa0:
        # ASSIGNSETFLAGS(y, IMMEDIATE());
        # pc++;
        # break;
        #
        # case 0xa4:
        # ASSIGNSETFLAGS(y, MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0xb4:
        # ASSIGNSETFLAGS(y, MEM(ZEROPAGEX()));
        # pc++;
        # break;
        #
        # case 0xac:
        # ASSIGNSETFLAGS(y, MEM(ABSOLUTE()));
        # pc += 2;
        # break;
        #
        # case 0xbc:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEX();
        # ASSIGNSETFLAGS(y, MEM(ABSOLUTEX()));
        # pc += 2;
        # break;

        # LDY instructions
        if instruction == 0xa0:  # $A0/160 LDY #n
            self.assign_then_set_flags(Y_OPREF, OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xa4:  # $A4/164 LDY zp
            self.assign_then_set_flags(Y_OPREF, OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xb4:  # $B4/180 LDY zp,X
            self.assign_then_set_flags(Y_OPREF, OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0xac:  # $AC/172 LDY abs
            self.assign_then_set_flags(Y_OPREF, OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xbc:  # $BC/188 LDY abs,X
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.assign_then_set_flags(Y_OPREF, OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        # case 0x4a:
        # LSR(a);
        # break;
        #
        # case 0x46:
        # LSR(MEM(ZEROPAGE()));
        # WRITE(ZEROPAGE());
        # pc++;
        # break;
        #
        # case 0x56:
        # LSR(MEM(ZEROPAGEX()));
        # WRITE(ZEROPAGEX());
        # pc++;
        # break;
        #
        # case 0x4e:
        # LSR(MEM(ABSOLUTE()));
        # WRITE(ABSOLUTE());
        # pc += 2;
        # break;
        #
        # case 0x5e:
        # LSR(MEM(ABSOLUTEX()));
        # WRITE(ABSOLUTEX());
        # pc += 2;
        # break;

        # LSR instructions
        if instruction == 0x4a:  # $4A/74 LSR A
            self.LSR(A_OPREF)
            return 1

        if instruction == 0x46:  # $46/70 LSR zp
            self.LSR(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x56:  # $56/86 LSR zp,X
            self.LSR(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0x4e:  # $4E/78 LSR abs
            self.LSR(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x5e:  # $5E/94 LSR abs,X
            self.LSR(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        # case 0xea:
        # break;

        # NOP instruction
        if instruction == 0xea:  # $EA/234 NOP
            return 1

        # case 0x09:
        # ORA(IMMEDIATE());
        # pc++;
        # break;
        #
        # case 0x05:
        # ORA(MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0x15:
        # ORA(MEM(ZEROPAGEX()));
        # pc++;
        # break;
        #
        # case 0x0d:
        # ORA(MEM(ABSOLUTE()));
        # pc += 2;
        # break;
        #
        # case 0x1d:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEX();
        # ORA(MEM(ABSOLUTEX()));
        # pc += 2;
        # break;
        #
        # case 0x19:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEY();
        # ORA(MEM(ABSOLUTEY()));
        # pc += 2;
        # break;
        #
        # case 0x01:
        # ORA(MEM(INDIRECTX()));
        # pc++;
        # break;
        #
        # case 0x11:
        # cpucycles += EVALPAGECROSSING_INDIRECTY();
        # ORA(MEM(INDIRECTY()));
        # pc++;
        # break;

        # ORA instructions
        if instruction == 0x09:  # $09/9 ORA #n
            self.ORA(OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0x05:  # $05/5 ORA zp
            self.ORA(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x15:  # $15/21 ORA zp,X
            self.ORA(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0x0d:  # $0D/13 ORA abs
            self.ORA(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x1d:  # $1D/29 ORA abs,X
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.ORA(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0x19:  # $19/25 ORA abs,Y
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.ORA(OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0x01:  # $01/1 ORA (zp,X)
            self.ORA(OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0x11:  # $11/17 ORA (zp),Y
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.ORA(OperandRef(LOC_VAL, self.indirect_y()))
            self.pc += 1
            return 1

        # case 0x48:
        # PUSH(a);
        # break;

        # PHA instruction
        if instruction == 0x48:  # $48/72 PHA
            self.push(self.a)
            return 1

        # case == 0x08:
        # PUSH(flags);
        # break;

        # PHP instruction
        if instruction == 0x08:  # $08/8 PHP
            # add in the B flag: https://github.com/eteran/pretendo/blob/master/doc/cpu/6502.txt
            self.push(self.flags | FB)
            return 1

        # case 0x68:
        # ASSIGNSETFLAGS(a, POP());
        # break;

        # PLA instruction
        if instruction == 0x68:  # $68/104 PLA
            self.assign_then_set_flags(A_OPREF, OperandRef(BYTE_VAL, self.pop()))
            return 1

        # case 0x28:
        # flags = POP();
        # break;

        # PLP instruction
        if instruction == 0x28:  # $28/40 PLP
            self.flags = self.pop()

            # https://en.wikipedia.org/wiki/MOS_Technology_6502
            # The "Break" flag of the processor is very different from the other
            # flag bits. It has no flag setting, resetting, or testing instructions
            # of its own, and is not affected by the PHP and PLP instructions. It
            # exists only on the stack, where BRK and PHP always write a 1, while
            # IRQ and NMI always write a 0.
            self.flags &= (~FB & 0xff)  # not done in siddump.c

            self.flags |= FU  # needed for Wolfgang Lorenz tests
            return 1

        # case 0x2a:
        # ROL(a);
        # break;
        #
        # case 0x26:
        # ROL(MEM(ZEROPAGE()));
        # WRITE(ZEROPAGE());
        # pc++;
        # break;
        #
        # case 0x36:
        # ROL(MEM(ZEROPAGEX()));
        # WRITE(ZEROPAGEX());
        # pc++;
        # break;
        #
        # case 0x2e:
        # ROL(MEM(ABSOLUTE()));
        # WRITE(ABSOLUTE());
        # pc += 2;
        # break;
        #
        # case 0x3e:
        # ROL(MEM(ABSOLUTEX()));
        # WRITE(ABSOLUTEX());
        # pc += 2;
        # break;

        # ROL instructions
        if instruction == 0x2a:  # $2A/42 ROL A
            self.ROL(A_OPREF)
            return 1

        if instruction == 0x26:  # $26/38 ROL zp
            self.ROL(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x36:  # $36/54 ROL zp,X
            self.ROL(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0x2e:  # $2E/46 ROL abs
            self.ROL(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x3e:  # $3E/62 ROL abs,X
            self.ROL(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        # case 0x6a:
        # ROR(a);
        # break;
        #
        # case 0x66:
        # ROR(MEM(ZEROPAGE()));
        # WRITE(ZEROPAGE());
        # pc++;
        # break;
        #
        # case 0x76:
        # ROR(MEM(ZEROPAGEX()));
        # WRITE(ZEROPAGEX());
        # pc++;
        # break;
        #
        # case 0x6e:
        # ROR(MEM(ABSOLUTE()));
        # WRITE(ABSOLUTE());
        # pc += 2;
        # break;
        #
        # case 0x7e:
        # ROR(MEM(ABSOLUTEX()));
        # WRITE(ABSOLUTEX());
        # pc += 2;
        # break;

        # ROR instructions
        if instruction == 0x6a:  # $6A/106 ROR A
            self.ROR(A_OPREF)
            return 1

        if instruction == 0x66:  # $66/102 ROR zp
            self.ROR(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x76:  # $76/118 ROR zp,X
            self.ROR(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0x6e:  # $6E/110 ROR abs
            self.ROR(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x7e:  # $7E/126 ROR abs,X
            self.ROR(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        # case 0x40:
        # if (sp == 0xff) return 0;
        # flags = POP();
        # pc = POP();
        # pc |= POP() << 8;
        # break;

        # RTI instruction
        if instruction == 0x40:  # $40/64 RTI
            if (self.exit_on_empty_stack
                    and (self.sp >= 0xfd or 0x00 <= self.sp <= STACK_WRAP_AREA)):
                # If there's not enough stack left for the return or
                # if the stack has already wrapped, then exit.
                return 0
            self.flags = self.pop()  # TODO: clear B flag like we did with PLP?
            self.flags |= FU  # needed for Wolfgang Lorenz tests
            # Note that unlike RTS, the return address on the stack is the actual address
            self.pc = self.pop()
            self.pc |= (self.pop() << 8)
            return 1

        # case 0x60:
        # if (sp == 0xff) return 0;
        # pc = POP();
        # pc |= POP() << 8;
        # pc++;
        # break;

        # RTS instruction
        if instruction == 0x60:  # $60/96 RTS
            if (self.exit_on_empty_stack
                    and (self.sp >= 0xfe or 0x00 <= self.sp <= STACK_WRAP_AREA)):
                # If there's not enough stack left for the return or
                # if the stack has already wrapped, then exit.
                return 0
            self.pc = self.pop()
            self.pc |= (self.pop() << 8)
            self.pc += 1
            return 1

        # case 0xe9:
        # SBC(IMMEDIATE());
        # pc++;
        # break;
        #
        # case 0xe5:
        # SBC(MEM(ZEROPAGE()));
        # pc++;
        # break;
        #
        # case 0xf5:
        # SBC(MEM(ZEROPAGEX()));
        # pc++;
        # break;
        #
        # case 0xed:
        # SBC(MEM(ABSOLUTE()));
        # pc += 2;
        # break;
        #
        # case 0xfd:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEX();
        # SBC(MEM(ABSOLUTEX()));
        # pc += 2;
        # break;
        #
        # case 0xf9:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEY();
        # SBC(MEM(ABSOLUTEY()));
        # pc += 2;
        # break;
        #
        # case 0xe1:
        # SBC(MEM(INDIRECTX()));
        # pc++;
        # break;
        #
        # case 0xf1:
        # cpucycles += EVALPAGECROSSING_INDIRECTY();
        # SBC(MEM(INDIRECTY()));
        # pc++;
        # break;

        # SBC instructions
        # $E9 or (equivalent pseudo op) $EB will work here, see:
        #    https://wiki.nesdev.com/w/index.php/Programming_with_unofficial_opcodes#Duplicated_instructions
        if instruction == 0xe9 or instruction == 0xeb:  # $E9/233 (or $EB/235) SBC #n
            self.SBC(OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xe5:  # $E5/229 SBC zp
            self.SBC(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xf5:  # $F5/245 SBC zp,X
            self.SBC(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0xed:  # $ED/237 SBC abs
            self.SBC(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xfd:  # $FD/253 SBC abs,X
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.SBC(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0xf9:  # $F9/249 SBC abs,Y
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.SBC(OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0xe1:  # $E1/225 SBC (zp,X)
            self.SBC(OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0xf1:  # $F1/241 SBC (zp),Y
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.SBC(OperandRef(LOC_VAL, self.indirect_y()))
            self.pc += 1
            return 1

        # case 0x38:
        # flags |= FC;
        # break;

        # SEC instruction
        if instruction == 0x38:  # $38/56 SEC
            self.flags |= FC
            return 1

        # case 0xf8:
        # flags |= FD;
        # break;

        # SED instruction
        if instruction == 0xf8:  # $F8/248 SED
            self.flags |= FD
            return 1

        # case 0x78:
        # flags |= FI;
        # break;

        # SEI instruction
        if instruction == 0x78:  # $78/120 SEI
            self.flags |= FI
            return 1

        # case 0x85:
        # MEM(ZEROPAGE()) = a;
        # WRITE(ZEROPAGE());
        # pc++;
        # break;
        #
        # case 0x95:
        # MEM(ZEROPAGEX()) = a;
        # WRITE(ZEROPAGEX());
        # pc++;
        # break;
        #
        # case 0x8d:
        # MEM(ABSOLUTE()) = a;
        # WRITE(ABSOLUTE());
        # pc += 2;
        # break;
        #
        # case 0x9d:
        # MEM(ABSOLUTEX()) = a;
        # WRITE(ABSOLUTEX());
        # pc += 2;
        # break;
        #
        # case 0x99:
        # MEM(ABSOLUTEY()) = a;
        # WRITE(ABSOLUTEY());
        # pc += 2;
        # break;
        #
        # case 0x81:
        # MEM(INDIRECTX()) = a;
        # WRITE(INDIRECTX());
        # pc++;
        # break;
        #
        # case 0x91:
        # MEM(INDIRECTY()) = a;
        # WRITE(INDIRECTY());
        # pc++;
        # break;

        # STA instructions
        # Note: STA/X/Y doesn't affect flags
        if instruction == 0x85:  # $85/133 STA zp
            self.set_mem(self.zeropage(), self.a)
            self.pc += 1
            return 1

        if instruction == 0x95:  # $95/149 STA zp,X
            self.set_mem(self.zeropage_x(), self.a)
            self.pc += 1
            return 1

        if instruction == 0x8d:  # $8D/141 STA abs
            self.set_mem(self.absolute(), self.a)
            self.pc += 2
            return 1

        if instruction == 0x9d:  # $9D/157 STA abs,X
            self.set_mem(self.absolute_x(), self.a)
            self.pc += 2
            return 1

        if instruction == 0x99:  # $99/153 STA abs,Y
            self.set_mem(self.absolute_y(), self.a)
            self.pc += 2
            return 1

        if instruction == 0x81:  # $81/129 STA (zp,X)
            self.set_mem(self.indirect_x(), self.a)
            self.pc += 1
            return 1

        if instruction == 0x91:  # $91/145 STA (zp),Y
            self.set_mem(self.indirect_y(), self.a)
            self.pc += 1
            return 1

        # case 0x86:
        # MEM(ZEROPAGE()) = x;
        # WRITE(ZEROPAGE());
        # pc++;
        # break;
        #
        # case 0x96:
        # MEM(ZEROPAGEY()) = x;
        # WRITE(ZEROPAGEY());
        # pc++;
        # break;
        #
        # case 0x8e:
        # MEM(ABSOLUTE()) = x;
        # WRITE(ABSOLUTE());
        # pc += 2;
        # break;

        # STX instructions
        if instruction == 0x86:  # $86/134 STX zp
            self.set_mem(self.zeropage(), self.x)
            self.pc += 1
            return 1

        if instruction == 0x96:  # $96/150 STX zp,Y
            self.set_mem(self.zeropage_y(), self.x)
            self.pc += 1
            return 1

        if instruction == 0x8e:  # $8E/142 STX abs
            self.set_mem(self.absolute(), self.x)
            self.pc += 2
            return 1

        # case 0x84:
        # MEM(ZEROPAGE()) = y;
        # WRITE(ZEROPAGE());
        # pc++;
        # break;
        #
        # case 0x94:
        # MEM(ZEROPAGEX()) = y;
        # WRITE(ZEROPAGEX());
        # pc++;
        # break;
        #
        # case 0x8c:
        # MEM(ABSOLUTE()) = y;
        # WRITE(ABSOLUTE());
        # pc += 2;
        # break;

        # STY instructions
        if instruction == 0x84:  # $84/132 STY zp
            self.set_mem(self.zeropage(), self.y)
            self.pc += 1
            return 1

        if instruction == 0x94:  # $94/148 STY zp,X
            self.set_mem(self.zeropage_x(), self.y)
            self.pc += 1
            return 1

        if instruction == 0x8c:  # $8C/140 STY abs
            self.set_mem(self.absolute(), self.y)
            self.pc += 2
            return 1

        # case 0xaa:
        # ASSIGNSETFLAGS(x, a);
        # break;

        # TAX instruction
        if instruction == 0xaa:  # $AA/170 TAX
            self.assign_then_set_flags(X_OPREF, A_OPREF)
            return 1

        # case 0xba:
        # ASSIGNSETFLAGS(x, sp);
        # break;

        # TSX instruction
        if instruction == 0xba:  # $BA/186 TSX
            self.assign_then_set_flags(X_OPREF, SP_OPREF)
            return 1

        # case 0x8a:
        # ASSIGNSETFLAGS(a, x);
        # break;

        # TXA instruction
        if instruction == 0x8a:  # $8A/138 TXA
            self.assign_then_set_flags(A_OPREF, X_OPREF)
            return 1

        # case 0x9a:
        # ASSIGNSETFLAGS(sp, x);
        # break;

        # TXS instruction
        if instruction == 0x9a:  # $9A/154 TXS
            # Bug in siddump.c < v1.08, TXS does NOT set flags
            self.assign_no_flag_changes(SP_OPREF, X_OPREF)
            return 1

        # case 0x98:
        # ASSIGNSETFLAGS(a, y);
        # break;

        # TYA instruction
        if instruction == 0x98:  # $98/152 TYA
            self.assign_then_set_flags(A_OPREF, Y_OPREF)
            return 1

        # case 0xa8:
        # ASSIGNSETFLAGS(y, a);
        # break;

        # TAY instruction
        if instruction == 0xa8:  # $A8/168 TAY
            self.assign_then_set_flags(Y_OPREF, A_OPREF)
            return 1

        # case 0x00:
        # return 0;

        # BRK instruction
        # http://www.6502.org/tutorials/register_preservation.html
        # https://wiki.nesdev.com/w/index.php/Status_flags
        # Articles say there is no B flag in the processor status register,
        # the bit is unused.  PHP and BRK pushes the P register onto the stack with break
        # bit set, and IRQ/NMI pushes P register with break bit clear.  The "actual" B flag
        # doesn't exist.  I did a BRK in VICE, and sure enough, the B flag wasn't set.

        if instruction == 0x00:  # $00/0 BRK
            # This is unnecessary to implement from a SID playback perspective
            # so siddump.c ignored it
            self.pc += 1  # BRK is a 2-byte opcode (2nd byte is padding)
            self.pc &= 0xffff
            self.push((self.pc) >> 8)
            self.push((self.pc) & 0xff)
            self.push(self.flags | FB)
            self.flags |= FI
            self.pc = self.get_le_word(IRQ)
            return 0

        # case 0xa7:
        # ASSIGNSETFLAGS(a, MEM(ZEROPAGE()));
        # x = a;
        # pc++;
        # break;
        #
        # case 0xb7:
        # ASSIGNSETFLAGS(a, MEM(ZEROPAGEY()));
        # x = a;
        # pc++;
        # break;
        #
        # case 0xaf:
        # ASSIGNSETFLAGS(a, MEM(ABSOLUTE()));
        # x = a;
        # pc += 2;
        # break;
        #
        # case 0xa3:
        # ASSIGNSETFLAGS(a, MEM(INDIRECTX()));
        # x = a;
        # pc++;
        # break;
        #
        # case 0xb3:
        # cpucycles += EVALPAGECROSSING_INDIRECTY();
        # ASSIGNSETFLAGS(a, MEM(INDIRECTY()));
        # x = a;
        # pc++;
        # break;

        # "LAX" pseudo-ops
        if instruction == 0xa7:  # $A7/167 LDA-LDX zp
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.zeropage()))
            self.x = self.a
            self.pc += 1
            return 1

        if instruction == 0xb7:  # $B7/183 LDA-LDX zp,Y
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.zeropage_y()))
            self.x = self.a
            self.pc += 1
            return 1

        if instruction == 0xaf:  # $AF/175 LDA-LDX abs
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.absolute()))
            self.x = self.a
            self.pc += 2
            return 1

        if instruction == 0xa3:  # $A3/163 LDA-LDX (zp,X)
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.indirect_x()))
            self.x = self.a
            self.pc += 1
            return 1

        if instruction == 0xb3:  # $B3/179 LDA-LDX (zp),Y
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.assign_then_set_flags(A_OPREF, OperandRef(LOC_VAL, self.indirect_y()))
            self.x = self.a
            self.pc += 1
            return 1

        # case 0x1a:
        # case 0x3a:
        # case 0x5a:
        # case 0x7a:
        # case 0xda:
        # case 0xfa:
        # break;
        #
        # case 0x80:
        # case 0x82:
        # case 0x89:
        # case 0xc2:
        # case 0xe2:
        # case 0x04:
        # case 0x44:
        # case 0x64:
        # case 0x14:
        # case 0x34:
        # case 0x54:
        # case 0x74:
        # case 0xd4:
        # case 0xf4:
        # pc++;
        # break;
        #
        # case 0x0c:
        # case 0x1c:
        # case 0x3c:
        # case 0x5c:
        # case 0x7c:
        # case 0xdc:
        # case 0xfc:
        # cpucycles += EVALPAGECROSSING_ABSOLUTEX();
        # pc += 2;
        # break;

        # NOP pseudo-ops:

        # NOP size 1, 2 cycle
        # $1A/26 NOP
        # $3A/58 NOP
        # $5A/90 NOP
        # $7A/122 NOP
        # $DA/218 NOP
        # $FA/250 NOP
        if instruction in (0x1a, 0x3a, 0x5a, 0x7a, 0xda, 0xfa):
            return 1

        # NOP (aka SKB) of size 2
        # $80/128 NOP zp
        # $82/130 NOP (or HALT?)
        # $89/137 NOP zp
        # $C2/194 NOP (or HALT?)
        # $E2/226 NOP (or HALT?)
        if (instruction in (0x80, 0x82, 0x89, 0xc2, 0xe2)  # 2 cycle
                # $04/4 NOP zp
                # $44/68 NOP zp
                # $64/100 NOP zp
                or instruction in (0x04, 0x44, 0x64)  # 3 cycle
                # $14/20 NOP zp
                # $34/52 NOP zp
                # $54/84 NOP zp
                # $74/116 NOP zp
                # $D4/212 NOP zp
                # $F4/244 NOP zp
                or instruction in (0x14, 0x34, 0x54, 0x74, 0xd4, 0xf4)):  # 4 cycle
            self.pc += 1
            return 1

        # NOP (aka SKB (skip next byte), does a read that's not stored) size 3, 4(+1) cycle
        # 0x0c is abolute address, so won't trigger page cross cycle
        # the others are absolute indexed x
        # $0C/12 NOP abs
        # $1C/28 NOP abs,X
        # $3C/60 NOP abs,X
        # $5C/92 NOP abs,X
        # $7C/124 NOP abs,X
        # $DC/220 NOP abs,X
        # $FC/252 NOP abs,X
        if instruction in (0x0c, 0x1c, 0x3c, 0x5c, 0x7c, 0xdc, 0xfc):
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.pc += 2
            return 1

        # case 0x02:
        # printf("Error: CPU halt at %04X\n", pc-1);
        # exit(1);
        # break;

        # HALT (aka JAM) pseudo-ops
        # $02/2 HALT
        # $12/18 HALT
        # $22/34 HALT
        # $32/50 HALT
        # $42/66 HALT
        # $52/82 HALT
        # $62/98 HALT
        # $72/114 HALT
        # $92/146 HALT
        # $B2/178 HALT
        # $D2/210 HALT
        # $F2/242 HALT
        if instruction in (0x02, 0x12, 0x22, 0x32, 0x42, 0x52, 0x62, 0x72, 0x92,
                           0xb2, 0xd2, 0xf2):
            raise ChiptuneSAKValueError("Error: CPU halt on ${:02X} at ${:04X}\n".format(instruction, self.pc - 1))

        # Pseudo-ops probably not needed for SID content extraction
        # $03/3 ASL-ORA (zp,X)
        # $07/7 ASL-ORA zp
        # $0B/11 AND #n/MOV b7->Cy
        # $0F/15 ASL-ORA abs
        # $13/19 ASL-ORA (zp),Y
        # $17/23 ASL-ORA abs,X
        # $1B/27 ASL-ORA abs,Y
        # $1F/31 ASL-ORA abs,X
        # $23/35 ROL-AND (zp,X)
        # $27/39 ROL-AND zp
        # $2B/43 AND #n-MOV b7->Cy
        # $2F/47 ROL-AND abs
        # $33/51 ROL-AND (zp),Y
        # $37/55 ROL-AND zp,X
        # $3B/59 ROL-AND abs,Y
        # $3F/63 ROL-AND abs,X
        # $43/67 LSR-EOR (zp,X)
        # $47/71 LSR-EOR zp
        # $4B/75 AND #n-LSR A
        # $4F/79 LSR-EOR abs
        # $53/83 LSR-EOR (zp),Y
        # $57/87 LSR-EOR abs,X
        # $5B/91 LSR-EOR abs,Y
        # $5F/95 LSR-EOR abs,X
        # $63/99 ROR-ADC (zp,X)
        # $67/103 ROR-ADC zp
        # $6B/107 AND #n-ROR A
        # $6F/111 ROR-ADC abs
        # $73/115 ROR-ADC (zp),Y
        # $77/119 ROR-ADC abs,X
        # $7B/123 ROR-ADC abs,Y
        # $7F/127 ROR-ADC abs,X
        # $83/131 STA-STX (zp,X)
        # $87/135 STA-STX zp
        # $8B/139 TXA-AND #n
        # $8F/143 STA-STX abs
        # $93/147 STA-STX (zp),Y
        # $97/151 STA-STX zp,Y
        # $9B/155 STA-STX abs,Y
        # $9C/156 STA-STX abs,X
        # $9E/158 STA-STX abs,X
        # $9F/159 STA-STX abs,X
        # $AB/171 LDA-LDX
        # $BB/187 LDA-LDX abs,Y
        # $BF/191 LDA-LDX abs,Y
        # $C3/195 DEC-CMP (zp,X)
        # $C7/199 DEC-CMP zp
        # $CB/203 SBX #n
        # $CF/207 DEC-CMP abs
        # $D3/211 DEC-CMP (zp),Y
        # $D7/215 DEC-CMP zp,X
        # $DB/219 DEC-CMP abs,Y
        # $DF/223 DEC-CMP abs,X
        # $E3/227 INC-SBC (zp,X)
        # $E7/231 INC-SBC zp
        # $EF/239 INC-SBC abs
        # $F3/243 INC-SBC (zp),Y
        # $F7/247 INC-SBC zp,X
        # $FB/251 INC-SBC abs,Y
        # $FF/255 INC-SBC abs,X

        raise ChiptuneSAKNotImplemented("Error: unknown/unimplemented opcode %s at %s" % (hex(instruction), hex(self.pc - 1)))

    def get_le_word(self, mem_loc):
        """
        Get a little-endian 16-bit value from a given memory loc

        :param mem_loc: location from which to retreive 16-bit value
        :type mem_loc: int
        :return: 16-bit le value at mem_loc
        :rtype: int
        """
        return self.get_mem(mem_loc) | (self.get_mem(mem_loc + 1) << 8)

    def set_le_word(self, mem_loc, word):
        """
        Set a little-endian 16-bit value at the given memory loc

        :param mem_loc: location at which to set 16-bit value
        :type mem_loc: int
        :param word: value to store in memory
        :type word: int
        """
        if not 0 <= word <= 65535:
            raise ChiptuneSAKValueError('Error: word value "%s" out of range' % word)
        lo = word % 256
        hi = word // 256
        self.set_mem(mem_loc, lo)
        self.set_mem(mem_loc + 1, hi)

    def inject_bytes(self, mem_loc, bytes):
        """
        Puts bytes directly into RAM (pays no attention to banking)

        :param mem_loc: starting memory location
        :type mem_loc: int
        :param bytes: bytes to inject into RAM
        :type bytes: bytes
        """
        for i, a_byte in enumerate(bytes):
            self.memory[mem_loc + i] = a_byte

    def clear_memory_usage(self):
        """
        Utility for debugging:  Clears the R/W memory usage tracking.
        Useful for removing the records of memory setup actions before a program starts
        running.
        """
        self.mem_usage = 0x10000 * [0x00]

    def print_stack(self):
        """
        Utility for debugging:  Print the stack ($100 to $1FF)
        """
        print(hexdump(self.memory[256:512], 256))
        print('current stack pointer ${:02x}'.format(self.sp))

    def print_memory_usage(self):
        """
        Utility for debugging: Show what memory locations have had read or write actions
        """
        for loc, usage in enumerate(self.mem_usage):
            if usage > 0:
                output = '${:04x}/{:d} '.format(loc, loc)
                if usage & MEM_USAGE_READ:
                    output += 'R'
                    if usage & MEM_USAGE_WRITE:
                        output += '/'
                if usage & MEM_USAGE_WRITE:
                    output += 'W'
                print(output)

    def update_zp_usage(self, a_set):
        """
        Update the passed in set with zero page locations with write activity
        """
        for loc in range(0, 256):
            if self.mem_usage[loc] & MEM_USAGE_WRITE:
                a_set.add(loc)


# The original C code used macros, which resulted in a crazy amount of polymorphism
# Going to take the simple class approach to absorb some of that generality
# OperandRef can be a reference to registers, byte vals (often immediates), and memory locations
class OperandRef:
    def __init__(self, type, val_or_loc=None):
        assert type in (A_REG, X_REG, Y_REG, SP_REG, BYTE_VAL, LOC_VAL), \
            "Error: invalid enum type when instantiating a new OperandRef"
        if type in (A_REG, X_REG, Y_REG, SP_REG) and val_or_loc is not None:
            raise ChiptuneSAKValueError("Error: value not needed for operand of type register")
        if type in (BYTE_VAL, LOC_VAL) and val_or_loc is None:
            raise ChiptuneSAKValueError("Error: value needed for operand")
        if type == BYTE_VAL and not (0 <= val_or_loc <= 255):
            raise ChiptuneSAKValueError("Error: byte value out of range")
        if type == LOC_VAL and not (0 <= val_or_loc <= 65535):
            raise ChiptuneSAKValueError("Error: memory location out of range")

        self.type = type
        self.val_or_loc = val_or_loc

    # this sets the contents of the register or memory location to byte_val
    def set_byte(self, byte_val, cpuInstance):
        if self.type == A_REG:
            cpuInstance.a = byte_val
        elif self.type == X_REG:
            cpuInstance.x = byte_val
        elif self.type == Y_REG:
            cpuInstance.y = byte_val
        elif self.type == SP_REG:
            cpuInstance.sp = byte_val
        elif self.type == LOC_VAL:
            cpuInstance.set_mem(self.val_or_loc, byte_val)
        else:
            raise ChiptuneSAKValueError("Error: unable to set OperandRef to a byte value")

    # this returns the register value, the fixed value, or the memory location's
    #    content value
    def get_byte(self, cpuInstance):
        if self.type == A_REG:
            result = cpuInstance.a
        elif self.type == X_REG:
            result = cpuInstance.x
        elif self.type == Y_REG:
            result = cpuInstance.y
        elif self.type == SP_REG:
            result = cpuInstance.sp
        elif self.type == LOC_VAL:
            result = cpuInstance.get_mem(self.val_or_loc)
        else:  # BYTE_VAL
            result = self.val_or_loc
        if not (0 <= result <= 255):
            raise ChiptuneSAKValueError("Error: byte out of range")
        return result


# operand "enums" (set outside normal byte range to avoid inband errors)
A_REG = 0x01 + 0xFF
X_REG = 0x02 + 0xFF
Y_REG = 0x03 + 0xFF
SP_REG = 0x04 + 0xFF
BYTE_VAL = 0x05 + 0xFF  # immediate values
LOC_VAL = 0x06 + 0xFF  # memory location ($0 to $FFFF)

A_OPREF = OperandRef(A_REG)
X_OPREF = OperandRef(X_REG)
Y_OPREF = OperandRef(Y_REG)
SP_OPREF = OperandRef(SP_REG)

# debugging main
if __name__ == "__main__":
    print("Nothing to do")
    pass
