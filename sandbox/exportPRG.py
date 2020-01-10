# Convert an ascii basic program into a Commodore PRG file
#
# Does not implement a grammar for BASIC, so no grammar checking, but will generate a valid PRG
# for a valid ascii BASIC program
#
# TODO?: Probably don't want to implement a syntax for control characters (e.g. {CYN})
#    https://www.c64-wiki.com/wiki/control_character
#    Currently, one must simply use the petscii byte with the correct control code value

"""
Some notes on Commodore BASIC:
- Spaces are not required (and usually avoided to save memory).  Spaces are not stored between line numbers
  and code, but a space will be shown there when LISTed on a Commodore.
- If not using command abbreviations, basic lines on c64 can be up to 80 characters, 88 on vic-20,
  and 160 on C128
- Variable names can be long, but only first two characters are significant
- Lines numbers can range from 0 to 65520
"""

import sys
from bytesUtil import little_endian_bytes, hexdump

basic_start_c64  = 2049 # $0801
basic_start_c128 = 7169 # $1C01

rem_len = len('rem')

"""
I created these token dictionaries based on this:
    https://portcommodore.com/dokuwiki/lib/exe/fetch.php?media=larry:comp:commodore:cbmmultichart.pdf

The basic token for pi is 255.  Petscii characters 126, 222, and 255 all seem to print out as pi.
In VICE, control-shift tilda types a pi symbol which, if put in an ASC statement, yields 255.

When I ran this c64 program:
10 print{pi}:rem{pi}
20 fort=0to9:printpeek(t+2049);:next:rem 2049 start of basic program
it prints
 3.14159265
 11  8  10  0  153  255  58  143  255 0
So the tokenized pi and the untokenized pi (in the REM) are both petscii 255
Therefore, the pi token doesn't need to appear in the dictionary
"""

c64_tokens = {
    b'end': b'\x80', b'for': b'\x81', b'next': b'\x82', b'data': b'\x83', b'input#': b'\x84',
    b'input': b'\x85', b'dim': b'\x86', b'read': b'\x87', b'let': b'\x88', b'goto': b'\x89',
    b'run': b'\x8a', b'if': b'\x8b', b'restore': b'\x8c', b'gosub': b'\x8d', b'return': b'\x8e',
    b'rem': b'\x8f', b'stop': b'\x90', b'on': b'\x91', b'wait': b'\x92', b'load': b'\x93',
    b'save': b'\x94', b'verify': b'\x95', b'def': b'\x96', b'poke': b'\x97', b'print#': b'\x98',
    b'print': b'\x99', b'cont': b'\x9a', b'list': b'\x9b', b'clr': b'\x9c', b'cmd': b'\x9d',
    b'sys': b'\x9e', b'open': b'\x9f', b'close': b'\xa0', b'get': b'\xa1', b'new': b'\xa2',
    b'tab(': b'\xa3', b'to': b'\xa4', b'fn': b'\xa5', b'spc(': b'\xa6', b'then': b'\xa7',
    b'not': b'\xa8', b'step': b'\xa9', b'+': b'\xaa', b'-': b'\xab', b'*': b'\xac', b'/': b'\xad',
    b'^': b'\xae', b'and': b'\xaf', b'or': b'\xb0', b'>': b'\xb1', b'=': b'\xb2', b'<': b'\xb3',
    b'sgn': b'\xb4', b'int': b'\xb5', b'abs': b'\xb6', b'usr': b'\xb7', b'fre': b'\xb8',
    b'pos': b'\xb9', b'sqr': b'\xba', b'rnd': b'\xbb', b'log': b'\xbc', b'exp': b'\xbd',
    b'cos': b'\xbe', b'sin': b'\xbf', b'tan': b'\xc0', b'atn': b'\xc1', b'peek': b'\xc2',
    b'len': b'\xc3', b'str$': b'\xc4', b'val': b'\xc5', b'asc': b'\xc6', b'chr$': b'\xc7',
    b'left$': b'\xc8', b'right$': b'\xc9', b'mid$': b'\xca', b'go': b'\xcb'}

c128_additional_tokens = {
    b'rgr': b'\xcc', b'rclr': b'\xcd', b'pot': b'\xce\x02', b'bump': b'\xce\x03', b'pen': b'\xce\x04',
    b'rsppos': b'\xce\x05', b'resrite': b'\xce\x06', b'rspcolor': b'\xce\x07', b'xor': b'\xce\x08',
    b'rwindow': b'\xce\t', b'pointer': b'\xce\n', b'joy': b'\xcf', b'rdot': b'\xd0',
    b'dec': b'\xd1', b'hex$': b'\xd2', b'err$': b'\xd3', b'instr': b'\xd4', b'else': b'\xd5',
    b'resume': b'\xd6', b'trap': b'\xd7', b'tron': b'\xd8', b'troff': b'\xd9', b'sound': b'\xda',
    b'vol': b'\xdb', b'auto': b'\xdc', b'pudef': b'\xdd', b'graphic': b'\xde', b'paint': b'\xdf',
    b'char': b'\xe0', b'box': b'\xe1', b'circle': b'\xe2', b'sshape': b'\xe4', b'draw': b'\xe5',
    b'locate': b'\xe6', b'color': b'\xe7', b'scnclr': b'\xe8', b'scale': b'\xe9', b'help': b'\xea',
    b'do': b'\xeb', b'loop': b'\xec', b'exit': b'\xed', b'directory': b'\xee', b'dsave': b'\xef',
    b'dload': b'\xf0', b'header': b'\xf1', b'scratch': b'\xf2', b'collect': b'\xf3',
    b'copy': b'\xf4', b'rename': b'\xf5', b'backup': b'\xf6', b'delete': b'\xf7', b'renumber': b'\xf8',
    b'key': b'\xf9', b'monitor': b'\xfa', b'using': b'\xfb', b'until': b'\xfc', b'while': b'\xfd',
    b'bank': b'\xfe\x02', b'filter': b'\xfe\x03', b'play': b'\xfe\x04', b'tempo': b'\xfe\x05',
    b'movspr': b'\xfe\x06', b'sprite': b'\xfe\x07', b'sprcolor': b'\xfe\x08', b'rreg': b'\xfe\t',
    b'envelope': b'\xfe\n', b'sleep': b'\xfe\x0b', b'catalog': b'\xfe\x0c', b'dopen': b'\xfe\r',
    b'append': b'\xfe\x0e', b'dclose': b'\xfe\x0f', b'bsave': b'\xfe\x10', b'bload': b'\xfe\x11',
    b'record': b'\xfe\x12', b'concat': b'\xfe\x13', b'dverify': b'\xfe\x14', b'dclear': b'\xfe\x15',
    b'sprsav': b'\xfe\x16', b'collision': b'\xfe\x17', b'begin': b'\xfe\x18', b'bend': b'\xfe\x19',
    b'window': b'\xfe\x1a', b'boot': b'\xfe\x1b', b'width': b'\xfe\x1c', b'sprdef': b'\xfe\x1d',
    b'quit': b'\xfe\x1e', b'stash': b'\xfe\x1f', b'fetch': b'\xfe!', b'swap': b'\xfe#',
    b'off': b'\xfe$', b'fast': b'\xfe%', b'slow': b'\xfe&'}

c128_tokens = {**c64_tokens, **c128_additional_tokens}


def ascii_to_petscii(ascii_bytes):
    result = []
    for a_byte in ascii_bytes:
        result.append(ab2pb(a_byte))
    return bytes(result)


# Convert an ascii char to a petscii char
#
# This treates lowercase letters as "unshifted", which means that, by default, lowercase
# letters display as uppercase on the c64.  So this method simply swaps the cases around.
#
# No BASIC tokens are harmed in this conversion (tokens live at 0 and between 128 and 255)
def ab2pb(ascii_byte):
    if ascii_byte >= ord('a') and ascii_byte <= ord('z'):
        return ascii_byte - 32

    if ascii_byte >= ord('A') and ascii_byte <= ord('Z'):
        return ascii_byte + 32    

    # The rest are either correct (such as printable symbols <= ordinal 64, and a few above that, like
    # '[', ']', and '^' (which turns into an up arrow)).  In many cases, there's no equivalent value to
    # translate to (without using unicode, as https://pypi.org/project/cbmcodecs/ does), so the chars
    # are just passed through unchanged.
    return ascii_byte


# Find first REM not inside quotes (anything after that is comment, and not tokenized)
# (Note: REM neuters quotes, and quotes neuters REM)
def find_1st_rem_outside_quotes(line):
    in_quotes = False
    for i in range(len(line)-rem_len):
        if line[i] == '"':
            in_quotes = not in_quotes
        if in_quotes:
            continue
        if line[i:i+rem_len] == 'rem':
            return i
    return -1 # no rem outside of quotes


def ascii_to_prg(ascii_prg, start_of_basic, basic_tokens):
    mem_pointer = start_of_basic

    # prg file load addr, gets stripped off during load
    tokenized_lines = bytearray(little_endian_bytes(mem_pointer)) 
    
    lines = ascii_prg.strip().split("\n")
    for line in lines:
        tokenized_line = bytearray()

        # strip off the line number
        (line_num, line) = line.split(" ", 1) # lazy coding assumes a space delimiter in the ascii BASIC
        line_num = int(line_num)
        line = line.lstrip()

        # Anything to the right of a REM doesn't get tokenized
        rem_split_loc = find_1st_rem_outside_quotes(line)
        if rem_split_loc != -1:
            remBytes = ascii_to_petscii(bytearray(line[rem_split_loc+rem_len:], 'latin-1'))
            line = line[:rem_split_loc+rem_len]
        else:
            remBytes = b''

        # divide up line into parts that do and don't get tokenized
        for i, part in enumerate(line.split('"')):
            part = bytearray(part + '"', 'latin-1') # add the split char back in
            if i%2 == 0: # if outside quotes, then tokenize
                # do substitutions on longer tokens first (e.g., PRINT# before PRINT)
                for aToken in sorted(basic_tokens, key=len, reverse=True):    
                    part = part.replace(aToken, basic_tokens[aToken])
            tokenized_line += ascii_to_petscii(part)
        tokenized_line = tokenized_line[:-1] + remBytes + b'\x00'
        mem_pointer += len(tokenized_line)+4 # start of next basic line
        tokenized_lines += little_endian_bytes(mem_pointer) + little_endian_bytes(line_num) + tokenized_line
    tokenized_lines += b'\x00\x00'
    return tokenized_lines


def ascii_to_c128prg(ascii_prg):
    return ascii_to_prg(ascii_prg, basic_start_c128, c128_tokens)


def ascii_to_c64prg(ascii_prg):
    return ascii_to_prg(ascii_prg, basic_start_c64, c64_tokens)


    
	