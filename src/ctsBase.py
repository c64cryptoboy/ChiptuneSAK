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
    qpm: int = 112  #: Tempo in Quarter Notes per Minute (QPM)
    extensions: dict = field(default_factory=dict)  #: Allows arbitrary state to be passed


class Triplet:
    def __init__(self, start_time=0, duration=0):
        self.start_time = start_time    #: Start time for the triplet as a whole
        self.duration = duration        #: Duration for the entire triplet
        self.content = []               #: The notes that go inside the triplet


class ChiptuneSAKBase:
    @classmethod
    def cts_type(cls):
        return 'ChiptuneSAKBase'

    def __init__(self):
        self._options = {}

    def get_option(self, arg, default=None):
        """
        Get an option

        :param arg: option name
        :type arg: string
        :param default: default value
        :type default: type of option
        :return: value of option
        :rtype: option type
        """
        if arg in self._options:
            return self._options[arg]
        return default

    def get_options(self):
        """
        Get a dictionary of all current options

        :return: options
        :rtype: dict
        """
        return self._options

    def set_options(self, **kwargs):
        """
        Set options.  All option keywords are converted to lowercase.

        :param kwargs: options
        :type kwargs: keyword options
        """
        for op, val in kwargs.items():
            self._options[op.lower()] = val


class ChiptuneSAKIR(ChiptuneSAKBase):
    @classmethod
    def cts_type(cls):
        return 'IR'

    def __init__(self):
        ChiptuneSAKBase.__init__(self)

    def to_chirp(self, **kwargs):
        """
        Converts a song to Chirp IR

        :return: chirp song
        :rtype: ctsChirp.ChirpSong
        """
        raise ChiptuneSAKNotImplemented("Conversion to Chirp not implemented")

    def to_mchirp(self, **kwargs):
        """
        Converts a song to MChirp IR

        :return: chirp song
        :rtype: ctsMChirp.MChirpSong
        """
        raise ChiptuneSAKNotImplemented("Conversion to MChirp not implemented")

    def to_rchirp(self, **kwargs):
        """
        Converts a song to RChirp IR

        :return: chirp song
        :rtype: ctsRChirp.RChirpSong
        """
        raise ChiptuneSAKNotImplemented("Conversion to RChirp not implemented")


class ChiptuneSAKIO(ChiptuneSAKBase):
    @classmethod
    def cts_type(cls):
        return 'IO'

    def __init__(self):
        ChiptuneSAKBase.__init__(self)

    def to_chirp(self, filename, **kwargs):
        """
        Imports a file into a ChirpSong

        :param filename: filename to import
        :type filename: str
        :return: Chirp song
        :rtype: ctsChirp.ChirpSong object
        """
        raise ChiptuneSAKNotImplemented(f"Not implemented")

    def to_rchirp(self, filename, **kwargs):
        """
        Imports a file into an RChirpSong

        :param filename: filename to import
        :type filename: str
        :return: RChirp song
        :rtype: ctsRChirp.RChirpSong object
        """
        raise ChiptuneSAKNotImplemented(f"Not implemented")

    def to_mchirp(self, filename, **kwargs):
        """
        Imports a file into a ChirpSong

        :param filename: filename to import
        :type filename: str
        :return: MChirp song
        :rtype: ctsMChirp.MChirpSong object
        """
        raise ChiptuneSAKNotImplemented(f"Not implemented")

    def to_bin(self, ir_song, **kwargs):
        """
        Outputs a song into the desired binary format (which may be ASCII text)

        :param ir_song: song to export
        :type ir_song: ChirpSong, MChirpSong, or RChirpSong
        :return: binary
        :rtype: either str or bytearray, depending on the output
        """
        raise ChiptuneSAKNotImplemented(f"Not implemented for type {ir_song.cts_type()}")

    def to_file(self, ir_song, filename, **kwargs):
        """
        Writes a song to a file

        :param ir_song: song to export
        :type ir_song: ChirpSong, MChirpSong, or RChirpSong
        :return: True on success
        :rtype: boolean
        """
        raise ChiptuneSAKNotImplemented(f"Not implemented for type {ir_song.cts_type()}")


class ChiptuneSAKCompress(ChiptuneSAKBase):
    @classmethod
    def cts_type(cls):
        return 'Compress'

    def __init__(self):
        ChiptuneSAKBase.__init__(self)

    def compress(self, rchirp_song, **kwargs):
        """
        Compresses an rchirp song

        :param rchirp_song: song to compress
        :type rchirp_song: ctsRChirp.RChirpSong
        :return: rchirp_song with compression
        :rtype: ctsRChirp.RChirpSong
        """
        raise ChiptuneSAKNotImplemented(f"Not implemented")


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
    :return: string representation of note and octave
    :rtype: str
    """
    if not 0 <= note_num <= 127:
        raise ChiptuneSAKValueError("Illegal note number %d" % note_num)
    octave = (note_num // 12) + octave_offset - 1
    pitch = note_num % 12
    return "%s%d" % (ctsConstants.PITCHES[pitch], octave)


# Regular expression for matching note names
note_name_format = re.compile('^([A-G])(#|##|b|bb)?(-{0,1}[0-7])$')


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
    f = Fraction(note.duration / ppq).limit_denominator(16)
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
    f = Fraction(time, ppq).limit_denominator(32)
    return f.denominator
