# Common byte functions


def int_to_hex(an_int):
    return "%X" % an_int


def hex_to_int(a_hex):
    if a_hex.startswith('$'):
        a_hex = a_hex[1:]
    elif a_hex.startswith('\\x') or a_hex.startswith('0x'):
        a_hex = a_hex[2:]
    return int(a_hex, 16)


def le_short_to_bytes(a_16_bit_num):
    hi = a_16_bit_num >> 8
    lo = a_16_bit_num & 256
    return bytearray([lo, hi])


def be_short_to_bytes(a_16_bit_num):
    hi = a_16_bit_num >> 8
    lo = a_16_bit_num & 256
    return bytearray([hi, lo])


def little_endian_int(a_bytearray):
    val = 0
    for i, byte in enumerate(a_bytearray):
        val |= (byte << (8*i))
    return val


def big_endian_int(a_bytearray):
    val = 0
    for byte in a_bytearray:
        val = (val << 8) | (byte << 8)
    return val


# start of copy from http://code.activestate.com/recipes/579064-hex-dump/
def group(a, *ns):
    for n in ns:
        a = [a[i:i+n] for i in range(0, len(a), n)]
    return a


def join(a, *cs):
    return [cs[0].join(join(t, *cs[1:])) for t in a] if cs else a


def hexdump(data):
    toHex = lambda c: '{:02X}'.format(c)
    toChr = lambda c: chr(c) if 32 <= c < 127 else '.'
    make = lambda f, *cs: join(group(list(map(f, data)), 8, 2), *cs)
    hs = make(toHex, '  ', ' ')
    cs = make(toChr, ' ', '')
    for i, (h, c) in enumerate(zip(hs, cs)):
        print('{:010X}: {:48}  {:16}'.format(i * 16, h, c))
# end of copy from http://code.activestate.com/recipes/579064-hex-dump/

