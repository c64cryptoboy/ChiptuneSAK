# 6502 instruction-level emulation
#
# Python code based on C code from https://csdb.dk/release/?id=152422

# TODOs:
# - make all this into a class with no globals
# - after testing, change method and variable names to python practices (MEM, FETCH(), etc.)
# - TODO: make all PC incrementing call a method that insures wrapping (i.e., & 0xFFFF)

# MUST DO:  INDIRECT_Y was wrong, Check INDIRECT_X!!!!!!!!

from ctsBytesUtil import little_endian_int, read_binary_file, hex_to_int
from ctsConstants import ARCH

OUTPUT = True
WRITE_LOG = False

if WRITE_LOG:
    debug_outfile = open(r'sandbox/output.csv', 'w')
else:
    debug_outfile = None

# operand "enums" (set outside normal byte range to avoid inband errors)
A_REG = 0x01 + 0xFF
X_REG = 0x02 + 0xFF
Y_REG = 0x03 + 0xFF
SP_REG = 0x04 + 0xFF
BYTE_VAL = 0x05 + 0xFF # immediate values
LOC_VAL = 0x06 + 0xFF # memory location ($0 to $FFFF)

FN = 0b10000000 # Negative
FV = 0b01000000 # oVerflow
FU = 0b00100000 # Unused
FB = 0b00010000 # Break
FD = 0b00001000 # Decimal
FI = 0b00000100 # Interrupt
FZ = 0b00000010 # Zero
FC = 0b00000001 # Carry

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


class Cpu6502Emulator:

# Note: memory is integers, not bytes, because we want to be able to perform
# arbitrary assignments
    def __init__(self):
        self.memory = 0x10000 * [0x00]  #: 64K memory as integers
        self.a = 0                      #: accumulator (byte)
        self.x = 0                      #: x register (byte)
        self.y = 0                      #: y register (byte)
        self.flags = 0                  #: flags (byte)
        self.sp = 0                     #: stack pointer (byte)        
        self.pc = 0                     #: program counter (16-bit)
        self.has_basic = False          #: True if BASIC ROM loaded
        self.has_kernal = False         #: True if KERNAL ROM loaded
        self.cpucycles = 0              #: count of cpu cycles processed 
        self.rom_ranges = []            #: ranages of immutable memory

    def set_ram(self, loc, val):
        for immutable_range in self.rom_ranges:
            if immutable_range[0] <= loc <= immutable_range[1]:
                return # don't change an immutable memory location
        self.memory[loc] = val

    #define LO() (MEM(pc))
    def lo(self):
        return self.memory[self.pc]

    #define HI() (MEM(pc+1))
    def hi(self):
        return self.memory[(self.pc+1) & 0xffff]

    #define FETCH() (MEM(pc++))
    def fetch(self):
        self.pc &= 0xffff
        val = self.memory[self.pc]
        self.pc = (self.pc + 1) & 0xffff       
        return val

    #define PUSH(data) (MEM(0x100 + (sp--)) = (data))
    def push(self, data):
        self.memory[0x100 + self.sp] = data
        self.sp -= 1; self.sp &= 0xff

    #define POP() (MEM(0x100 + (++sp)))
    def pop(self):
        self.sp += 1; self.sp &= 0xff
        return self.memory[0x100 + self.sp]

    #define IMMEDIATE() (LO())
    def immediate(self):
        return self.lo()

    #define ABSOLUTE() (LO() | (HI() << 8))
    def absolute(self):
        return self.lo() | (self.hi() << 8)

    #define ABSOLUTEX() (((LO() | (HI() << 8)) + x) & 0xffff)
    def absolute_x(self):
        return (self.absolute() + self.x) & 0xffff

    #define ABSOLUTEY() (((LO() | (HI() << 8)) + y) & 0xffff)
    def absolute_y(self):
        return (self.absolute() + self.y) & 0xffff

    #define ZEROPAGE() (LO() & 0xff)
    def zeropage(self):
        return self.lo() & 0xff

    #define ZEROPAGEX() ((LO() + x) & 0xff)
    def zeropage_x(self):
        return (self.lo() + self.x) & 0xff

    #define ZEROPAGEY() ((LO() + y) & 0xff)
    def zeropage_y(self):
        return (self.lo() + self.y) & 0xff

    #define INDIRECTX() (MEM((LO() + x) & 0xff) | (MEM((LO() + x + 1) & 0xff) << 8))
    def indirect_x(self):
        return self.memory[(self.lo() + self.x) & 0xff] | (self.memory[(self.lo() + self.x + 1) & 0xff] << 8)

    #define INDIRECTY() (((MEM(LO()) | (MEM((LO() + 1) & 0xff) << 8)) + y) & 0xffff)
    def indirect_y(self):
        zp_vec = self.memory[self.pc]
        return ((self.memory[zp_vec] | (self.memory[(zp_vec + 1) & 0xff] << 8)) + self.y) & 0xffff

    #define INDIRECTZP() (((MEM(LO()) | (MEM((LO() + 1) & 0xff) << 8)) + 0) & 0xffff)
    def indirect_zp(self):
        #return ((self.memory[self.lo()] | (self.memory[(self.lo() + 1) & 0xff] << 8)) + 0) & 0xffff
        zp_vec = self.memory[self.pc]
        return ((self.memory[zp_vec] | (self.memory[(zp_vec + 1) & 0xff] << 8)) + 0) & 0xffff

    # Drop:
    # #define WRITE(address)                  \
    # {                                       \
    #   /* cpuwritemap[(address) >> 6] = 1; */  \
    # }
    def debug_write(self, address):
        #if 1024 <= address <= 2023:
        """
        if 40960 <= address <= 49151:
            print("DEBUG: attempt to write to BASIC 40960-49151 ($A000-$BFFF) at %d" % (address))
        if 57344 <= address <= 65535:
            print("DEBUG: attempt to write to KERNEL 57344-65535 ($E000-$FFFF) at %d" % (address))
        """
        pass

    #define EVALPAGECROSSING(baseaddr, realaddr) ((((baseaddr) ^ (realaddr)) & 0xff00) ? 1 : 0)
    def eval_page_crossing(self, baseaddr, realaddr):
        if (baseaddr ^ realaddr) & 0xff00 != 0:
            return 1
        return 0

    #define EVALPAGECROSSING_ABSOLUTEX() (EVALPAGECROSSING(ABSOLUTE(), ABSOLUTEX()))
    def eval_page_crossing_absolute_x(self):
        return self.eval_page_crossing(self.absolute(), self.absolute_x())

    #define EVALPAGECROSSING_ABSOLUTEY() (EVALPAGECROSSING(ABSOLUTE(), ABSOLUTEY()))
    def eval_page_crossing_absolute_y(self):
        return self.eval_page_crossing(self.absolute(), self.absolute_y())

    #define EVALPAGECROSSING_INDIRECTY() (EVALPAGECROSSING(INDIRECTZP(), INDIRECTY()))
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
        self.cpucycles += 1 # taking the branch adds a cycle
        temp = self.fetch()                                     
        if temp < 0x80: # if branching forward    
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
            self.flags = (self.flags & ~(FN|FZ) & 0xff) | (a_byte & FN)

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
            temp = (self.a & 0xf) + (data & 0xf) + (self.flags & FC)               
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
        self.a = temp                                                            



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
        # TODO: once this all works, clean up temp vars
        tempval = operand_ref.get_byte(self)                                             
        temp = self.a - tempval - ((self.flags & FC) ^ FC)                            

        if (self.flags & FD):
            tempval2 = (self.a & 0xf) - (tempval & 0xf) - ((self.flags & FC) ^ FC)    
            if (tempval2 & 0x10):                                             
                tempval2 = ((tempval2 - 6) & 0xf) | ((self.a & 0xf0) - (tempval & 0xf0) - 0x10)                                         
            else:
                tempval2 = (tempval2 & 0xf) | ((self.a & 0xf0) - (tempval & 0xf0)) 
            if (tempval2 & 0x100):                                           
                tempval2 -= 0x60                                            
            if (temp < 0x100):                                               
                self.flags |= FC                                                 
            else:                                                             
                self.flags &= (~FC & 0xff)                                                
            self.set_flags(temp & 0xff)                                           
            if ((self.a ^ temp) & 0x80) and ((self.a ^ tempval) & 0x80):              
                self.flags |= FV                                                 
            else:                                                             
                self.flags &= (~FV & 0xff)                                                
            self.a = tempval2                                                    
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
            self.a = temp                                                        

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
        src = reg_operand_ref.get_byte(self) # byte from a, x, or y
        data = operand_ref.get_byte(self) # byte from immediate or memory lookup
        temp = (src - data) & 0xff                                                   
        self.flags = (self.flags & ~(FC|FN|FZ) & 0xff) | (temp & FN)
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
            temp |= 1            
        if (temp & 0x100):
            self.flags |= FC        
        else:
            self.flags &= (~FC & 0xff)                    
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
        self.assign_then_set_flags(operand_ref, OperandRef(BYTE_VAL, temp))           

    # #define INC(data)                       \
    # {                                       \
    #   temp = data + 1;                      \
    #   ASSIGNSETFLAGS(data, temp);           \
    # }
    def INC(self, operand_ref):                       
        temp = operand_ref.get_byte(self) + 1                      
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
        self.flags = (self.flags & ~(FN|FV) & 0xff) | (temp & (FN|FV))             
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
    def init_cpu(self, newpc, newa = 0, newx = 0, newy = 0, flags = FU):
        self.pc = newpc
        self.a = newa
        self.x = newx
        self.y = newy
        self.flags = flags
        self.sp = 0xff
        self.cpucycles = 0


    def byte_hex(self, num):
        return '{0:0{1}X}'.format(num,2)

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
        #mem_watch = 1068
        mem_watch = 40960
        if OUTPUT:
            output_str = "{:08d},PC=${:04x},{:05d},A=${:02x},X=${:02x},Y=${:02x},P=%{:08b},{:05d}={:03d}/${:02x}" \
                .format(self.cpucycles, self.pc, self.pc, self.a, self.x, self.y, self.flags, mem_watch, self.memory[mem_watch], self.memory[mem_watch])
            if WRITE_LOG:
                #print("PC: %s OP: %s A: %s X: %s Y: %s flags: %s" %  (hex(self.pc - 1),
                #    hex(instruction), self.byte_hex(self.a), self.byte_hex(self.x),
                #    self.byte_hex(self.y), format(self.flags, '08b')))
                debug_outfile.write(output_str + "\n")
            else:
                print(output_str)
            #if self.memory[mem_watch] != 148:
            #    exit("CHANGED!")

        instruction = self.fetch()
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
        if instruction == 0x69:
            self.ADC(OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1
        
        if instruction == 0x65:
            self.ADC(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1  
        
        if instruction == 0x75:
            self.ADC(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0x6d:
            self.ADC(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1
                            
        if instruction == 0x7d:
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.ADC(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1
        
        if instruction == 0x79:
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.ADC(OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1
        
        if instruction == 0x61:
            self.ADC(OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1
        
        if instruction == 0x71:
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
        if instruction == 0x29:
            self.AND(OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1
        
        if instruction == 0x25:
            self.AND(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1
        
        if instruction == 0x35:
            self.AND(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1
        
        if instruction == 0x2d:
            self.AND(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x3d:
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.AND(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1
        
        if instruction == 0x39:
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.AND(OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0x21:
            self.AND(OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1
        
        if instruction == 0x31:
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
        if instruction == 0x0a:
            self.ASL(OperandRef(A_REG))
            return 1

        if instruction == 0x06:
            self.ASL(OperandRef(LOC_VAL, self.zeropage()))
            self.pc+=1
            return 1

        if instruction == 0x16:
            self.ASL(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc+=1
            return 1

        if instruction == 0x0e:
            self.ASL(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x1e:
            self.ASL(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        # case 0x90:
        # if (!(flags & FC)) BRANCH()
        # else pc++;
        # break;

        # BCC instruction
        if instruction == 0x90:
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
        if instruction == 0xb0:
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
        if instruction == 0xf0:
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
        if instruction == 0x24:
            self.BIT(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x2c:
            self.BIT(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        # case 0x30:
        # if (flags & FN) BRANCH()
        # else pc++;
        # break;

        # BMI instruction
        if instruction == 0x30:
            if (self.flags & FN):
                self.branch()
            else:
                self.pc +=1
            return 1

        # case 0xd0:
        # if (!(flags & FZ)) BRANCH()
        # else pc++;
        # break;

        # BNE instruction
        if instruction == 0xd0:
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
        if instruction == 0x10:
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
        if instruction == 0x50:
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
        if instruction == 0x70:
            if (self.flags & FV):
                self.branch()
            else:
                self.pc += 1
            return 1

        # case 0x18:
        # flags &= ~FC;
        # break;

        # CLC instruction
        if instruction == 0x18:
            self.flags &= (~FC & 0xff)
            return 1

        # case 0xd8:
        # flags &= ~FD;
        # break;

        # CLD instruction
        if instruction == 0xd8:
            self.flags &= (~FD & 0xff)
            return 1

        # case 0x58:
        # flags &= ~FI;
        # break;

        # CLI instruction
        if instruction == 0x58:
            self.flags &= (~FI & 0xff)
            return 1

        # case 0xb8:
        # flags &= ~FV;
        # break;

        # CLV instruction
        if instruction == 0xb8:
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
        if instruction == 0xc9:
            self.CMP(OperandRef(A_REG), OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xc5:
            self.CMP(OperandRef(A_REG), OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xd5:
            self.CMP(OperandRef(A_REG), OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0xcd:
            self.CMP(OperandRef(A_REG), OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xdd:
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.CMP(OperandRef(A_REG), OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0xd9:
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.CMP(OperandRef(A_REG), OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0xc1:
            self.CMP(OperandRef(A_REG), OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0xd1:
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.CMP(OperandRef(A_REG), OperandRef(LOC_VAL, self.indirect_y()))
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
        if instruction == 0xe0:
            self.CMP(OperandRef(X_REG), OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xe4:
            self.CMP(OperandRef(X_REG), OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xec:
            self.CMP(OperandRef(X_REG), OperandRef(LOC_VAL, self.absolute()))
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
        if instruction == 0xc0:
            self.CMP(OperandRef(Y_REG), OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xc4:
            self.CMP(OperandRef(Y_REG), OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xcc:
            self.CMP(OperandRef(Y_REG), OperandRef(LOC_VAL, self.absolute()))
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
        if instruction == 0xc6:
            self.DEC(OperandRef(self.zeropage()))
            self.debug_write(self.zeropage())
            self.pc += 1
            return 1

        if instruction == 0xd6:
            self.DEC(OperandRef(self.zeropage_x()))
            self.debug_write(self.zeropage_x())
            self.pc += 1
            return 1

        if instruction == 0xce:
            self.DEC(OperandRef(self.absolute()))
            self.debug_write(self.absolute())
            self.pc += 2
            return 1

        if instruction == 0xde:
            self.DEC(OperandRef(self.absolute_x()))
            self.debug_write(self.absolute_x())
            self.pc += 2
            return 1

        # case 0xca:
        # x--;
        # SETFLAGS(x);
        # break;

        # DEX instruction
        if instruction == 0xca:
            self.x -= 1; self.x &= 0xff
            self.set_flags(self.x)
            return 1


        # case 0x88:
        # y--;
        # SETFLAGS(y);
        # break;

        # DEY instruction
        if instruction == 0x88:
            self.y -= 1; self.y &= 0xff
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
        if instruction == 0x49:
            self.EOR(OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0x45:
            self.EOR(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x55:
            self.EOR(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0x4d:
            self.EOR(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x5d:
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.EOR(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0x59:
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.EOR(OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0x41:
            self.EOR(OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0x51:
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
        if instruction == 0xe6:
            self.INC(OperandRef(LOC_VAL, self.zeropage()))
            self.debug_write(self.zeropage())
            self.pc += 1
            return 1

        if instruction == 0xf6:
            self.INC(OperandRef(LOC_VAL, self.zeropage_x()))
            self.debug_write(self.zeropage_x())
            self.pc += 1
            return 1

        if instruction == 0xee:
            self.INC(OperandRef(LOC_VAL, self.absolute()))
            self.debug_write(self.absolute())
            self.pc += 2
            return 1

        if instruction == 0xfe:
            self.INC(OperandRef(LOC_VAL, self.absolute_x()))
            self.debug_write(self.absolute_x())
            self.pc += 2
            return 1


        # case 0xe8:
        # x++;
        # SETFLAGS(x);
        # break;

        # INX instruction
        if instruction == 0xe8:
            self.x += 1; self.x &= 0xff
            self.set_flags(self.x)
            return 1


        # case 0xc8:
        # y++;
        # SETFLAGS(y);
        # break;

        # INY instruction
        if instruction == 0xc8:
            self.y += 1; self.y &= 0xff
            self.set_flags(self.y)
            return 1


        # case 0x20:
        # PUSH((pc+1) >> 8);
        # PUSH((pc+1) & 0xff);
        # pc = ABSOLUTE();
        # break;

        # JSR instruction
        if instruction == 0x20:
            self.push((self.pc+1) >> 8)
            self.push((self.pc+1) & 0xff)
            self.pc = self.absolute()

            # Stub in some kernal routines
            """
            if self.pc == 65490:
                tmp = chr(self.a)
                if not tmp.isprintable():
                    tmp = 'np'
                print("$FFD2 prints '%s' %d" % (tmp, self.a))
            """
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
        if instruction == 0x4c:
            self.pc = self.absolute()
            return 1

        if instruction == 0x6c:
            adr = self.absolute()
            # Yup, indirect JMP is bug compatible
            self.pc = (self.memory[adr] | (self.memory[((adr + 1) & 0xff) | (adr & 0xff00)] << 8))
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
        if instruction == 0xa9:
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xa5:
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xb5:
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0xad:
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xbd:
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0xb9:
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0xa1:
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0xb1:
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.indirect_y()))
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
        if instruction == 0xa2:
            self.assign_then_set_flags(OperandRef(X_REG), OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xa6:
            self.assign_then_set_flags(OperandRef(X_REG), OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xb6:
            self.assign_then_set_flags(OperandRef(X_REG), OperandRef(LOC_VAL, self.zeropage_y()))
            self.pc += 1
            return 1

        if instruction == 0xae:
            self.assign_then_set_flags(OperandRef(X_REG), OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xbe:
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.assign_then_set_flags(OperandRef(X_REG), OperandRef(LOC_VAL, self.absolute_y()))
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
        if instruction == 0xa0:
            self.assign_then_set_flags(OperandRef(Y_REG), OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xa4:
            self.assign_then_set_flags(OperandRef(Y_REG), OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xb4:
            self.assign_then_set_flags(OperandRef(Y_REG), OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0xac:
            self.assign_then_set_flags(OperandRef(Y_REG), OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xbc:
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.assign_then_set_flags(OperandRef(Y_REG), OperandRef(LOC_VAL, self.absolute_x()))
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
        if instruction == 0x4a:
            self.LSR(OperandRef(A_REG))
            return 1

        if instruction == 0x46:
            self.LSR(OperandRef(LOC_VAL, self.zeropage()))
            self.debug_write(self.zeropage())
            self.pc += 1
            return 1

        if instruction == 0x56:
            self.LSR(OperandRef(LOC_VAL, self.zeropage_x()))
            self.debug_write(self.zeropage_x())
            self.pc += 1
            return 1

        if instruction == 0x4e:
            self.LSR(OperandRef(LOC_VAL, self.absolute()))
            self.debug_write(self.absolute())
            self.pc += 2
            return 1

        if instruction == 0x5e:
            self.LSR(OperandRef(LOC_VAL, self.absolute_x()))
            self.debug_write(self.absolute_x())
            self.pc += 2
            return 1


        # case 0xea:
        # break;

        # NOP instruction
        if instruction == 0xea:
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
        if instruction == 0x09:
            self.ORA(OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0x05:
            self.ORA(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0x15:
            self.ORA(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0x0d:
            self.ORA(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0x1d:
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.ORA(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0x19:
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.ORA(OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0x01:
            self.ORA(OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0x11:
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.ORA(OperandRef(LOC_VAL, self.indirect_y()))
            self.pc += 1
            return 1


        # case 0x48:
        # PUSH(a);
        # break;

        # PHA instruction
        if instruction == 0x48:
            self.push(OperandRef(A_REG))
            return 1


        # case == 0x08:
        # PUSH(flags);
        # break;

        # PHP instruction
        # TODO: Pretendo says PHP always pushes B flag as 1...
        if instruction == 0x08:
            self.push(self.flags)
            return 1


        # case 0x68:
        # ASSIGNSETFLAGS(a, POP());
        # break;

        # PLA instruction
        if instruction == 0x68:
            self.assign_then_set_flags(OperandRef(A_REG), self.pop())
            return 1


        # case 0x28:
        # flags = POP();
        # break;

        # PLP instruction
        if instruction == 0x28:
            self.flags = self.pop()
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
        if instruction == 0x2a:
            self.ROL(OperandRef(A_REG))
            return 1

        if instruction == 0x26:
            self.ROL(OperandRef(LOC_VAL, self.zeropage()))
            self.debug_write(self.zeropage())
            self.pc += 1
            return 1

        if instruction == 0x36:
            self.ROL(OperandRef(LOC_VAL, self.zeropage_x()))
            self.debug_write(self.zeropage_x())
            self.pc += 1
            return 1

        if instruction == 0x2e:
            self.ROL(OperandRef(LOC_VAL, self.absolute()))
            self.debug_write(self.absolute())
            self.pc += 2
            return 1

        if instruction == 0x3e:
            self.ROL(OperandRef(LOC_VAL, self.absolute_x()))
            self.debug_write(self.absolute_x())
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
        if instruction == 0x6a:
            self.ROR(OperandRef(A_REG))
            return 1

        if instruction == 0x66:
            self.ROR(OperandRef(LOC_VAL, self.zeropage()))
            self.debug_write(self.zeropage())
            self.pc += 1
            return 1

        if instruction == 0x76:
            self.ROR(OperandRef(LOC_VAL, self.zeropage_x()))
            self.debug_write(self.zeropage_x())
            self.pc += 1
            return 1

        if instruction == 0x6e:
            self.ROR(OperandRef(LOC_VAL, self.absolute()))
            self.debug_write(self.absolute())
            self.pc += 2
            return 1

        if instruction == 0x7e:
            self.ROR(OperandRef(LOC_VAL, self.absolute_x()))
            self.debug_write(self.absolute_x())
            self.pc += 2
            return 1


        # case 0x40:
        # if (sp == 0xff) return 0;
        # flags = POP();
        # pc = POP();
        # pc |= POP() << 8;
        # break;

        # RTI instruction
        if instruction == 0x40:
            if self.sp == 0xff:
                return 0
            self.flags = self.pop()
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
        if instruction == 0x60:
            if self.sp == 0xff:
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
        if instruction == 0xe9:
            self.SBC(OperandRef(BYTE_VAL, self.immediate()))
            self.pc += 1
            return 1

        if instruction == 0xe5:
            self.SBC(OperandRef(LOC_VAL, self.zeropage()))
            self.pc += 1
            return 1

        if instruction == 0xf5:
            self.SBC(OperandRef(LOC_VAL, self.zeropage_x()))
            self.pc += 1
            return 1

        if instruction == 0xed:
            self.SBC(OperandRef(LOC_VAL, self.absolute()))
            self.pc += 2
            return 1

        if instruction == 0xfd:
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.SBC(OperandRef(LOC_VAL, self.absolute_x()))
            self.pc += 2
            return 1

        if instruction == 0xf9:
            self.cpucycles += self.eval_page_crossing_absolute_y()
            self.SBC(OperandRef(LOC_VAL, self.absolute_y()))
            self.pc += 2
            return 1

        if instruction == 0xe1:
            self.SBC(OperandRef(LOC_VAL, self.indirect_x()))
            self.pc += 1
            return 1

        if instruction == 0xf1:
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.SBC(OperandRef(LOC_VAL, self.indirect_y()))
            self.pc += 1
            return 1


        # case 0x38:
        # flags |= FC;
        # break;

        # SEC instruction
        if instruction == 0x38:
            self.flags |= FC
            return 1


        # case 0xf8:
        # flags |= FD;
        # break;

        # SED instruction
        if instruction == 0xf8:
            self.flags |= FD
            return 1


        # case 0x78:
        # flags |= FI;
        # break;

        # SEI instruction
        if instruction == 0x78:
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
        if instruction == 0x85:
            #self.memory[self.zeropage()] = self.a
            self.set_ram(self.zeropage(), self.a)
            self.debug_write(self.zeropage())
            self.pc += 1
            return 1

        if instruction == 0x95:
            #self.memory[self.zeropage_x()] = self.a
            self.set_ram(self.zeropage_x(), self.a)
            self.debug_write(self.zeropage_x())
            self.pc += 1
            return 1

        if instruction == 0x8d:
            #self.memory[self.absolute()] = self.a
            self.set_ram(self.absolute(), self.a)
            self.debug_write(self.absolute())
            self.pc += 2
            return 1

        if instruction == 0x9d:
            #self.memory[self.absolute_x()] = self.a
            self.set_ram(self.absolute_x(), self.a)
            self.debug_write(self.absolute_x())
            self.pc += 2
            return 1

        if instruction == 0x99:
            #self.memory[self.absolute_y()] = self.a
            self.set_ram(self.absolute_y(), self.a)
            self.debug_write(self.absolute_y())
            self.pc += 2
            return 1

        if instruction == 0x81:
            #self.memory[self.indirect_x()] = self.a
            self.set_ram(self.indirect_x(), self.a)
            self.debug_write(self.indirect_x())
            self.pc += 1
            return 1

        if instruction == 0x91:
            #self.memory[self.indirect_y()] = self.a
            self.set_ram(self.indirect_y(), self.a)
            self.debug_write(self.indirect_y())
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
        if instruction == 0x86:
            #self.memory[self.zeropage()] = self.x
            self.set_ram(self.zeropage(), self.x)
            self.debug_write(self.zeropage())
            self.pc += 1
            return 1

        if instruction == 0x96:
            #self.memory[self.zeropage_y()] = self.x
            self.set_ram(self.zeropage_y(), self.x)
            self.debug_write(self.zeropage_y())
            self.pc += 1
            return 1

        if instruction == 0x8e:
            #self.memory[self.absolute()] = self.x
            self.set_ram(self.absolute(), self.x)
            self.debug_write(self.absolute())
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
        if instruction == 0x84:
            #self.memory[self.zeropage()] = self.y
            self.set_ram(self.zeropage(), self.y)
            self.debug_write(self.zeropage())
            self.pc += 1
            return 1

        if instruction == 0x94:
            #self.memory[self.zeropage_x()] = self.y
            self.set_ram(self.zeropage_x(), self.y)
            self.debug_write(self.zeropage_x())
            self.pc += 1
            return 1

        if instruction == 0x8c:
            #self.memory[self.absolute()] = self.y
            self.set_ram(self.absolute(), self.y)
            self.debug_write(self.absolute())
            self.pc += 2
            return 1


        # case 0xaa:
        # ASSIGNSETFLAGS(x, a);
        # break;

        # TAX instruction
        if instruction == 0xaa:
            self.assign_then_set_flags(OperandRef(X_REG), OperandRef(A_REG))
            return 1


        # case 0xba:
        # ASSIGNSETFLAGS(x, sp);
        # break;

        # TSX instruction
        if instruction == 0xba:
            self.assign_then_set_flags(OperandRef(X_REG), OperandRef(SP_REG))
            return 1


        # case 0x8a:
        # ASSIGNSETFLAGS(a, x);
        # break;

        # TXA instruction
        if instruction == 0x8a:
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(X_REG))
            return 1


        # case 0x9a:
        # ASSIGNSETFLAGS(sp, x);
        # break;

        # TXS instruction
        if instruction == 0x9a:
            self.assign_then_set_flags(OperandRef(SP_REG), OperandRef(X_REG))
            return 1


        # case 0x98:
        # ASSIGNSETFLAGS(a, y);
        # break;

        # TYA instruction
        if instruction == 0x98:
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(Y_REG))
            return 1


        # case 0xa8:
        # ASSIGNSETFLAGS(y, a);
        # break;

        # TAY instruction
        if instruction == 0xa8:
            self.assign_then_set_flags(OperandRef(Y_REG), OperandRef(A_REG))
            return 1


        # case 0x00:
        # return 0;

        # BRK instruction
        # TODO: Should set interrupt flag, push PC+2, push flags (like PHP does)
        if instruction == 0x00:
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
        if instruction == 0xa7:
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.zeropage()))
            self.x = self.a
            self.pc += 1
            return 1

        if instruction == 0xb7:
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.zeropage_y()))
            self.x = self.a
            self.pc += 1
            return 1

        if instruction == 0xaf:
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.absolute()))
            self.x = self.a
            self.pc += 2
            return 1

        if instruction == 0xa3:
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.indirect_x()))
            self.x = self.a
            self.pc += 1
            return 1

        if instruction == 0xb3:
            self.cpucycles += self.eval_page_crossing_indirect_y()
            self.assign_then_set_flags(OperandRef(A_REG), OperandRef(LOC_VAL, self.indirect_y()))
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
        if instruction in (0x1a, 0x3a, 0x5a, 0x7a, 0xda, 0xfa):
            return 1

        # NOP (aka SKB) of size 2
        if (instruction in (0x80, 0x82, 0x89, 0xc2, 0xe2) # 2 cycle
            or instruction in (0x04, 0x44, 0x64) # 3 cycle
            or instruction in (0x14, 0x34, 0x54, 0x74, 0xd4, 0xf4)): # 4 cycle
            self.pc += 1
            return 1

        # NOP (aka SKB, does a read that's not stored) size 3, 4(+1) cycle
        # 0x0c is abolute address, so won't trigger page cross cycle
        # the others are absolute indexed x
        if instruction in (0x0c, 0x1c, 0x3c, 0x5c, 0x7c, 0xdc, 0xfc):
            self.cpucycles += self.eval_page_crossing_absolute_x()
            self.pc += 2
            return 1


        # case 0x02:
        # # also 0x12, 0x22, 0x32, 0x42, 0x52, 0x62, 0x72, 0x92, 0xb2, 0xd2, 0xf2
        # printf("Error: CPU halt at %04X\n", pc-1);
        # exit(1);
        # break;

        # JAM pseudo-ops
        if instruction in (0x02, 0x12, 0x22, 0x32, 0x42, 0x52, 0x62, 0x72, 0x92,
            0xb2, 0xd2, 0xf2):
            raise Exception("Error: CPU halt at %s\n" % hex(self.pc-1))

        raise Exception("Error: unknown opcode %s at %s" % (hex(instruction), hex(self.pc-1)))


    def get_addr_at_loc(self, mem_loc):
        return little_endian_int(self.memory[mem_loc:mem_loc+2])


    # allowed to inject into ROM areas, etc.
    def inject_bytes(self, mem_loc, bytes):
        for i, a_byte in enumerate(bytes):
            self.memory[mem_loc + i] = a_byte


    def inject_roms(self):
        path_and_filename = r'res/c64kernal.bin'
        binary = read_binary_file(path_and_filename)
        if binary is not None:
            self.inject_bytes(57344, binary) # KERNAL ROM 57344-65535 ($E000-$FFFF)
            self.has_kernal = True
            self.rom_ranges.append((57344, 65535))            
        else:
            print("Warning: could not find %s" % (path_and_filename))

        path_and_filename = r'res/c64basic.bin'
        binary = read_binary_file(path_and_filename)
        if binary is not None:
            self.inject_bytes(40960, binary) # BASIC ROM 40960-49151 ($A000-$BFFF)
            self.has_basic = True
            self.rom_ranges.append((40960, 49151))             
        else:               
            print("Warning: could not find %s" % (path_and_filename))


# The original C code used macros, which resulted in a crazy amount of polymorphism
# Going to take the simple class approach to absorb some of that generality
# OperandRef can be a reference to registers, byte vals (often immediates), and memory locations
class OperandRef:
    def __init__(self, type, val_or_loc = None):
        assert type in (A_REG, X_REG, Y_REG, SP_REG, BYTE_VAL, LOC_VAL), \
            "Error: invalid enum type when instantiating a new OperandRef"
        if type in (A_REG, X_REG, Y_REG, SP_REG) and val_or_loc is not None:
            raise Exception("Error: value not needed for operand of type register")
        if type in (BYTE_VAL, LOC_VAL) and val_or_loc is None:
            raise Exception("Error: value needed for operand")
        if type == BYTE_VAL and not (0 <= val_or_loc <= 255):
            raise Exception("Error: byte value out of range")
        if type == LOC_VAL and not (0 <= val_or_loc <= 65535):
            raise Exception("Error: memory location out of range")

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
            #cpuInstance.memory[self.val_or_loc] = byte_val
            cpuInstance.set_ram(self.val_or_loc, byte_val)
        else:
            raise Exception("Error: unable to set OperandRef to a byte value")

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
            result = cpuInstance.memory[self.val_or_loc]
        else: # BYTE_VAL
            result = self.val_or_loc
        return result

# debugging main
if __name__ == "__main__":

    # Test 1
    '''    
    cpuState = Cpu6502Emulator()

    # init: init_cpu(initaddress, subtune);
    # play: init_cpu(playaddress);

    test_prog = [160, 15, 152, 89, 12, 128, 32, 210, 255, 136, 208, 246, 96, 12, 71,
        81, 65, 77, 38, 84, 73, 94, 42, 74, 74, 66, 87, 2]

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

    for i, byte in enumerate(test_prog):
        cpuState.memory[32768+i] = byte

    # ROM Patch:  Make $FFD2 print routine just an RTS
    cpuState.memory[65490] = 0x60

    #cpuState.inject_roms()

    cpuState.init_cpu(32768)
    
    while cpuState.runcpu():
        pass
    '''

    # Test 2

    cpuState = Cpu6502Emulator()

    cpuState.inject_roms()

    print("Want to see this used on screen memory:")
    strings = cpuState.memory[58464:58539]
    print(strings)
    for char in strings:
        if not chr(char).isprintable():
            char = ord('~')
        print(chr(char), end='')
    print("\n\n")

    # On a RESET, the CPU loads the vector from $FFFC/$FFFD into the PC
    # then just continues
    reset = cpuState.get_addr_at_loc(65532)

    # According to Michael, B flag not set on reset, as I've seen others do:
    #    https://www.pagetable.com/?p=410
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
        # Among other things, faking the raster keeps up from getting stuck in
        # an infinite loop here:
        # 65371 $FF5B CINT: "Initialize Screen Editor and VIC-Chip"
        #    FF5E   AD 12 D0   LDA $D012
        #    FF61   D0 FB      BNE $FF5E

        # Necessary to have unmodifiable memory in the BASIC ROM area.
        # The ram check only stops when, working its way up from $0801, it hits the
        # BASIC ROM and finds that it can't change it

        # Current bug:  Why didn't the add 40 work?
        if cpuState.cpucycles == 2005051:
            True == True

        if cpuState.cpucycles > 2410000:
            break

        # $E5CA - $E5D5 is waiting for keyboard input, we've gone far enough
        if 58826 <= cpuState.pc <= 58837:
            break 

    # check what's written on the screen 1024-2023 ($0400-$07E7)
    if WRITE_LOG:
        debug_outfile.close()
    print(cpuState.memory[1024:2024])
    pass

    """
    From the Compute book Mapping the C64:
    64738 $FCE2
    Power-On Reset Routine
    This is the RESET routine which is pointed to by the 6510 hardware
    RESET vector at 65532 ($FFFC).
    This routine is automatically executed when the computer is first
    turned on. First, it sets the Interrupt disable flag, sets the stack point
    er, and clears the Decimal mode flag. Next it tests for an autostart
    cartridge. If one is found, the routine immediately jumps through the
    cartridge cold start vector at 32768 ($8000). If no cartridge is found,
    the Kernal initialization routines IOINIT, RAMTAS, RESTOR, and
    CINT are called, the Interrupt disable flag is cleared, and the BASIC
    program is entered through the cold start vector at 40960 ($A000).


    58464 $E460 WORDS
    Power-Up Messages
    The ASCII text of the start-up messages "**** COMMODORE 64
    BASIC V2 ****" and "BYTES FREE" is stored here.

    """

