# Common byte functions


def int_to_hex(anInt):
    return "%X" % anInt


def hex_to_int(aHex):
    if aHex.startswith('$'):
        aHex = aHex[1:]
    return int(aHex, 16)


def little_endian_bytes(a16BitNum):
    hi = a16BitNum//256
    lo = a16BitNum - hi*256
    return bytes([lo, hi])


def little_endian_int(aBytearray):
    val = 0
    for i, byte in enumerate(aBytearray):
        val |= (byte << (8*i))
    return val


def big_endian_int(aBytearray):
    val = 0
    for byte in aBytearray:
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

