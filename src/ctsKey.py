import collections
from ctsErrors import *

Key = collections.namedtuple('Key', ['offset', 'type', 'sharps', 'flats'])

KEYS = {
'C' : Key(0,  'major', (), ()),
'G' : Key(7,  'major', ('F#'), ()),
'D' : Key(2,  'major', ('F#', 'C#'), ()),
'A' : Key(9,  'major', ('F#', 'C#', 'G#'), ()),
'E' : Key(4,  'major', ('F#', 'C#', 'G#', 'D#'), ()),
'B' : Key(11, 'major', ('F#', 'C#', 'G#', 'D#', 'A#'), ()),
'F#': Key(6,  'major', ('F#', 'C#', 'G#', 'D#', 'A#', 'E#'), ()),
'C#': Key(1,  'major', ('F#', 'C#', 'G#', 'D#', 'A#', 'E#', 'B#'), ()),
'F' : Key(5,  'major', (), ('Bb')),
'Bb': Key(10, 'major', (), ('Bb', 'Eb')),
'Eb': Key(3,  'major', (), ('Bb', 'Eb', 'Ab')),
'Ab': Key(8,  'major', (), ('Bb', 'Eb', 'Ab', 'Db')),
'Db': Key(1,  'major', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb')),
'Gb': Key(6,  'major', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb')),
'Cb': Key(11, 'major', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb', 'Fb')),
'Am':  Key(0,  'minor', (), ()),
'Em':  Key(7,  'minor', ('F#'), ()),
'Bm' : Key(2,  'minor', ('F#', 'C#'), ()),
'F#m': Key(9,  'minor', ('F#', 'C#', 'G#'), ()),
'C#m': Key(4,  'minor', ('F#', 'C#', 'G#', 'D#'), ()),
'G#m': Key(11, 'minor', ('F#', 'C#', 'G#', 'D#', 'A#'), ()),
'D#m': Key(6,  'minor', ('F#', 'C#', 'G#', 'D#', 'A#', 'E#'), ()),
'A#m': Key(1,  'minor', ('F#', 'C#', 'G#', 'D#', 'A#', 'E#', 'B#'), ()),
'Dm' : Key(5,  'minor', (), ('Bb')),
'Gm' : Key(10, 'minor', (), ('Bb', 'Eb')),
'Cm' : Key(3,  'minor', (), ('Bb', 'Eb', 'Ab')),
'Fm' : Key(8,  'minor', (), ('Bb', 'Eb', 'Ab', 'Db')),
'Bbm': Key(1,  'minor', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb')),
'Ebm': Key(6,  'minor', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb')),
'Abm': Key(6,  'minor', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb', 'Fb')),
}


def normalize(key_str):
    if len(key_str) > 1:
        return key_str[0].upper() + key_str[1:].lower()
    else:
        return key_str.upper()


def accidentals(key_str):
    if len(KEYS[key_str].flats) > 0:
        return 'flats'
    else:
        return 'sharps'


class ChirpKey:
    def __init__(self, key_str):
        self.key_name = normalize(key_str)
        if self.key_name not in KEYS:
            raise ChiptuneSAKValueError("Illegal key %s" % key_str)
        self.key = KEYS[key_str]

    def is_major(self):
        return self.key.type == 'major'

    def is_minor(self):
        return self.key.type == 'minor'

    def transpose(self, semitones):
        new_key_offset = (self.key.offset + semitones) % 12
        possible = [k for k in KEYS if KEYS[k].offset == new_key_offset and KEYS[k].type == self.key.type]
        if len(possible) > 1:
            possible = [k for k in possible if accidentals(k) == accidentals(self.key_name)]
        assert(len(possible) == 1)
        self.key_name = possible[0]
        self.key = KEYS[self.key_name]

    def minimize_accidentals(self):
        possible = [k for k in KEYS if KEYS[k].offset == self.key.offset and KEYS[k].type == self.key.type]
        if len(possible) > 1:
            possible.sort(key=lambda k: len(KEYS[k].sharps) + len(KEYS[k].flats))
        self.key_name = possible[0]
        self.key = KEYS[self.key_name]

    def accidentals(self):
        return accidentals(self.key_name)

    def __str__(self):
        return self.key_name


if __name__ == '__main__':
    k = ChirpKey('B')
    print(k)

    k.transpose(2)
    print(k)

    k.transpose(2)
    print(k)

    k.minimize_accidentals()
    print('Minimized accidentals: %s' % k)

    k.transpose(-7)
    print(k)
