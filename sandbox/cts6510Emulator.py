# 6510 instruction-level emulation
#
# Python code based on C code from https://csdb.dk/release/?id=152422

# TODOs:
# - Check for unnecessary semicolons
# - all ~ replaced followed by & 0xff
# - make sure all IMMEDIATE is BYTE_VAL
# - make sure all non-IMMEDIATE is LOC_VAL
# - fully grok the PC logic (some instruction implementations here don't adjust it)

MEM = [0] * 0x10000 # TODO: Later make this lowercase
cpucycles = 0

# "global" for the 6510, so global here
a = x = y = flags = sp = pc = 0

# operand "enums" (set outside normal byte range)
A_REG = 0x01 + 0xFF
X_REG = 0x02 + 0xFF
Y_REG = 0x03 + 0xFF
SP_REG = 0x04 + 0xFF
BYTE_VAL = 0x05 + 0xFF # immediate values
LOC_VAL = 0x06 + 0xFF # memory location ($0 to $FFFF)

# base cycle values for instructions 0 through 255:
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

# The original C code used macros, which resulted in a crazy amount of polymorphism
# Going to take the simple class approach to absorb some of that generality
# OperandRef can be a reference to registers, byte vals (immediates), and memory locations
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
    def set_byte(self, byte_val):
        if self.type == A_REG:
            global a
            a = byte_val
        elif self.type == X_REG:
            global x
            x = byte_val
        elif self.type == Y_REG:
            global y
            y = byte_val
        elif self.type == SP_REG:
            global sp
            sp = byte_val
        elif self.type == LOC_VAL:
            global MEM
            MEM[self.val_or_loc] = byte_val
        else:
            raise Exception("Error: unable to set OperandRef to a byte value")

    # this returns the register value, the fixed value, or the memory location's
    #    content value
    def get_byte(self):
        if self.type == A_REG:
            return a
        elif self.type == X_REG:
            return x
        elif self.type == Y_REG:
            return y
        elif self.type == SP_REG:
            return sp
        elif self.type == LOC_VAL:
            return MEM[self.val_or_loc]
        else: # BYTE_VAL
            return self.val_or_loc

FN = 0x80 # Negative
FV = 0x40 # oVerflow
FB = 0x10 # Break
FD = 0x08 # Decimal
FI = 0x04 # Interrupt
FZ = 0x02 # Zero
FC = 0x01 # Carry


"""
TODO:
    >>> "{0:b}".format(~5 & 0x0f)
    '1010'
    >>> f"{~5 & 0x0f:b}"
    '1010'
"""

"""
Drop
#define MEM(address) (mem[address])
"""

#define LO() (MEM(pc))
def LO():
    return MEM[pc]

#define HI() (MEM(pc+1))
def HI():
    return MEM[pc+1]

#define FETCH() (MEM(pc++))
def FETCH():
    global pc
    val = MEM[pc]
    pc += 1
    return val

#define PUSH(data) (MEM(0x100 + (sp--)) = (data))
def PUSH(data):
    global sp
    MEM[0x100 + sp] = data
    sp -= 1

#define POP() (MEM(0x100 + (++sp)))
def POP():
    global sp
    sp += 1
    return MEM[0x100 + sp]

#define IMMEDIATE() (LO())
def IMMEDIATE():
    return LO()

#define ABSOLUTE() (LO() | (HI() << 8))
def ABSOLUTE():
    return LO() | (HI() << 8)

#define ABSOLUTEX() (((LO() | (HI() << 8)) + x) & 0xffff)
def ABSOLUTEX():
    return ((LO() | (HI() << 8)) + x) & 0xffff

#define ABSOLUTEY() (((LO() | (HI() << 8)) + y) & 0xffff)
def ABSOLUTEY():
    return ((LO() | (HI() << 8)) + y) & 0xffff

#define ZEROPAGE() (LO() & 0xff)
def ZEROPAGE():
    return LO() & 0xff

#define ZEROPAGEX() ((LO() + x) & 0xff)
def ZEROPAGEX():
    return (LO() + x) & 0xff

#define ZEROPAGEY() ((LO() + y) & 0xff)
def ZEROPAGEY():
    return (LO() + y) & 0xff

#define INDIRECTX() (MEM((LO() + x) & 0xff) | (MEM((LO() + x + 1) & 0xff) << 8))
def INDIRECTX():
    return MEM[(LO() + x) & 0xff] | (MEM[(LO() + x + 1) & 0xff] << 8)

#define INDIRECTY() (((MEM(LO()) | (MEM((LO() + 1) & 0xff) << 8)) + y) & 0xffff)
def INDIRECTY():
    return ((MEM[LO()] | (MEM[(LO() + 1) & 0xff] << 8)) + y) & 0xffff

#define INDIRECTZP() (((MEM(LO()) | (MEM((LO() + 1) & 0xff) << 8)) + 0) & 0xffff)
def INDIRECTZP():
    return ((MEM[LO()] | (MEM[(LO() + 1) & 0xff] << 8)) + 0) & 0xffff

"""
Drop:
#define WRITE(address)                  \
{                                       \
  /* cpuwritemap[(address) >> 6] = 1; */  \
}
"""
def write(address): # TODO: Kill this later
    return  

#define EVALPAGECROSSING(baseaddr, realaddr) ((((baseaddr) ^ (realaddr)) & 0xff00) ? 1 : 0)
def EVALPAGECROSSING(baseaddr, realaddr):
    if (baseaddr ^ realaddr) & 0xff00 != 0:
        return 1
    return 0

#define EVALPAGECROSSING_ABSOLUTEX() (EVALPAGECROSSING(ABSOLUTE(), ABSOLUTEX()))
def EVALPAGECROSSING_ABSOLUTEX():
    return EVALPAGECROSSING(ABSOLUTE(), ABSOLUTEX())

#define EVALPAGECROSSING_ABSOLUTEY() (EVALPAGECROSSING(ABSOLUTE(), ABSOLUTEY()))
def EVALPAGECROSSING_ABSOLUTEY():
    return EVALPAGECROSSING(ABSOLUTE(), ABSOLUTEY())

#define EVALPAGECROSSING_INDIRECTY() (EVALPAGECROSSING(INDIRECTZP(), INDIRECTY()))
def EVALPAGECROSSING_INDIRECTY():
    EVALPAGECROSSING(INDIRECTZP(), INDIRECTY())

"""
#define BRANCH()                                          \
{                                                         \
  ++cpucycles;                                            \
  temp = FETCH();                                         \
  if (temp < 0x80)                                        \
  {                                                       \
    cpucycles += EVALPAGECROSSING(pc, pc + temp);         \
    SETPC(pc + temp);                                     \
  }                                                       \
  else                                                    \
  {                                                       \
    cpucycles += EVALPAGECROSSING(pc, pc + temp - 0x100); \
    SETPC(pc + temp - 0x100);                             \
  }                                                       \
}
"""
def BRANCH():
    global cpucycles, pc
    cpucycles += 1 # taking the branch adds a cycle
    temp = FETCH()                                     
    if temp < 0x80: # if branching forward    
        cpucycles += EVALPAGECROSSING(pc, pc + temp)   
        pc = pc + temp                            
    else:
        cpucycles += EVALPAGECROSSING(pc, pc + temp - 0x100)
        pc = pc + temp - 0x100

"""
#define SETFLAGS(data)                  \
{                                       \
  if (!(data))                          \
    flags = (flags & ~FN) | FZ;         \
  else                                  \
    flags = (flags & ~(FN|FZ)) |        \
    ((data) & FN);                      \
}
"""
# a_byte from a register value (i.e., a,x,y)
def SETFLAGS(a_byte):
    global flags
    assert 0 <= a_byte <= 255, "Error: can't set flags using non-byte value"
    if a_byte == 0:
        flags = (flags & ~FN & 0xff) | FZ
    else:
        # turn off flag's N and Z, then add in a_byte's N
        flags = (flags & ~(FN|FZ) & 0xff) | (a_byte & FN)

"""
#define ASSIGNSETFLAGS(dest, data)      \
{                                       \
  dest = data;                          \
  if (!dest)                            \
    flags = (flags & ~FN) | FZ;         \
  else                                  \
    flags = (flags & ~(FN|FZ)) |        \
    (dest & FN);                        \
}
"""
# a_byte came from a register value (i.e., a,x,y,sp), a memory lookup, or a stack pop
def ASSIGNSETFLAGS(dest_operand_ref, src_operand_ref):
    src_byte = src_operand_ref.get_byte()
    dest_operand_ref.set_byte(src_byte)
    SETFLAGS(src_byte)

"""
#define ADC(data)                                                        \
{                                                                        \
    unsigned tempval = data;                                             \
                                                                         \
    if (flags & FD)                                                      \
    {                                                                    \
        temp = (a & 0xf) + (tempval & 0xf) + (flags & FC);               \
        if (temp > 0x9)                                                  \
            temp += 0x6;                                                 \
        if (temp <= 0x0f)                                                \
            temp = (temp & 0xf) + (a & 0xf0) + (tempval & 0xf0);         \
        else                                                             \
            temp = (temp & 0xf) + (a & 0xf0) + (tempval & 0xf0) + 0x10;  \
        if (!((a + tempval + (flags & FC)) & 0xff))                      \
            flags |= FZ;                                                 \
        else                                                             \
            flags &= ~FZ;                                                \
        if (temp & 0x80)                                                 \
            flags |= FN;                                                 \
        else                                                             \
            flags &= ~FN;                                                \
        if (((a ^ temp) & 0x80) && !((a ^ tempval) & 0x80))              \
            flags |= FV;                                                 \
        else                                                             \
            flags &= ~FV;                                                \
        if ((temp & 0x1f0) > 0x90) temp += 0x60;                         \
        if ((temp & 0xff0) > 0xf0)                                       \
            flags |= FC;                                                 \
        else                                                             \
            flags &= ~FC;                                                \
    }                                                                    \
    else                                                                 \
    {                                                                    \
        temp = tempval + a + (flags & FC);                               \
        SETFLAGS(temp & 0xff);                                           \
        if (!((a ^ tempval) & 0x80) && ((a ^ temp) & 0x80))              \
            flags |= FV;                                                 \
        else                                                             \
            flags &= ~FV;                                                \
        if (temp > 0xff)                                                 \
            flags |= FC;                                                 \
        else                                                             \
            flags &= ~FC;                                                \
    }                                                                    \
    a = temp;                                                            \
}
"""
# I like the bit logic from here better https://github.com/eteran/pretendo/blob/master/doc/cpu/6502.txt
def ADC(operand_ref):
    data = operand_ref.get_byte()
    global a, flags
    if (flags & FD):                                           
        temp = (a & 0xf) + (data & 0xf) + (flags & FC)               
        if (temp > 0x9):                                                  
            temp += 0x6                                                 
        if (temp <= 0x0f):                                                
            temp = (temp & 0xf) + (a & 0xf0) + (data & 0xf0)         
        else:                                                             
            temp = (temp & 0xf) + (a & 0xf0) + (data & 0xf0) + 0x10  
        if not ((a + data + (flags & FC)) & 0xff):                      
            flags |= FZ                                                 
        else:                                                             
            flags &= (~FZ & 0xff)                                                
        if (temp & 0x80):                                                 
            flags |= FN                                                 
        else:                                                             
            flags &= (~FN & 0xff)                                                
        if ((a ^ temp) & 0x80) and not ((a ^ data) & 0x80): 
            flags |= FV                                                 
        else:                                                             
            flags &= (~FV & 0xff)                                                
        if (temp & 0x1f0) > 0x90:
            temp += 0x60                         
        if (temp & 0xff0) > 0xf0:                                       
            flags |= FC                                                 
        else:                                                             
            flags &= (~FC & 0xff)                                                
    else:                                                                 
        temp = data + a + (flags & FC)                               
        SETFLAGS(temp & 0xff)                                           
        if not ((a ^ data) & 0x80) and ((a ^ temp) & 0x80):              
            flags |= FV                                                 
        else:                                                             
            flags &= (~FV & 0xff)                                                
        if (temp > 0xff):                                                 
            flags |= FC                                                 
        else:                                                             
            flags &= (~FC & 0xff)                                                
    a = temp                                                            


"""
#define SBC(data)                                                        \
{                                                                        \
    unsigned tempval = data;                                             \
    temp = a - tempval - ((flags & FC) ^ FC);                            \
                                                                         \
    if (flags & FD)                                                      \
    {                                                                    \
        unsigned tempval2;                                               \
        tempval2 = (a & 0xf) - (tempval & 0xf) - ((flags & FC) ^ FC);    \
        if (tempval2 & 0x10)                                             \
            tempval2 = ((tempval2 - 6) & 0xf) | ((a & 0xf0) - (tempval   \
            & 0xf0) - 0x10);                                             \
        else                                                             \
            tempval2 = (tempval2 & 0xf) | ((a & 0xf0) - (tempval         \
            & 0xf0));                                                    \
        if (tempval2 & 0x100)                                            \
            tempval2 -= 0x60;                                            \
        if (temp < 0x100)                                                \
            flags |= FC;                                                 \
        else                                                             \
            flags &= ~FC;                                                \
        SETFLAGS(temp & 0xff);                                           \
        if (((a ^ temp) & 0x80) && ((a ^ tempval) & 0x80))               \
            flags |= FV;                                                 \
        else                                                             \
            flags &= ~FV;                                                \
        a = tempval2;                                                    \
    }                                                                    \
    else                                                                 \
    {                                                                    \
        SETFLAGS(temp & 0xff);                                           \
        if (temp < 0x100)                                                \
            flags |= FC;                                                 \
        else                                                             \
            flags &= ~FC;                                                \
        if (((a ^ temp) & 0x80) && ((a ^ tempval) & 0x80))               \
            flags |= FV;                                                 \
        else                                                             \
            flags &= ~FV;                                                \
        a = temp;                                                        \
    }                                                                    \
}
"""
def SBC(operand_ref):
    # TODO: once this all works, clean up temp vars
    global a, flags
    tempval = operand_ref.get_byte()                                             
    temp = a - tempval - ((flags & FC) ^ FC)                            

    if (flags & FD):
        tempval2 = (a & 0xf) - (tempval & 0xf) - ((flags & FC) ^ FC)    
        if (tempval2 & 0x10):                                             
            tempval2 = ((tempval2 - 6) & 0xf) | ((a & 0xf0) - (tempval & 0xf0) - 0x10)                                         
        else:
            tempval2 = (tempval2 & 0xf) | ((a & 0xf0) - (tempval & 0xf0)) 
        if (tempval2 & 0x100):                                           
            tempval2 -= 0x60                                            
        if (temp < 0x100):                                               
            flags |= FC                                                 
        else:                                                             
            flags &= (~FC & 0xff)                                                
        SETFLAGS(temp & 0xff)                                           
        if ((a ^ temp) & 0x80) and ((a ^ tempval) & 0x80):              
            flags |= FV                                                 
        else:                                                             
            flags &= (~FV & 0xff)                                                
        a = tempval2                                                    
    else:                                                                 
        SETFLAGS(temp & 0xff)                                           
        if (temp < 0x100):                                           
            flags |= FC                                                 
        else:                                                             
            flags &= (~FC & 0xff)                                                
        if ((a ^ temp) & 0x80) and ((a ^ tempval) & 0x80):              
            flags |= FV                                                 
        else:                                                             
            flags &= (~FV & 0xff)                                                
        a = temp                                                        

"""
#define CMP(src, data)                  \
{                                       \
  temp = (src - data) & 0xff;           \
                                        \
  flags = (flags & ~(FC|FN|FZ)) |       \
          (temp & FN);                  \
                                        \
  if (!temp) flags |= FZ;               \
  if (src >= data) flags |= FC;         \
}
"""

# handles CMP, CPX, and CPY
def CMP(reg_operand_ref, operand_ref):
    global flags
    src = reg_operand_ref.get_byte() # byte from a, x, or y
    data = operand_ref.get_byte() # byte from immediate or memory lookup
    temp = (src - data) & 0xff                                                   
    flags = (flags & ~(FC|FN|FZ) & 0xff) | (temp & FN)
    if not temp:
        flags |= FZ               
    if src >= data:
        flags |= FC             

"""
#define ASL(data)                       \
{                                       \
  temp = data;                          \
  temp <<= 1;                           \
  if (temp & 0x100) flags |= FC;        \
  else flags &= ~FC;                    \
  ASSIGNSETFLAGS(data, temp);           \
}
"""
def ASL(operand_ref):
    global flags            
    temp = operand_ref.get_byte()                    
    temp <<= 1               
    if (temp & 0x100):
        flags |= FC        
    else:
        flags &= (~FC & 0xff)
    ASSIGNSETFLAGS(operand_ref, OperandRef(BYTE_VAL, temp))        


"""
#define LSR(data)                       \
{                                       \
  temp = data;                          \
  if (temp & 1) flags |= FC;            \
  else flags &= ~FC;                    \
  temp >>= 1;                           \
  ASSIGNSETFLAGS(data, temp);           \
}
"""
def LSR(operand_ref):
    global flags                   
    temp = operand_ref.get_byte()                          
    if (temp & 1):
        flags |= FC            
    else:
        flags &= (~FC & 0xff)                    
    temp >>= 1                           
    ASSIGNSETFLAGS(operand_ref, OperandRef(BYTE_VAL, temp))           

"""
#define ROL(data)                       \
{                                       \
  temp = data;                          \
  temp <<= 1;                           \
  if (flags & FC) temp |= 1;            \
  if (temp & 0x100) flags |= FC;        \
  else flags &= ~FC;                    \
  ASSIGNSETFLAGS(data, temp);           \
}
"""
def ROL(operand_ref):
    global flags                
    temp = operand_ref.get_byte()                          
    temp <<= 1                           
    if (flags & FC):
        temp |= 1            
    if (temp & 0x100):
        flags |= FC        
    else:
        flags &= (~FC & 0xff)                    
    ASSIGNSETFLAGS(operand_ref, OperandRef(BYTE_VAL, temp))           

"""
#define ROR(data)                       \
{                                       \
  temp = data;                          \
  if (flags & FC) temp |= 0x100;        \
  if (temp & 1) flags |= FC;            \
  else flags &= ~FC;                    \
  temp >>= 1;                           \
  ASSIGNSETFLAGS(data, temp);           \
}
"""
def ROR(operand_ref):
    global flags                                                    
    temp = operand_ref.get_byte()                          
    if (flags & FC):
        temp |= 0x100        
    if (temp & 1):
        flags |= FC            
    else:
        flags &= (~FC & 0xff)                    
    temp >>= 1                           
    ASSIGNSETFLAGS(operand_ref, OperandRef(BYTE_VAL, temp))           

"""
#define DEC(data)                       \
{                                       \
  temp = data - 1;                      \
  ASSIGNSETFLAGS(data, temp);           \
}
"""
def DEC(operand_ref):                       
    temp = operand_ref.get_byte() - 1                      
    ASSIGNSETFLAGS(operand_ref, OperandRef(BYTE_VAL, temp))           

"""
#define INC(data)                       \
{                                       \
  temp = data + 1;                      \
  ASSIGNSETFLAGS(data, temp);           \
}
"""
def INC(operand_ref):                       
    temp = operand_ref.get_byte() + 1                      
    ASSIGNSETFLAGS(operand_ref, OperandRef(BYTE_VAL, temp))           

"""
#define EOR(data)                       \
{                                       \
  a ^= data;                            \
  SETFLAGS(a);                          \
}
"""
def EOR(operand_ref):
    global a                  
    a ^= operand_ref.get_byte()                            
    SETFLAGS(a)                          

"""
#define ORA(data)                       \
{                                       \
  a |= data;                            \
  SETFLAGS(a);                          \
}
"""
def ORA(operand_ref):
    global a                    
    a |= operand_ref.get_byte()                            
    SETFLAGS(a)                          

"""
#define AND(data)                       \
{                                       \
  a &= data;                            \
  SETFLAGS(a)                           \
}
"""
def AND(operand_ref):
    global a                    
    a &= operand_ref.get_byte()                            
    SETFLAGS(a)                           

"""
#define BIT(data)                       \
{                                       \
  flags = (flags & ~(FN|FV)) |          \
          (data & (FN|FV));             \
  if (!(data & a)) flags |= FZ;         \
  else flags &= ~FZ;                    \
}
"""
def BIT(operand_ref):
    global flags
    temp = operand_ref.get_byte()
    flags = (flags & ~(FN|FV) & 0xff) | (temp & (FN|FV))             
    if not (temp & a):
        flags |= FZ         
    else:
        flags &= (~FZ & 0xff)                   

"""
void initcpu(unsigned short newpc, unsigned char newa, unsigned char newx, unsigned char newy);
int runcpu(void);
void setpc(unsigned short newpc);

unsigned short pc;
unsigned char a;
unsigned char x;
unsigned char y;
unsigned char flags;
unsigned char sp;
unsigned char mem[0x10000];
unsigned int cpucycles;

static const int cpucycles_table[] = 
{
  7,  6,  0,  8,  3,  3,  5,  5,  3,  2,  2,  2,  4,  4,  6,  6, 
  2,  5,  0,  8,  4,  4,  6,  6,  2,  4,  2,  7,  4,  4,  7,  7, 
  6,  6,  0,  8,  3,  3,  5,  5,  4,  2,  2,  2,  4,  4,  6,  6, 
  2,  5,  0,  8,  4,  4,  6,  6,  2,  4,  2,  7,  4,  4,  7,  7, 
  6,  6,  0,  8,  3,  3,  5,  5,  3,  2,  2,  2,  3,  4,  6,  6, 
  2,  5,  0,  8,  4,  4,  6,  6,  2,  4,  2,  7,  4,  4,  7,  7, 
  6,  6,  0,  8,  3,  3,  5,  5,  4,  2,  2,  2,  5,  4,  6,  6, 
  2,  5,  0,  8,  4,  4,  6,  6,  2,  4,  2,  7,  4,  4,  7,  7, 
  2,  6,  2,  6,  3,  3,  3,  3,  2,  2,  2,  2,  4,  4,  4,  4, 
  2,  6,  0,  6,  4,  4,  4,  4,  2,  5,  2,  5,  5,  5,  5,  5, 
  2,  6,  2,  6,  3,  3,  3,  3,  2,  2,  2,  2,  4,  4,  4,  4, 
  2,  5,  0,  5,  4,  4,  4,  4,  2,  4,  2,  4,  4,  4,  4,  4, 
  2,  6,  2,  8,  3,  3,  5,  5,  2,  2,  2,  2,  4,  4,  6,  6, 
  2,  5,  0,  8,  4,  4,  6,  6,  2,  4,  2,  7,  4,  4,  7,  7, 
  2,  6,  2,  8,  3,  3,  5,  5,  2,  2,  2,  2,  4,  4,  6,  6, 
  2,  5,  0,  8,  4,  4,  6,  6,  2,  4,  2,  7,  4,  4,  7,  7
};

void initcpu(unsigned short newpc, unsigned char newa, unsigned char newx, unsigned char newy)
{
  pc = newpc;
  a = newa;
  x = newx;
  y = newy;
  flags = 0;
  sp = 0xff;
  cpucycles = 0;
}
"""

"""
int runcpu(void)
{
  unsigned temp;

  unsigned char op = FETCH();
  /* printf("PC: %04x OP: %02x A:%02x X:%02x Y:%02x\n", pc-1, op, a, x, y); */
  cpucycles += cpucycles_table[op];
  switch(op)
  {
"""
def runcpu():
    global pc, cpucycles, flags
    instruction = FETCH()
    cpucycles += cpucycles_table[instruction]


    """
    case 0x69:
    ADC(IMMEDIATE());
    pc++;
    break;

    case 0x65:
    ADC(MEM(ZEROPAGE()));
    pc++;
    break;

    case 0x75:
    ADC(MEM(ZEROPAGEX()));
    pc++;
    break;

    case 0x6d:
    ADC(MEM(ABSOLUTE()));
    pc += 2;
    break;

    case 0x7d:
    cpucycles += EVALPAGECROSSING_ABSOLUTEX();
    ADC(MEM(ABSOLUTEX()));
     pc += 2;
    break;

    case 0x79:
    cpucycles += EVALPAGECROSSING_ABSOLUTEY();
    ADC(MEM(ABSOLUTEY()));
    pc += 2;
    break;

    case 0x61:
    ADC(MEM(INDIRECTX()));
    pc++;
    break;

    case 0x71:
    cpucycles += EVALPAGECROSSING_INDIRECTY();
    ADC(MEM(INDIRECTY()));
    pc++;
    break;
    """
    # ADC instructions    
    if instruction == 0x69:
        ADC(OperandRef(BYTE_VAL, IMMEDIATE()))
        pc += 1
    
    elif instruction == 0x65:
        ADC(OperandRef(LOC_VAL, ZEROPAGE()))
        pc += 1
    
    elif instruction == 0x75:
        ADC(OperandRef(LOC_VAL, ZEROPAGEX()))
        pc += 1
    
    elif instruction == 0x6d:
        ADC(OperandRef(LOC_VAL, ABSOLUTE()))
        pc += 2
    
    elif instruction == 0x7d:
        cpucycles += EVALPAGECROSSING_ABSOLUTEX()
        ADC(OperandRef(LOC_VAL, ABSOLUTEX()))
        pc += 2
    
    elif instruction == 0x79:
        cpucycles += EVALPAGECROSSING_ABSOLUTEY()
        ADC(OperandRef(LOC_VAL, ABSOLUTEY()))
        pc += 2
    
    elif instruction == 0x61:
        ADC(OperandRef(LOC_VAL, INDIRECTX()))
        pc += 1
    
    elif instruction == 0x71:
        cpucycles += EVALPAGECROSSING_INDIRECTY()
        ADC(OperandRef(LOC_VAL, INDIRECTY()))
        pc += 1
    

    """
    case 0x29:
    AND(IMMEDIATE());
    pc++;
    break;

    case 0x25:
    AND(MEM(ZEROPAGE()));
    pc++;
    break;

    case 0x35:
    AND(MEM(ZEROPAGEX()));
    pc++;
    break;

    case 0x2d:
    AND(MEM(ABSOLUTE()));
    pc += 2;
    break;

    case 0x3d:
    cpucycles += EVALPAGECROSSING_ABSOLUTEX();
    AND(MEM(ABSOLUTEX()));
    pc += 2;
    break;

    case 0x39:
    cpucycles += EVALPAGECROSSING_ABSOLUTEY();
    AND(MEM(ABSOLUTEY()));
    pc += 2;
    break;

    case 0x21:
    AND(MEM(INDIRECTX()));
    pc++;
    break;

    case 0x31:
    cpucycles += EVALPAGECROSSING_INDIRECTY();
    AND(MEM(INDIRECTY()));
    pc++;
    break;
    """
    # AND instructions    
    if instruction == 0x29:
        AND(OperandRef(BYTE_VAL, IMMEDIATE()))
        pc += 1
    
    elif instruction == 0x25:
        AND(OperandRef(LOC_VAL, ZEROPAGE()))
        pc += 1
    
    elif instruction == 0x35:
        AND(OperandRef(LOC_VAL, ZEROPAGEX()))
        pc += 1
    
    elif instruction == 0x2d:
        AND(OperandRef(LOC_VAL, ABSOLUTE()))
        pc += 2

    elif instruction == 0x3d:
        cpucycles += EVALPAGECROSSING_ABSOLUTEX()
        AND(OperandRef(LOC_VAL, ABSOLUTEX()))
        pc += 2
    
    elif instruction == 0x39:
        cpucycles += EVALPAGECROSSING_ABSOLUTEY()
        AND(OperandRef(LOC_VAL, ABSOLUTEY()))
        pc += 2

    elif instruction == 0x21:
        AND(OperandRef(LOC_VAL, INDIRECTX()))
        pc += 1
    
    elif instruction == 0x31:
        cpucycles += EVALPAGECROSSING_INDIRECTY()
        AND(OperandRef(LOC_VAL, INDIRECTY()))
        pc += 1


    """
    case 0x0a:
    ASL(a);
    break;

    case 0x06:
    ASL(MEM(ZEROPAGE()));
    pc++;
    break;

    case 0x16:
    ASL(MEM(ZEROPAGEX()));
    pc++;
    break;

    case 0x0e:
    ASL(MEM(ABSOLUTE()));
    pc += 2;
    break;

    case 0x1e:
    ASL(MEM(ABSOLUTEX()));
    pc += 2;
    break;
    """
    # ASL instructions
    if instruction == 0x0a:
        ASL(OperandRef(A_REG))

    elif instruction == 0x06:
        ASL(OperandRef(LOC_VAL, ZEROPAGE()))
        pc+=1

    elif instruction == 0x16:
        ASL(OperandRef(LOC_VAL, ZEROPAGEX()))
        pc+=1

    elif instruction == 0x0e:
        ASL(OperandRef(LOC_VAL, ABSOLUTE()))
        pc += 2

    elif instruction == 0x1e:
        ASL(OperandRef(LOC_VAL, ABSOLUTEX()))
        pc += 2

    """
    case 0x90:
    if (!(flags & FC)) BRANCH()
    else pc++;
    break;
    """
    # BCC instruction
    if instruction == 0x90:
        if not (flags & FC):
            BRANCH()
        else:
            pc += 1

    """    
    case 0xb0:
    if (flags & FC) BRANCH()
    else pc++;
    break;
    """
    # BCS instruction
    if instruction == 0xb0:
        if (flags & FC):
            BRANCH()
        else:
            pc += 1

    """
    case 0xf0:
    if (flags & FZ) BRANCH()
    else pc++;
    break;
    """
    # BEQ instruction
    if instruction == 0xf0:
        if (flags & FZ):
            BRANCH()
        else:
            pc += 1

    """  
    case 0x24:
    BIT(MEM(ZEROPAGE()));
    pc++;
    break;

    case 0x2c:
    BIT(MEM(ABSOLUTE()));
    pc += 2;
    break;
    """
    # BIT instructions
    if instruction == 0x24:
        BIT(OperandRef(LOC_VAL, ZEROPAGE()))
        pc += 1

    elif instruction == 0x2c:
        BIT(OperandRef(LOC_VAL, ABSOLUTE()))
        pc += 2

    """
    case 0x30:
    if (flags & FN) BRANCH()
    else pc++;
    break;
    """
    # BMI instruction
    if instruction == 0x30:
        if (flags & FN):
            BRANCH()
        else:
            pc +=1

    """
    case 0xd0:
    if (!(flags & FZ)) BRANCH()
    else pc++;
    break;
    """
    # BNE instruction
    if instruction == 0xd0:
        if not (flags & FZ):
            BRANCH()
        else:
            pc += 1

    """
    case 0x10:
    if (!(flags & FN)) BRANCH()
    else pc++;
    break;
    """
    # BPL instruction
    if instruction == 0x10:
        if not (flags & FN):
            BRANCH()
        else:
            pc += 1

    """
    case 0x50:
    if (!(flags & FV)) BRANCH()
    else pc++;
    break;
    """
    # BVC instruction
    if instruction == 0x50:
        if not (flags & FV):
            BRANCH()
        else:
            pc += 1

    """
    case 0x70:
    if (flags & FV) BRANCH()
    else pc++;
    break;
    """
    # BVS instruction
    if instruction == 0x70:
        if (flags & FV):
            BRANCH()
        else:
            pc += 1

    """
    case 0x18:
    flags &= ~FC;
    break;
    """
    # CLC instruction
    if instruction == 0x18:
        flags &= (~FC & 0xff)

    """
    case 0xd8:
    flags &= ~FD;
    break;
    """
    # CLD instruction
    if instruction == 0xd8:
        flags &= (~FD & 0xff)

    """
    case 0x58:
    flags &= ~FI;
    break;
    """
    # CLI instruction
    if instruction == 0x58:
        flags &= (~FI & 0xff)

    """    
    case 0xb8:
    flags &= ~FV;
    break;
    """
    # CLV instruction
    if instruction == 0xb8:
        flags &= (~FV & 0xff)

    """
    case 0xc9:
    CMP(a, IMMEDIATE());
    pc++;
    break;

    case 0xc5:
    CMP(a, MEM(ZEROPAGE()));
    pc++;
    break;

    case 0xd5:
    CMP(a, MEM(ZEROPAGEX()));
    pc++;
    break;

    case 0xcd:
    CMP(a, MEM(ABSOLUTE()));
    pc += 2;
    break;

    case 0xdd:
    cpucycles += EVALPAGECROSSING_ABSOLUTEX();
    CMP(a, MEM(ABSOLUTEX()));
    pc += 2;
    break;

    case 0xd9:
    cpucycles += EVALPAGECROSSING_ABSOLUTEY();
    CMP(a, MEM(ABSOLUTEY()));
    pc += 2;
    break;

    case 0xc1:
    CMP(a, MEM(INDIRECTX()));
    pc++;
    break;

    case 0xd1:
    cpucycles += EVALPAGECROSSING_INDIRECTY();
    CMP(a, MEM(INDIRECTY()));
    pc++;
    break;
    """
    # CMP instructions
    if instruction == 0xc9:
        CMP(OperandRef(A_REG), OperandRef(BYTE_VAL, IMMEDIATE()))
        pc += 1

    elif instruction == 0xc5:
        CMP(OperandRef(A_REG), OperandRef(LOC_VAL, ZEROPAGE()))
        pc += 1

    elif instruction == 0xd5:
        CMP(OperandRef(A_REG), OperandRef(LOC_VAL, ZEROPAGEX()))
        pc += 1

    elif instruction == 0xcd:
        CMP(OperandRef(A_REG), OperandRef(LOC_VAL, ABSOLUTE()))
        pc += 2

    elif instruction == 0xdd:
        cpucycles += EVALPAGECROSSING_ABSOLUTEX()
        CMP(OperandRef(A_REG), OperandRef(LOC_VAL, ABSOLUTEX()))
        pc += 2

    elif instruction == 0xd9:
        cpucycles += EVALPAGECROSSING_ABSOLUTEY()
        CMP(OperandRef(A_REG), OperandRef(LOC_VAL, ABSOLUTEY()))
        pc += 2

    elif instruction == 0xc1:
        CMP(OperandRef(A_REG), OperandRef(LOC_VAL, INDIRECTX()))
        pc += 1

    elif instruction == 0xd1:
        cpucycles += EVALPAGECROSSING_INDIRECTY()
        CMP(OperandRef(A_REG), OperandRef(LOC_VAL, INDIRECTY()))
        pc += 1

    """
    case 0xe0:
    CMP(x, IMMEDIATE());
    pc++;
    break;

    case 0xe4:
    CMP(x, MEM(ZEROPAGE()));
    pc++;
    break;

    case 0xec:
    CMP(x, MEM(ABSOLUTE()));
    pc += 2;
    break;
    """
    # CPX instructions
    if instruction == 0xe0:
        CMP(OperandRef(X_REG), OperandRef(BYTE_VAL, IMMEDIATE()))
        pc += 1

    elif instruction == 0xe4:
        CMP(OperandRef(X_REG), OperandRef(LOC_VAL, ZEROPAGE()))
        pc += 1

    elif instruction == 0xec:
        CMP(OperandRef(X_REG), OperandRef(LOC_VAL, ABSOLUTE()))
        pc += 2

    """
    case 0xc0:
    CMP(y, IMMEDIATE());
    pc++;
    break;

    case 0xc4:
    CMP(y, MEM(ZEROPAGE()));
    pc++;
    break;

    case 0xcc:
    CMP(y, MEM(ABSOLUTE()));
    pc += 2;
    break;
    """
    # CPY instructions
    if instruction == 0xc0:
        CMP(OperandRef(Y_REG), OperandRef(BYTE_VAL, IMMEDIATE()))
        pc += 1

    elif instruction == 0xc4:
        CMP(OperandRef(Y_REG), OperandRef(LOC_VAL, ZEROPAGE()))
        pc += 1

    elif instruction == 0xcc:
        CMP(OperandRef(Y_REG), OperandRef(LOC_VAL, ABSOLUTE()))
        pc += 2


    """
    case 0xc6:
    DEC(MEM(ZEROPAGE()));
    WRITE(ZEROPAGE());
    pc++;
    break;

    case 0xd6:
    DEC(MEM(ZEROPAGEX()));
    WRITE(ZEROPAGEX());
    pc++;
    break;

    case 0xce:
    DEC(MEM(ABSOLUTE()));
    WRITE(ABSOLUTE());
    pc += 2;
    break;

    case 0xde:
    DEC(MEM(ABSOLUTEX()));
    WRITE(ABSOLUTEX());
    pc += 2;
    break;
    """
    # DEC instructions
    if instruction == 0xc6:
        DEC(OperandRef(ZEROPAGE()))
        WRITE(ZEROPAGE())
        pc += 1

    elif instruction == 0xd6:
        DEC(OperandRef(ZEROPAGEX()))
        WRITE(ZEROPAGEX())
        pc += 1

    elif instruction == 0xce:
        DEC(OperandRef(ABSOLUTE()))
        WRITE(ABSOLUTE())
        pc += 2

    elif instruction == 0xde:
        DEC(OperandRef(ABSOLUTEX()))
        WRITE(ABSOLUTEX())
        pc += 2

# **************************************************************

    """
    case 0xca:
    x--;
    SETFLAGS(x);
    break;
    """
    # DEX instruction
    if instruction == 0xca:
        x -= 1
        SETFLAGS(x)


    """
    case 0x88:
    y--;
    SETFLAGS(y);
    break;
    """
    # DEY instruction
    if instruction == 0x88:
        y -= 1
        SETFLAGS(y)


    """
    case 0x49:
    EOR(IMMEDIATE());
    pc++;
    break;

    case 0x45:
    EOR(MEM(ZEROPAGE()));
    pc++;
    break;

    case 0x55:
    EOR(MEM(ZEROPAGEX()));
    pc++;
    break;

    case 0x4d:
    EOR(MEM(ABSOLUTE()));
    pc += 2;
    break;

    case 0x5d:
    cpucycles += EVALPAGECROSSING_ABSOLUTEX();
    EOR(MEM(ABSOLUTEX()));
    pc += 2;
    break;

    case 0x59:
    cpucycles += EVALPAGECROSSING_ABSOLUTEY();
    EOR(MEM(ABSOLUTEY()));
    pc += 2;
    break;

    case 0x41:
    EOR(MEM(INDIRECTX()));
    pc++;
    break;

    case 0x51:
    cpucycles += EVALPAGECROSSING_INDIRECTY();
    EOR(MEM(INDIRECTY()));
    pc++;
    break;
    """
    # EOR instructions
    if instruction == 0x49:
        EOR(IMMEDIATE())
        pc += 1

    elif instruction == 0x45:
        EOR(MEM(ZEROPAGE()))
        pc += 1

    elif instruction == 0x55:
        EOR(MEM(ZEROPAGEX()))
        pc += 1

    elif instruction == 0x4d:
        EOR(MEM(ABSOLUTE()))
        pc += 2

    elif instruction == 0x5d:
        cpucycles += EVALPAGECROSSING_ABSOLUTEX()
        EOR(MEM(ABSOLUTEX()))
        pc += 2

    elif instruction == 0x59:
        cpucycles += EVALPAGECROSSING_ABSOLUTEY()
        EOR(MEM(ABSOLUTEY()))
        pc += 2

    elif instruction == 0x41:
        EOR(MEM(INDIRECTX()))
        pc += 1

    elif instruction == 0x51:
        cpucycles += EVALPAGECROSSING_INDIRECTY()
        EOR(MEM(INDIRECTY()))
        pc += 1


    """
    case 0xe6:
    INC(MEM(ZEROPAGE()));
    WRITE(ZEROPAGE());
    pc++;
    break;

    case 0xf6:
    INC(MEM(ZEROPAGEX()));
    WRITE(ZEROPAGEX());
    pc++;
    break;

    case 0xee:
    INC(MEM(ABSOLUTE()));
    WRITE(ABSOLUTE());
    pc += 2;
    break;

    case 0xfe:
    INC(MEM(ABSOLUTEX()));
    WRITE(ABSOLUTEX());
    pc += 2;
    break;
    """
    # INC instructions
    if instruction == 0xe6:
        INC(MEM(ZEROPAGE()))
        WRITE(ZEROPAGE())
        pc += 1

    elif instruction == 0xf6:
        INC(MEM(ZEROPAGEX()))
        WRITE(ZEROPAGEX())
        pc += 1

    elif instruction == 0xee:
        INC(MEM(ABSOLUTE()))
        WRITE(ABSOLUTE())
        pc += 2

    elif instruction == 0xfe:
        INC(MEM(ABSOLUTEX()))
        WRITE(ABSOLUTEX())
        pc += 2


    """
    case 0xe8:
    x++;
    SETFLAGS(x);
    break;
    """
    # INX instruction
    if instruction == 0xe8:
        x += 1
        SETFLAGS(x)


    """
    case 0xc8:
    y++;
    SETFLAGS(y);
    break;
    """
    # INY instruction
    if instruction == 0xc8:
        y += 1
        SETFLAGS(y)


    """
    case 0x20:
    PUSH((pc+1) >> 8);
    PUSH((pc+1) & 0xff);
    pc = ABSOLUTE();
    break;
    """
    # JSR instruction
    if instruction == 0x20:
        PUSH((pc+1) >> 8)
        PUSH((pc+1) & 0xff)
        pc = ABSOLUTE()


    """
    case 0x4c:
    pc = ABSOLUTE();
    break;

    case 0x6c:
    {
      unsigned short adr = ABSOLUTE();
      pc = (MEM(adr) | (MEM(((adr + 1) & 0xff) | (adr & 0xff00)) << 8));
    }
    break;
    """
    # JMP instructions
    if instruction == 0x4c:
       pc = ABSOLUTE()

    elif instruction == 0x6c:
        temp = ABSOLUTE()
        # Yup, indirect JMP is bug compatible
        pc = (MEM(temp) | (MEM(((temp + 1) & 0xff) | (temp & 0xff00)) << 8))


    """
    case 0xa9:
    ASSIGNSETFLAGS(a, IMMEDIATE());
    pc++;
    break;

    case 0xa5:
    ASSIGNSETFLAGS(a, MEM(ZEROPAGE()));
    pc++;
    break;

    case 0xb5:
    ASSIGNSETFLAGS(a, MEM(ZEROPAGEX()));
    pc++;
    break;

    case 0xad:
    ASSIGNSETFLAGS(a, MEM(ABSOLUTE()));
    pc += 2;
    break;

    case 0xbd:
    cpucycles += EVALPAGECROSSING_ABSOLUTEX();
    ASSIGNSETFLAGS(a, MEM(ABSOLUTEX()));
    pc += 2;
    break;

    case 0xb9:
    cpucycles += EVALPAGECROSSING_ABSOLUTEY();
    ASSIGNSETFLAGS(a, MEM(ABSOLUTEY()));
    pc += 2;
    break;

    case 0xa1:
    ASSIGNSETFLAGS(a, MEM(INDIRECTX()));
    pc++;
    break;

    case 0xb1:
    cpucycles += EVALPAGECROSSING_INDIRECTY();
    ASSIGNSETFLAGS(a, MEM(INDIRECTY()));
    pc++;
    break;
    """
    # LDA instructions
    if instruction == 0xa9:
        ASSIGNSETFLAGS(a, IMMEDIATE())
        pc += 1

    elif instruction == 0xa5:
        ASSIGNSETFLAGS(a, MEM(ZEROPAGE()))
        pc += 1

    elif instruction == 0xb5:
        ASSIGNSETFLAGS(a, MEM(ZEROPAGEX()))
        pc += 1

    elif instruction == 0xad:
        ASSIGNSETFLAGS(a, MEM(ABSOLUTE()))
        pc += 2

    elif instruction == 0xbd:
        cpucycles += EVALPAGECROSSING_ABSOLUTEX()
        ASSIGNSETFLAGS(a, MEM(ABSOLUTEX()))
        pc += 2

    elif instruction == 0xb9:
        cpucycles += EVALPAGECROSSING_ABSOLUTEY()
        ASSIGNSETFLAGS(a, MEM(ABSOLUTEY()))
        pc += 2

    elif instruction == 0xa1:
        ASSIGNSETFLAGS(a, MEM(INDIRECTX()))
        pc += 1

    elif instruction == 0xb1:
        cpucycles += EVALPAGECROSSING_INDIRECTY()
        ASSIGNSETFLAGS(a, MEM(INDIRECTY()))
        pc += 1


    """
    case 0xa2:
    ASSIGNSETFLAGS(x, IMMEDIATE());
    pc++;
    break;

    case 0xa6:
    ASSIGNSETFLAGS(x, MEM(ZEROPAGE()));
    pc++;
    break;

    case 0xb6:
    ASSIGNSETFLAGS(x, MEM(ZEROPAGEY()));
    pc++;
    break;

    case 0xae:
    ASSIGNSETFLAGS(x, MEM(ABSOLUTE()));
    pc += 2;
    break;

    case 0xbe:
    cpucycles += EVALPAGECROSSING_ABSOLUTEY();
    ASSIGNSETFLAGS(x, MEM(ABSOLUTEY()));
    pc += 2;
    break;
    """
    # LDX instructions
    if instruction == 0xa2:
        ASSIGNSETFLAGS(x, IMMEDIATE())
        pc += 1

    elif instruction == 0xa6:
        ASSIGNSETFLAGS(x, MEM(ZEROPAGE()))
        pc += 1

    elif instruction == 0xb6:
        ASSIGNSETFLAGS(x, MEM(ZEROPAGEY()))
        pc += 1

    elif instruction == 0xae:
        ASSIGNSETFLAGS(x, MEM(ABSOLUTE()))
        pc += 2

    elif instruction == 0xbe:
        cpucycles += EVALPAGECROSSING_ABSOLUTEY()
        ASSIGNSETFLAGS(x, MEM(ABSOLUTEY()))
        pc += 2


    """
    case 0xa0:
    ASSIGNSETFLAGS(y, IMMEDIATE());
    pc++;
    break;

    case 0xa4:
    ASSIGNSETFLAGS(y, MEM(ZEROPAGE()));
    pc++;
    break;

    case 0xb4:
    ASSIGNSETFLAGS(y, MEM(ZEROPAGEX()));
    pc++;
    break;

    case 0xac:
    ASSIGNSETFLAGS(y, MEM(ABSOLUTE()));
    pc += 2;
    break;

    case 0xbc:
    cpucycles += EVALPAGECROSSING_ABSOLUTEX();
    ASSIGNSETFLAGS(y, MEM(ABSOLUTEX()));
    pc += 2;
    break;
    """
    # LDY instructions
    if instruction == 0xa0:
        ASSIGNSETFLAGS(y, IMMEDIATE())
        pc += 1

    elif instruction == 0xa4:
        ASSIGNSETFLAGS(y, MEM(ZEROPAGE()))
        pc += 1

    elif instruction == 0xb4:
        ASSIGNSETFLAGS(y, MEM(ZEROPAGEX()))
        pc += 1

    elif instruction == 0xac:
        ASSIGNSETFLAGS(y, MEM(ABSOLUTE()))
        pc += 2

    elif instruction == 0xbc:
        cpucycles += EVALPAGECROSSING_ABSOLUTEX()
        ASSIGNSETFLAGS(y, MEM(ABSOLUTEX()))
        pc += 2


    """
    case 0x4a:
    LSR(a);
    break;

    case 0x46:
    LSR(MEM(ZEROPAGE()));
    WRITE(ZEROPAGE());
    pc++;
    break;

    case 0x56:
    LSR(MEM(ZEROPAGEX()));
    WRITE(ZEROPAGEX());
    pc++;
    break;

    case 0x4e:
    LSR(MEM(ABSOLUTE()));
    WRITE(ABSOLUTE());
    pc += 2;
    break;

    case 0x5e:
    LSR(MEM(ABSOLUTEX()));
    WRITE(ABSOLUTEX());
    pc += 2;
    break;
    """
    # LSR instructions
    if instruction == 0x4a:
        LSR(a)

    elif instruction == 0x46:
        LSR(MEM(ZEROPAGE()))
        WRITE(ZEROPAGE())
        pc += 1

    elif instruction == 0x56:
        LSR(MEM(ZEROPAGEX()))
        WRITE(ZEROPAGEX())
        pc += 1

    elif instruction == 0x4e:
        LSR(MEM(ABSOLUTE()))
        WRITE(ABSOLUTE())
        pc += 2

    elif instruction == 0x5e:
        LSR(MEM(ABSOLUTEX()))
        WRITE(ABSOLUTEX())
        pc += 2


    """
    case 0xea:
    break;
    """
    # NOP instruction
    if instruction == 0xea:
        pass


    """
    case 0x09:
    ORA(IMMEDIATE());
    pc++;
    break;

    case 0x05:
    ORA(MEM(ZEROPAGE()));
    pc++;
    break;

    case 0x15:
    ORA(MEM(ZEROPAGEX()));
    pc++;
    break;

    case 0x0d:
    ORA(MEM(ABSOLUTE()));
    pc += 2;
    break;

    case 0x1d:
    cpucycles += EVALPAGECROSSING_ABSOLUTEX();
    ORA(MEM(ABSOLUTEX()));
    pc += 2;
    break;

    case 0x19:
    cpucycles += EVALPAGECROSSING_ABSOLUTEY();
    ORA(MEM(ABSOLUTEY()));
    pc += 2;
    break;

    case 0x01:
    ORA(MEM(INDIRECTX()));
    pc++;
    break;

    case 0x11:
    cpucycles += EVALPAGECROSSING_INDIRECTY();
    ORA(MEM(INDIRECTY()));
    pc++;
    break;
    """
    # ORA instructions
    if instruction == 0x09:
        ORA(IMMEDIATE())
        pc += 1

    elif instruction == 0x05:
        ORA(MEM(ZEROPAGE()))
        pc += 1

    elif instruction == 0x15:
        ORA(MEM(ZEROPAGEX()))
        pc += 1

    elif instruction == 0x0d:
        ORA(MEM(ABSOLUTE()))
        pc += 2

    elif instruction == 0x1d:
        cpucycles += EVALPAGECROSSING_ABSOLUTEX()
        ORA(MEM(ABSOLUTEX()))
        pc += 2

    elif instruction == 0x19:
        cpucycles += EVALPAGECROSSING_ABSOLUTEY()
        ORA(MEM(ABSOLUTEY()))
        pc += 2

    elif instruction == 0x01:
        ORA(MEM(INDIRECTX()))
        pc += 1

    elif instruction == 0x11:
        cpucycles += EVALPAGECROSSING_INDIRECTY()
        ORA(MEM(INDIRECTY()))
        pc += 1


    """
    case 0x48:
    PUSH(a);
    break;
    """
    # PHA instruction
    if instruction == 0x48:
        PUSH(a)


    """
    case == 0x08:
    PUSH(flags);
    break;
    """
    # PHP instruction
    # TODO: Pretendo says PHP always pushes B flag as 1...
    if instruction == 0x08:
        PUSH(flags)


    """
    case 0x68:
    ASSIGNSETFLAGS(a, POP());
    break;
    """
    # PLA instruction
    if instruction == 0x68:
        ASSIGNSETFLAGS(a, POP())


    """    
    case 0x28:
    flags = POP();
    break;
    """
    # PLP instruction
    if instruction == 0x28:
        flags = POP()


    """
    case 0x2a:
    ROL(a);
    break;

    case 0x26:
    ROL(MEM(ZEROPAGE()));
    WRITE(ZEROPAGE());
    pc++;
    break;

    case 0x36:
    ROL(MEM(ZEROPAGEX()));
    WRITE(ZEROPAGEX());
    pc++;
    break;

    case 0x2e:
    ROL(MEM(ABSOLUTE()));
    WRITE(ABSOLUTE());
    pc += 2;
    break;

    case 0x3e:
    ROL(MEM(ABSOLUTEX()));
    WRITE(ABSOLUTEX());
    pc += 2;
    break;
    """
    # ROL instructions
    if instruction == 0x2a:
        ROL(a)

    elif instruction == 0x26:
        ROL(MEM(ZEROPAGE()))
        WRITE(ZEROPAGE())
        pc += 1

    elif instruction == 0x36:
        ROL(MEM(ZEROPAGEX()))
        WRITE(ZEROPAGEX())
        pc += 1

    elif instruction == 0x2e:
        ROL(MEM(ABSOLUTE()))
        WRITE(ABSOLUTE())
        pc += 2

    elif instruction == 0x3e:
        ROL(MEM(ABSOLUTEX()))
        WRITE(ABSOLUTEX())
        pc += 2


    """
    case 0x6a:
    ROR(a);
    break;

    case 0x66:
    ROR(MEM(ZEROPAGE()));
    WRITE(ZEROPAGE());
    pc++;
    break;

    case 0x76:
    ROR(MEM(ZEROPAGEX()));
    WRITE(ZEROPAGEX());
    pc++;
    break;

    case 0x6e:
    ROR(MEM(ABSOLUTE()));
    WRITE(ABSOLUTE());
    pc += 2;
    break;

    case 0x7e:
    ROR(MEM(ABSOLUTEX()));
    WRITE(ABSOLUTEX());
    pc += 2;
    break;
    """
    # ROR instructions
    if instruction == 0x6a:
        ROR(a)

    elif instruction == 0x66:
        ROR(MEM(ZEROPAGE()))
        WRITE(ZEROPAGE())
        pc += 1

    elif instruction == 0x76:
        ROR(MEM(ZEROPAGEX()))
        WRITE(ZEROPAGEX())
        pc += 1

    elif instruction == 0x6e:
        ROR(MEM(ABSOLUTE()))
        WRITE(ABSOLUTE())
        pc += 2

    elif instruction == 0x7e:
        ROR(MEM(ABSOLUTEX()))
        WRITE(ABSOLUTEX())
        pc += 2


    """
    case 0x40:
    if (sp == 0xff) return 0;
    flags = POP();
    pc = POP();
    pc |= POP() << 8;
    break;
    """
    # RTI instruction
    if instruction == 0x40:
        if sp == 0xff:
            return 0
        flags = POP()
        pc = POP()
        pc |= POP() << 8


    """
    case 0x60:
    if (sp == 0xff) return 0;
    pc = POP();
    pc |= POP() << 8;
    pc++;
    break;
    """
    # RTS instruction
    if instruction == 0x60:
        if sp == 0xff:
            return 0
        pc = POP()
        pc |= POP() << 8
        pc += 1


    """
    case 0xe9:
    SBC(IMMEDIATE());
    pc++;
    break;

    case 0xe5:
    SBC(MEM(ZEROPAGE()));
    pc++;
    break;

    case 0xf5:
    SBC(MEM(ZEROPAGEX()));
    pc++;
    break;

    case 0xed:
    SBC(MEM(ABSOLUTE()));
    pc += 2;
    break;

    case 0xfd:
    cpucycles += EVALPAGECROSSING_ABSOLUTEX();
    SBC(MEM(ABSOLUTEX()));
    pc += 2;
    break;

    case 0xf9:
    cpucycles += EVALPAGECROSSING_ABSOLUTEY();
    SBC(MEM(ABSOLUTEY()));
    pc += 2;
    break;

    case 0xe1:
    SBC(MEM(INDIRECTX()));
    pc++;
    break;

    case 0xf1:
    cpucycles += EVALPAGECROSSING_INDIRECTY();
    SBC(MEM(INDIRECTY()));
    pc++;
    break;
    """
    # SBC instructions
    if instruction == 0xe9:
        SBC(IMMEDIATE())
        pc += 1

    elif instruction == 0xe5:
        SBC(MEM(ZEROPAGE()))
        pc += 1

    elif instruction == 0xf5:
        SBC(MEM(ZEROPAGEX()))
        pc += 1

    elif instruction == 0xed:
        SBC(MEM(ABSOLUTE()))
        pc += 2

    elif instruction == 0xfd:
        cpucycles += EVALPAGECROSSING_ABSOLUTEX()
        SBC(MEM(ABSOLUTEX()))
        pc += 2

    elif instruction == 0xf9:
        cpucycles += EVALPAGECROSSING_ABSOLUTEY()
        SBC(MEM(ABSOLUTEY()))
        pc += 2

    elif instruction == 0xe1:
        SBC(MEM(INDIRECTX()))
        pc += 1

    elif instruction == 0xf1:
        cpucycles += EVALPAGECROSSING_INDIRECTY()
        SBC(MEM(INDIRECTY()))
        pc += 1


    """
    case 0x38:
    flags |= FC;
    break;
    """
    # SEC instruction
    if instruction == 0x38:
        flags |= FC


    """
    case 0xf8:
    flags |= FD;
    break;
    """
    # SED instruction
    if instruction == 0xf8:
       flags |= FD


    """
    case 0x78:
    flags |= FI;
    break;
    """
    # SEI instruction
    if instruction == 0x78:
        flags |= FI


    """
    case 0x85:
    MEM(ZEROPAGE()) = a;
    WRITE(ZEROPAGE());
    pc++;
    break;

    case 0x95:
    MEM(ZEROPAGEX()) = a;
    WRITE(ZEROPAGEX());
    pc++;
    break;

    case 0x8d:
    MEM(ABSOLUTE()) = a;
    WRITE(ABSOLUTE());
    pc += 2;
    break;

    case 0x9d:
    MEM(ABSOLUTEX()) = a;
    WRITE(ABSOLUTEX());
    pc += 2;
    break;

    case 0x99:
    MEM(ABSOLUTEY()) = a;
    WRITE(ABSOLUTEY());
    pc += 2;
    break;

    case 0x81:
    MEM(INDIRECTX()) = a;
    WRITE(INDIRECTX());
    pc++;
    break;

    case 0x91:
    MEM(INDIRECTY()) = a;
    WRITE(INDIRECTY());
    pc++;
    break;
    """
    # STA instructions
    if instruction == 0x85:
        MEM(ZEROPAGE()) = a
        WRITE(ZEROPAGE())
        pc += 1

    elif instruction == 0x95:
        MEM(ZEROPAGEX()) = a
        WRITE(ZEROPAGEX())
        pc += 1

    elif instruction == 0x8d:
        MEM(ABSOLUTE()) = a
        WRITE(ABSOLUTE())
        pc += 2

    elif instruction == 0x9d:
        MEM(ABSOLUTEX()) = a
        WRITE(ABSOLUTEX())
        pc += 2

    elif instruction == 0x99:
        MEM(ABSOLUTEY()) = a
        WRITE(ABSOLUTEY())
        pc += 2

    elif instruction == 0x81:
        MEM(INDIRECTX()) = a
        WRITE(INDIRECTX())
        pc += 1

    elif instruction == 0x91:
        MEM(INDIRECTY()) = a
        WRITE(INDIRECTY())
        pc += 1


    """
    case 0x86:
    MEM(ZEROPAGE()) = x;
    WRITE(ZEROPAGE());
    pc++;
    break;

    case 0x96:
    MEM(ZEROPAGEY()) = x;
    WRITE(ZEROPAGEY());
    pc++;
    break;

    case 0x8e:
    MEM(ABSOLUTE()) = x;
    WRITE(ABSOLUTE());
    pc += 2;
    break;
    """
    # STX instructions
    if instruction == 0x86:
        MEM(ZEROPAGE()) = x
        WRITE(ZEROPAGE())
        pc += 1

    elif instruction == 0x96:
        MEM(ZEROPAGEY()) = x
        WRITE(ZEROPAGEY())
        pc += 1

    elif instruction == 0x8e:
        MEM(ABSOLUTE()) = x
        WRITE(ABSOLUTE())
        pc += 2


    """
    case 0x84:
    MEM(ZEROPAGE()) = y;
    WRITE(ZEROPAGE());
    pc++;
    break;

    case 0x94:
    MEM(ZEROPAGEX()) = y;
    WRITE(ZEROPAGEX());
    pc++;
    break;

    case 0x8c:
    MEM(ABSOLUTE()) = y;
    WRITE(ABSOLUTE());
    pc += 2;
    break;
    """
    # STY instructions
    if instruction == 0x84:
        MEM(ZEROPAGE()) = y
        WRITE(ZEROPAGE())
        pc += 1

    elif instruction == 0x94:
        MEM(ZEROPAGEX()) = y
        WRITE(ZEROPAGEX())
        pc += 1

    elif instruction == 0x8c:
        MEM(ABSOLUTE()) = y
        WRITE(ABSOLUTE())
        pc += 2


    """
    case 0xaa:
    ASSIGNSETFLAGS(x, a);
    break;
    """
    # TAX instruction
    if instruction == 0xaa:
        ASSIGNSETFLAGS(x, a)


    """
    case 0xba:
    ASSIGNSETFLAGS(x, sp);
    break;
    """
    # TSX instruction
    if instruction == 0xba:
        ASSIGNSETFLAGS(x, sp)


    """
    case 0x8a:
    ASSIGNSETFLAGS(a, x);
    break;
    """
    # TXA instruction
    if instruction == 0x8a:
        ASSIGNSETFLAGS(a, x)


    """
    case 0x9a:
    ASSIGNSETFLAGS(sp, x);
    break;
    """
    # TXS instruction
    if instruction == 0x9a:
       ASSIGNSETFLAGS(sp, x)


    """
    case 0x98:
    ASSIGNSETFLAGS(a, y);
    break;
    """
    # TYA instruction
    if instruction == 0x98:
       ASSIGNSETFLAGS(a, y)


    """
    case 0xa8:
    ASSIGNSETFLAGS(y, a);
    break;
    """
    # TAY instruction
    if instruction == 0xa8:
        ASSIGNSETFLAGS(y, a)


    """
    # TODO: Should set interrupt flag, push PC+2, push flags (like PHP does)
    case 0x00:
    return 0;
    """
    # BRK instruction
    # TODO: Should set interrupt flag, push PC+2, push flags (like PHP does)
    if instruction == 0x00:
        return 0


    """  
    case 0xa7:
    ASSIGNSETFLAGS(a, MEM(ZEROPAGE()));
    x = a;
    pc++;
    break;

    case 0xb7:
    ASSIGNSETFLAGS(a, MEM(ZEROPAGEY()));
    x = a;
    pc++;
    break;

    case 0xaf:
    ASSIGNSETFLAGS(a, MEM(ABSOLUTE()));
    x = a;
    pc += 2;
    break;

    case 0xa3:
    ASSIGNSETFLAGS(a, MEM(INDIRECTX()));
    x = a;
    pc++;
    break;

    case 0xb3:
    cpucycles += EVALPAGECROSSING_INDIRECTY();
    ASSIGNSETFLAGS(a, MEM(INDIRECTY()));
    x = a;
    pc++;
    break;
    """
    # "LAX" pseudo-ops
    if instruction == 0xa7:
        ASSIGNSETFLAGS(a, MEM(ZEROPAGE()))
        x = a
        pc += 1

    elif instruction == 0xb7:
        ASSIGNSETFLAGS(a, MEM(ZEROPAGEY()))
        x = a
        pc += 1

    elif instruction == 0xaf:
        ASSIGNSETFLAGS(a, MEM(ABSOLUTE()))
        x = a
        pc += 2

    elif instruction == 0xa3:
        ASSIGNSETFLAGS(a, MEM(INDIRECTX()))
        x = a
        pc += 1

    elif instruction == 0xb3:
        cpucycles += EVALPAGECROSSING_INDIRECTY()
        ASSIGNSETFLAGS(a, MEM(INDIRECTY()))
        x = a
        pc += 1


    """
    # NOP size 1, 2 cycle
    case 0x1a:
    case 0x3a:
    case 0x5a:
    case 0x7a:
    case 0xda:
    case 0xfa:
    break;
    
    # NOP size 2, 2 cycle
    case 0x80:
    case 0x82:
    case 0x89:
    case 0xc2:
    case 0xe2:

    # NOP size 2, 3 cycle
    case 0x04:
    case 0x44:
    case 0x64:

    # NOP size 2, 4 cycle
    case 0x14:
    case 0x34:
    case 0x54:
    case 0x74:
    case 0xd4:
    case 0xf4:
    pc++;
    break;
    
    # NOP size TODO, 4 cycle
    case 0x0c:

    # NOP size TODO, 4(+1) cycle
    case 0x1c:
    case 0x3c:
    case 0x5c:
    case 0x7c:
    case 0xdc:
    case 0xfc:
    cpucycles += EVALPAGECROSSING_ABSOLUTEX();
    pc += 2;
    break;
    """
    # NOP pseudo-ops:
    # NOP size 1, 2 cycle
    case 0x1a:
    case 0x3a:
    case 0x5a:
    case 0x7a:
    case 0xda:
    case 0xfa:
    break;
    
    # NOP size 2, 2 cycle
    case 0x80:
    case 0x82:
    case 0x89:
    case 0xc2:
    case 0xe2:

    # NOP size 2, 3 cycle
    case 0x04:
    case 0x44:
    case 0x64:

    # NOP size 2, 4 cycle
    case 0x14:
    case 0x34:
    case 0x54:
    case 0x74:
    case 0xd4:
    case 0xf4:
    pc += 1;
    break;
    
    # NOP size TODO, 4 cycle
    case 0x0c:

    # NOP size TODO, 4(+1) cycle
    case 0x1c:
    case 0x3c:
    case 0x5c:
    case 0x7c:
    case 0xdc:
    case 0xfc:
    cpucycles += EVALPAGECROSSING_ABSOLUTEX();
    pc += 2;
    break;


    """
    case 0x02:
    # also 0x12, 0x22, 0x32, 0x42, 0x52, 0x62, 0x72, 0x92, 0xb2, 0xd2, 0xf2
    printf("Error: CPU halt at %04X\n", pc-1);
    exit(1);
    break;
    """
    # JAM pseudo-ops
    case 0x02:
    # also 0x12, 0x22, 0x32, 0x42, 0x52, 0x62, 0x72, 0x92, 0xb2, 0xd2, 0xf2
    printf("Error: CPU halt at %04X\n", pc-1);
    exit(1);
    break;


    """         
    default:
    printf("Error: Unknown opcode $%02X at $%04X\n", op, pc-1);
    exit(1);
    break;
    """
  }
  return 1;
}

# Note: got rid of this:
void setpc(unsigned short newpc)
{
  pc = newpc;
}

"""

# debugging main
if __name__ == "__main__":
    ASSIGNSETFLAGS(OperandRef(A_REG), OperandRef(BYTE_VAL, 17))
    CMP(OperandRef(A_REG), OperandRef(BYTE_VAL, 17))
