import re
import collections
from dataclasses import dataclass, field
from fractions import Fraction
from ctsErrors import *
import ctsConstants
import ctsKey


# Named tuple types for several lists throughout
TimeSignatureEvent = collections.namedtuple('TimeSignature', ['start_time', 'num', 'denom'])
KeySignatureEvent = collections.namedtuple('KeySignature', ['start_time', 'key'])
TempoEvent = collections.namedtuple('Tempo', ['start_time', 'qpm'])
OtherMidiEvent = collections.namedtuple('OtherMidi', ['start_time', 'msg'])
ProgramEvent = collections.namedtuple('Program', ['start_time', 'program'])
Beat = collections.namedtuple('Beat', ['start_time', 'measure', 'beat'])
Rest = collections.namedtuple('Rest', ['start_time', 'duration'])
MeasureMarker = collections.namedtuple('MeasureMarker', ['start_time', 'measure_number'])


@dataclass
class SongMetadata:
    ppq: int = ctsConstants.DEFAULT_MIDI_PPQN  #: PPQ = Pulses Per Quarter = ticks/quarter note
    name: str = ''  #: Song name
    composer: str = ''  #: Composer
    copyright: str = ''  #: Copyright statement
    time_signature: TimeSignatureEvent = TimeSignatureEvent(0, 4, 4)  #: Starting time signature
    key_signature: KeySignatureEvent = KeySignatureEvent(0, ctsKey.ChirpKey('C'))  #: Starting key signature
    qpm: int = 112  #: Tmpo in Quarter Notes per Minute (QPM)
    extensions: dict = field(default_factory=dict)  #: Allows arbitrary state to be passed


class Triplet:
    def __init__(self, start_time=0, duration=0):
        self.start_time = start_time    #: Start time for the triplet as a whole
        self.duration = duration        #: Duration for the entire triplet
        self.content = []               #: The notes that go inside the triplet


class ChiptuneSAKBase:
    pass


class ChiptuneSAKIR(ChiptuneSAKBase):
    @classmethod
    def ir_type(cls):
        return 'IR'

    def to_chirp(self):
        raise ChiptuneSAKNotImplemented("Conversion to Chirp not implemented")

    def to_mchirp(self):
        raise ChiptuneSAKNotImplemented("Conversion to MChirp not implemented")

    def to_rchirp(self):
        raise ChiptuneSAKNotImplemented("Conversion to RChirp not implemented")


class ChiptuneSAKIO(ChiptuneSAKBase):
    @classmethod
    def io_type(cls):
        return 'IO'

    def __init__(self):
        self.options = {}

    def to_chirp(self, filename):
        raise ChiptuneSAKIOError(f"Not implemented")

    def to_rchirp(self, filename):
        raise ChiptuneSAKIOError(f"Not implemented")

    def to_mchirp(self, filename):
        raise ChiptuneSAKIOError(f"Not implemented")

    def to_bin(self, ir_song):
        raise ChiptuneSAKIOError(f"Not implemented for type {ir_song.ir_type()}")

    def to_file(self, ir_song, filename):
        raise ChiptuneSAKIOError(f"Not implemented for type {ir_song.ir_type()}")


class ChiptuneSAKCompress(ChiptuneSAKBase):
    @classmethod
    def compress_type(cls):
        return 'Compress'

    def __init__(self):
        self.options = {}

    def compress(self, rchirp_song):
        raise ChiptuneSAKIOError(f"Not implemented")


# --------------------------------------------------------------------------------------
#
#  Utility functions
#
# --------------------------------------------------------------------------------------


def duration_to_note_name(duration, ppq, locale='US'):
    """
    Given a ppq (pulses per quaver) convert a duration to a human readable note length, e.g., 'eighth'
    Works for notes, dotted notes, and triplets down to sixty-fourth notes.
    :param duration:
    :type duration:
    :param ppq:
    :type ppq:
    :param locale:
    :type locale:
    :return:
    :rtype:
    """
    f = Fraction(duration / ppq).limit_denominator(64)
    return ctsConstants.DURATIONS[locale.upper()].get(f, '<unknown>')


def pitch_to_note_name(note_num, octave_offset=0):
    """
    Gets note name for a given MIDI pitch
    :param note_num:
    :type note_num:
    :param octave_offset:
    :type octave_offset:
    :return:
    :rtype:
    """
    if not 0 <= note_num <= 127:
        raise ChiptuneSAKValueError("Illegal note number %d" % note_num)
    octave = (note_num // 12) + octave_offset - 1
    pitch = note_num % 12
    return "%s%d" % (ctsConstants.PITCHES[pitch], octave)


# Regular expression for matching note names
note_name_format = re.compile('^([A-G])(#|##|b|bb)?([0-7])$')


def note_name_to_pitch(note_name, octave_offset=0):
    """
    Returns MIDI note number for a named pitch.  C4 = 60
    Includes processing of enharmonic notes (double sharps or double flats)

    :param note_name: A note name as a string, e.g. C#4
    :type note_name: str
    :param octave_offset: Octave offset
    :type octave_offset: int
    :return: Midi note number
    :rtype: int
    """
    if note_name_format.match(note_name) is None:
        raise ChiptuneSAKValueError('Illegal note name: "%s"' % note_name)
    m = note_name_format.match(note_name)
    note_name = m.group(1)
    accidentals = m.group(2)
    octave = int(m.group(3)) - octave_offset + 1
    note_num = ctsConstants.PITCHES.index(note_name) + 12 * octave
    if accidentals is not None:
        note_num += accidentals.count('#')
        note_num -= accidentals.count('b')
    return note_num

    
def decompose_duration(duration, ppq, allowed_durations):
    """
    Decomposes a given duration into a sum of allowed durations.
    This function uses a greedy algorithm, which iteratively finds the largest allowed duration shorter than
    the remaining duration and subtracts it from the remaining
    :param duration:           Duration to be decomposed, in ticks.
    :type duration:            int
    :param ppq:                Ticks per quarter note.
    :type ppq:                 int
    :param allowed_durations:  Dictionary of allowed durations.  Allowed durations are expressed as fractions
                               of a quarter note.
    :type allowed_durations:   dictionary (or set) of allowed durations, as fractions of a quarter note
    :return:                   List of fractions
    :rtype:                    list
    """
    ret_durations = []
    min_allowed_duration = min(allowed_durations)
    remainder = duration
    while remainder > 0:
        if remainder < min_allowed_duration * ppq:
            raise ChiptuneSAKValueError("Illegal note duration %d" % duration)
        for d in sorted(allowed_durations, reverse=True):
            if remainder >= d * ppq:
                ret_durations.append(d)
                remainder -= d * ppq
                break
    return ret_durations


def is_triplet(note, ppq):
    """
    Determine if note is a triplet
    :param note:  note
    :type note:   ctsChirp.Note
    :param ppq:   ppq
    :type ppq:    int
    :return:      True of the note is a triplet type
    :rtype:       bool
    """
    f = Fraction(note.duration/ppq).limit_denominator(16)
    if f.denominator % 3 == 0:
        return True
    return False


def start_beat_type(time, ppq):
    """
    Gets the beat type that would have to be used to make this note an integral number of beats
    from the start of the measure
    :param time:  Time in ticks from the start of the measure.
    :type time:   int
    :param ppq:   ppq for the song
    :type ppq:    int
    :return:      Denominator that would have to be used to make this note an integral number of beats
                  from the start of the measure.  If the note is a triplet not starting on the beat it
                  will be a multiple of 3.
    :rtype:       int
    """
    f = Fraction(time, ppq).limit_denominator(16)
    return f.denominator


def freq_for_midi_num(midi_num, tuning=ctsConstants.CONCERT_A):
    """
    Convert a midi number into its frequency

    :param midi_num: midi number
    :type midi_num: int
    :param tuning: frequency, defaults to CONCERT_A
    :type tuning: float, optional
    :return: frequency for midi number
    :rtype: float
    """
    return tuning * pow(2, (midi_num - ctsConstants.A4_MIDI_NUM) / 12)


def get_arch_freq_for_midi_num(midi_num, architecture, tuning=ctsConstants.CONCERT_A):
    """
    Convert a pitch frequency into a frequency for a particular architecture (e.g. PAL C64)
    
    :param midi_num: midi note number
    :type midi_num: int
    :param architecture: Architecture description string
    :type architecture: string
    :return: int frequency for arch
    :rtype: int    
    """
    if architecture not in ('NTSC-C64', 'PAL-C64'):
        raise ChiptuneSAKValueError("Error: arch type not supported for freq conversion")

    # ref: https://codebase64.org/doku.php?id=base:how_to_calculate_your_own_sid_frequency_table
    # SID oscillator is 24-bit (phase-accumulating design)
    return round((0x1000000 / ctsConstants.ARCH[architecture].system_clock) * freq_for_midi_num(midi_num, tuning))
