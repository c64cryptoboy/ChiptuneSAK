import sys

# token values based on this:
#    https://portcommodore.com/dokuwiki/lib/exe/fetch.php?media=larry:comp:commodore:cbmmultichart.pdf

c64_tokens = {
    '{endOfLine}': b'\x00', 'end': b'\x80', 'for': b'\x81', 'next': b'\x82', 'data': b'\x83',
    'input#': b'\x84', 'input': b'\x85', 'dim': b'\x86', 'read': b'\x87', 'let': b'\x88',
    'goto': b'\x89', 'run': b'\x8a', 'if': b'\x8b', 'restore': b'\x8c', 'gosub': b'\x8d',
    'return': b'\x8e', 'rem': b'\x8f', 'stop': b'\x90', 'on': b'\x91', 'wait': b'\x92',
    'load': b'\x93', 'save': b'\x94', 'verify': b'\x95', 'def': b'\x96', 'poke': b'\x97',
    'print#': b'\x98', 'print': b'\x99', 'cont': b'\x9a', 'list': b'\x9b', 'clr': b'\x9c',
    'cmd': b'\x9d', 'sys': b'\x9e', 'open': b'\x9f', 'close': b'\xa0', 'get': b'\xa1',
    'new': b'\xa2', 'tab(': b'\xa3', 'to': b'\xa4', 'fn': b'\xa5', 'spc(': b'\xa6', 'then': b'\xa7',
    'not': b'\xa8', 'step': b'\xa9', '+': b'\xaa', '-': b'\xab', '*': b'\xac', '/': b'\xad',
    '^': b'\xae', 'and': b'\xaf', 'or': b'\xb0', '>': b'\xb1', '=': b'\xb2', '<': b'\xb3',
    'sgn': b'\xb4', 'int': b'\xb5', 'abs': b'\xb6', 'usr': b'\xb7', 'fre': b'\xb8', 'pos': b'\xb9',
    'sqr': b'\xba', 'rnd': b'\xbb', 'log': b'\xbc', 'exp': b'\xbd', 'cos': b'\xbe', 'sin': b'\xbf',
    'tan': b'\xc0', 'atn': b'\xc1', 'peek': b'\xc2', 'len': b'\xc3', 'str$': b'\xc4',
    'val': b'\xc5', 'asc': b'\xc6', 'chr$': b'\xc7', 'left$': b'\xc8', 'right$': b'\xc9',
    'mid$': b'\xca', 'go': b'\xcb', '{pi}': b'\xff'}

c128_additional_tokens = {
    'rgr': b'\xcc', 'rclr': b'\xcd', 'pot': b'\xce\x02', 'bump': b'\xce\x03', 'pen': b'\xce\x04',
    'rsppos': b'\xce\x05', 'resrite': b'\xce\x06', 'rspcolor': b'\xce\x07', 'xor': b'\xce\x08',
    'rwindow': b'\xce\t', 'pointer': b'\xce\n', 'joy': b'\xcf', 'rdot': b'\xd0', 'dec': b'\xd1',
    'hex$': b'\xd2', 'err$': b'\xd3', 'instr': b'\xd4', 'else': b'\xd5', 'resume': b'\xd6',
    'trap': b'\xd7', 'tron': b'\xd8', 'troff': b'\xd9', 'sound': b'\xda', 'vol': b'\xdb',
    'auto': b'\xdc', 'pudef': b'\xdd', 'graphic': b'\xde', 'paint': b'\xdf', 'char': b'\xe0',
    'box': b'\xe1', 'circle': b'\xe2', 'sshape': b'\xe4', 'draw': b'\xe5', 'locate': b'\xe6',
    'color': b'\xe7', 'scnclr': b'\xe8', 'scale': b'\xe9', 'help': b'\xea', 'do': b'\xeb',
    'loop': b'\xec', 'exit': b'\xed', 'directory': b'\xee', 'dsave': b'\xef', 'dload': b'\xf0',
    'header': b'\xf1', 'scratch': b'\xf2', 'collect': b'\xf3', 'copy': b'\xf4', 'rename': b'\xf5',
    'backup': b'\xf6', 'delete': b'\xf7', 'renumber': b'\xf8', 'key': b'\xf9', 'monitor': b'\xfa',
    'using': b'\xfb', 'until': b'\xfc', 'while': b'\xfd', 'bank': b'\xfe\x02', 'filter': b'\xfe\x03',
    'play': b'\xfe\x04', 'tempo': b'\xfe\x05', 'movspr': b'\xfe\x06', 'sprite': b'\xfe\x07',
    'sprcolor': b'\xfe\x08', 'rreg': b'\xfe\t', 'envelope': b'\xfe\n', 'sleep': b'\xfe\x0b',
    'catalog': b'\xfe\x0c', 'dopen': b'\xfe\r', 'append': b'\xfe\x0e', 'dclose': b'\xfe\x0f',
    'bsave': b'\xfe\x10', 'bload': b'\xfe\x11', 'record': b'\xfe\x12', 'concat': b'\xfe\x13',
    'dverify': b'\xfe\x14', 'dclear': b'\xfe\x15', 'sprsav': b'\xfe\x16', 'collision': b'\xfe\x17',
    'begin': b'\xfe\x18', 'bend': b'\xfe\x19', 'window': b'\xfe\x1a', 'boot': b'\xfe\x1b',
    'width': b'\xfe\x1c', 'sprdef': b'\xfe\x1d', 'quit': b'\xfe\x1e', 'stash': b'\xfe\x1f',
    'fetch': b'\xfe!', 'swap': b'\xfe#', 'off': b'\xfe$', 'fast': b'\xfe%', 'slow': b'\xfe&'}

c128_tokens = {**c64_tokens, **c128_additional_tokens}


test_prg = """10 print"test":rem blah
20 goto10"""

# Start of BASIC: C64 $0801 (2049), C128 $1C01 (7169)

# Example
# 10 print"test":rem blah
# 20 goto10

# c64 same as c128 except for starting memory location
# c64:  01 08 14 08 0A 00 99 22 54 45 53 54 22 3A 8F 20 42 4C 41 48 00 1C 08 14 00 89 31 30 00 00 00
# c128: 01 1C 14 1C 0A 00 99 22 54 45 53 54 22 3A 8F 20 42 4C 41 48 00 1C 1C 14 00 89 31 30 00 00 00

# c128 example
# Note: 1st two bytes (load addr) get stripped off
# $1C01: 14 1C                 ptr to next line prt
# $1C03: 0A 00                 line 10
# $1C05: 99                    PRINT
# $1C06: 22 54 45 53 54 22 3A  "TEST":
# $1C0D: 8F                    REM
# $1C0E: 20                    space
# $1C0F: 42 4C 41 48           BLAH
# $1C13: 00                    end of line
# $1C14: 1C 1C                 ptr to next line prt
# $1C16: 14 00                 line 20
# $1C18: 89                    GOTO
# $1C19: 31 30                 10
# $1C1B: 00                    end of line
# $1C1C: 00 00                 ptr to next line prt == 0 == prg end


# TODO: implement ascii->petscii and create designations for control characters
#    Reference: https://www.c64-wiki.com/wiki/control_character

prg = bytearray()

def main():
    pass


if __name__ == "__main__":
    main()
    
	