import collections
import ctsConstants

# Named tuple types for several lists throughout
TimeSignature = collections.namedtuple('TimeSignature', ['start_time', 'num', 'denom'])
KeySignature = collections.namedtuple('KeySignature', ['start_time', 'key'])
Tempo = collections.namedtuple('Tempo', ['start_time', 'bpm'])
OtherMidi = collections.namedtuple('OtherMidi', ['start_time', 'msg'])
Beat = collections.namedtuple('Beat', ['start_time', 'measure', 'beat'])
Rest = collections.namedtuple('Rest', ['start_time', 'duration'])
Program = collections.namedtuple('Program', ['start_time', 'program'])
MeasureMarker = collections.namedtuple('MeasureMarker', ['start_time', 'measure_number'])


class SongMetadata:
    def __init__(self):
        self.ppq = 960
        self.name = ''
        self.composer = ''
        self.time_signature = TimeSignature(0, 4, 4)
        self.key_signature = KeySignature(0, 'C')
        self.bpm = 112


