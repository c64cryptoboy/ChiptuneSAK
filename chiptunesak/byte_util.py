# Common byte functions


def int_to_hex(an_int):
    return "%X" % an_int


def hex_to_int(a_hex):
    if a_hex.startswith('$'):
        a_hex = a_hex[1:]
    elif a_hex.startswith('\\x') or a_hex.startswith('0x'):
        a_hex = a_hex[2:]
    return int(a_hex, 16)


def little_endian_bytes(a_num, min_bytes=2):
    retval = bytearray()
    remaining = a_num
    while remaining != 0:
        retval.append(remaining & 0xFF)
        remaining >>= 8
    while len(retval) < min_bytes:
        retval.append(0)
    return retval


def big_endian_bytes(a_num, min_bytes=2):
    retval = bytearray()
    remaining = a_num
    while remaining != 0:
        retval.append(remaining & 0xFF)
        remaining >>= 8
    while len(retval) < min_bytes:
        retval.append(0)
    return retval[::-1]


def little_endian_int(a_bytearray, signed=False):
    return int.from_bytes(a_bytearray, byteorder='little', signed=signed)


def big_endian_int(a_bytearray, signed=False):
    return int.from_bytes(a_bytearray, byteorder='big', signed=signed)


# group()/join()/hexdump()
# adapted from http://code.activestate.com/recipes/579064-hex-dump/
def group(a, *ns):
    for n in ns:
        a = [a[i:i + n] for i in range(0, len(a), n)]
    return a


def join(a, *cs):
    return [cs[0].join(join(t, *cs[1:])) for t in a] if cs else a


def hexdump(data, start=0):
    toHex = lambda c: '{:02X}'.format(c)
    toChr = lambda c: chr(c) if 32 <= c < 127 else '.'
    make = lambda f, *cs: join(group(list(map(f, data)), 8, 2), *cs)
    hs = make(toHex, '  ', ' ')
    cs = make(toChr, ' ', '')
    for i, (h, c) in enumerate(zip(hs, cs)):
        print('{:010X}: {:48}  {:16}'.format(i * 16 + start, h, c))


def read_binary_file(path_and_filename):
    try:
        with open(path_and_filename, mode='rb') as in_file:
            return in_file.read()
    except FileNotFoundError:
        return None


def write_binary_file(path_and_filename, binary):
    with open(path_and_filename, 'wb') as out_file:
        out_file.write(binary)
