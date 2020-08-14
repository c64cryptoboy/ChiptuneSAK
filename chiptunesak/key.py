# flake8: noqa

from chiptunesak.errors import ChiptuneSAKValueError
import collections

KeySignature = collections.namedtuple('Key', ['name', 'offset', 'type', 'sharps', 'flats'])

KEYS = {
    'C':   KeySignature('C', 0,    'major', (), ()),
    'G':   KeySignature('G', 7,    'major', ('F#'), ()),
    'D':   KeySignature('D', 2,    'major', ('F#', 'C#'), ()),
    'A':   KeySignature('A', 9,    'major', ('F#', 'C#', 'G#'), ()),
    'E':   KeySignature('E', 4,    'major', ('F#', 'C#', 'G#', 'D#'), ()),
    'B':   KeySignature('B', 11,   'major', ('F#', 'C#', 'G#', 'D#', 'A#'), ()),
    'F#':  KeySignature('F#', 6,   'major', ('F#', 'C#', 'G#', 'D#', 'A#', 'E#'), ()),
    'C#':  KeySignature('C#', 1,   'major', ('F#', 'C#', 'G#', 'D#', 'A#', 'E#', 'B#'), ()),
    'F':   KeySignature('F',  5,   'major', (), ('Bb')),
    'Bb':  KeySignature('Bb', 10,  'major', (), ('Bb', 'Eb')),
    'Eb':  KeySignature('Eb', 3,   'major', (), ('Bb', 'Eb', 'Ab')),
    'Ab':  KeySignature('Ab', 8,   'major', (), ('Bb', 'Eb', 'Ab', 'Db')),
    'Db':  KeySignature('Db', 1,   'major', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb')),
    'Gb':  KeySignature('Gb', 6,   'major', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb')),
    'Cb':  KeySignature('Cb', 11,  'major', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb', 'Fb')),
    'Am':  KeySignature('Am', 0,   'minor', (), ()),
    'Em':  KeySignature('Em', 7,   'minor', ('F#'), ()),
    'Bm':  KeySignature('Bm', 2,   'minor', ('F#', 'C#'), ()),
    'F#m': KeySignature('F#m', 9,  'minor', ('F#', 'C#', 'G#'), ()),
    'C#m': KeySignature('C#m', 4,  'minor', ('F#', 'C#', 'G#', 'D#'), ()),
    'G#m': KeySignature('G#m', 11, 'minor', ('F#', 'C#', 'G#', 'D#', 'A#'), ()),
    'D#m': KeySignature('D#m', 6,  'minor', ('F#', 'C#', 'G#', 'D#', 'A#', 'E#'), ()),
    'A#m': KeySignature('A#m', 1,  'minor', ('F#', 'C#', 'G#', 'D#', 'A#', 'E#', 'B#'), ()),
    'Dm':  KeySignature('Dm', 5,   'minor', (), ('Bb')),
    'Gm':  KeySignature('Gm', 10,  'minor', (), ('Bb', 'Eb')),
    'Cm':  KeySignature('Cm', 3,   'minor', (), ('Bb', 'Eb', 'Ab')),
    'Fm':  KeySignature('Fm', 8,   'minor', (), ('Bb', 'Eb', 'Ab', 'Db')),
    'Bbm': KeySignature('Bbm', 1,  'minor', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb')),
    'Ebm': KeySignature('Ebm', 6,  'minor', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb')),
    'Abm': KeySignature('Abm', 6,  'minor', (), ('Bb', 'Eb', 'Ab', 'Db', 'Gb', 'Cb', 'Fb')),
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
        self.key_signature = KEYS[key_str]

    def is_major(self):
        return self.key_signature.type == 'major'

    def is_minor(self):
        return self.key_signature.type == 'minor'

    def transpose(self, semitones):
        new_key_offset = (self.key_signature.offset + semitones) % 12
        possible = [k for k in KEYS if KEYS[k].offset == new_key_offset and KEYS[k].type == self.key_signature.type]
        if len(possible) > 1:
            possible = [k for k in possible if accidentals(k) == accidentals(self.key_name)]
        assert(len(possible) == 1)
        self.key_name = possible[0]
        self.key_signature = KEYS[self.key_name]
        return self

    def minimize_accidentals(self):
        possible = [k for k in KEYS
                    if KEYS[k].offset == self.key_signature.offset and KEYS[k].type == self.key_signature.type]
        if len(possible) > 1:
            possible.sort(key=lambda k: len(KEYS[k].sharps) + len(KEYS[k].flats))
        self.key_name = possible[0]
        self.key_signature = KEYS[self.key_name]
        return self

    def accidentals(self):
        return accidentals(self.key_name)

    def __eq__(self, other):
        return self.key_signature == other.key_signature

    def __str__(self):
        return self.key_name
