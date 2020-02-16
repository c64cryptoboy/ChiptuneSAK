import collections
from fractions import Fraction
from ctsErrors import *
from ctsConstants import *
from recordtype import recordtype

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
        self.copyright = ''
        self.time_signature = TimeSignature(0, 4, 4)
        self.key_signature = KeySignature(0, 'C')
        self.bpm = 112



# --------------------------------------------------------------------------------------
#
#  Utility functions
#
# --------------------------------------------------------------------------------------

def quantization_error(t_ticks, q_ticks):
    """
    Calculated the error, in ticks, for the given time for a quantization of q ticks.
    """
    j = t_ticks // q_ticks
    return int(min(abs(t_ticks - q_ticks * j), abs(t_ticks - q_ticks * (j + 1))))


def objective_error(notes, test_quantization):
    """
    This is the objective function for getting the error for the entire set of notes for a
    given quantization in ticks.  The function used here could be a sum, RMS, or other
    statistic, but empirical tests indicate that the max used here works well and is robust.
    """
    return max(quantization_error(n, test_quantization) for n in notes)


def find_quantization(ppq, time_series):
    """
    Find the optimal quantization in ticks to use for a given set of times.  The algorithm given
    here is by no means universal or guaranteed, but it usually gives a sensible answer.

    The algorithm works as follows:
    - Starting with quarter notes, obtain the error from quantization of the entire set of times.
    - Then obtain the error from quantization by 2/3 that value (i.e. triplets).
    - Then go to the next power of two (e.g. 8th notes, a6th notes, etc.) and repeat

    A minimum in quantization error will be observed at the "right" quantization.  In either case
    above, the next quantization tested will be incommensurate (either a factor of 2/3 or a factor
    of 3/4) which will make the quantization error worse.

    Thus, the first minimum that appears will be the correct value.

    The algorithm does not seem to work as well for note durations as it does for note starts, probably
    because performed music rarely has clean note cutoffs.
    """
    last_err = len(time_series) * ppq
    n_notes = len(time_series)
    last_q = ppq
    note_value = 4
    while note_value <= 128:  # We have arbitrarily chosen 128th notes as the fastest possible
        test_quantization = ppq * 4 // note_value
        e = objective_error(time_series, test_quantization)
        # print(test_quantization, e) # This was useful for observing the behavior of real-world music
        if e == 0:  # Perfect quantization!  We are done.
            return test_quantization
        # If this is worse than the last one, the last one was the right one.
        elif e > last_err:
            return last_q
        last_q = test_quantization
        last_err = e

        # Now test the quantization for triplets of the current note value.
        test_quantization = test_quantization * 2 // 3
        e = objective_error(time_series, test_quantization)
        # print(test_quantization, e) # This was useful for observing the behavior of real-world music
        if e == 0:  # Perfect quantization!  We are done.
            return test_quantization
            # If this is worse than the last one, the last one was the right one.
        elif e > last_err:
            return last_q
        last_q = test_quantization
        last_err = e

        # Try the next power of two
        note_value *= 2
    return 1  # Return a 1 for failed quantization means 1 tick resolution


def find_duration_quantization(ppq, durations, qticks_note):
    """
    The duration quantization is determined from the shortest note length.
    The algorithm starts from the estimated quantization for note starts.
    """
    min_length = min(durations)
    if not (min_length > 0):
        raise ChiptuneSAKQuantizationError("Illegal minimum note length (%d)" % min_length)
    current_q = qticks_note
    ratio = min_length / current_q
    while ratio < 0.9:
        # Try a triplet
        tmp_q = current_q
        current_q = current_q * 3 // 2
        ratio = min_length / current_q
        if ratio > 0.9:
            break
        current_q = tmp_q // 2
        ratio = min_length / current_q
    return current_q


def quantize_fn(t, qticks):
    """
    This function quantizes a time to a certain number of ticks.
    """
    current = t // qticks
    next = current + 1
    current *= qticks
    next *= qticks
    if abs(t - current) <= abs(next - t):
        return current
    else:
        return next


def duration_to_note_name(duration, ppq):
    """
    Given a ppq (pulses per quaver) convert a duration to a human readable note length, e.g., 'eighth'
    Works for notes, dotted notes, and triplets down to sixty-fourth notes.
    """
    f = Fraction(duration / ppq).limit_denominator(64)
    return DURATIONS.get(f, '<unknown>')


def pitch_to_note_name(note_num, octave_offset=0):
    """
    Gets note name for a given MIDI pitch
    """
    if not 0 <= note_num <= 127:
        raise ChiptuneSAKValueError("Illegal note number %d" % note_num)
    octave = (note_num // 12) + octave_offset
    pitch = note_num % 12
    return "%s%d" % (PITCHES[pitch], octave)


def is_triplet(note, ppq):
    """
    Determine if note is a triplet
        :param note:
        :param ppq:
        :return:
    """
    f = Fraction(note.duration/ppq).limit_denominator(16)
    if f.denominator % 3 == 0:
        return True
    return False

# Goat tracker commons (TODO: Move this someplace else at some point)

GtPatternRow = recordtype('GtPatternRow',
    [('note_data', 0xBD), ('inst_num', 0), ('command', 0), ('command_data', 0)])

# TODO: Replace 0xBD with GT_REST after refactoring
PATTERN_EMPTY_ROW = GtPatternRow(note_data = 0xBD) 

# TODO: Replace 0xFF with GT_PAT_END
PATTERN_END_ROW = GtPatternRow(note_data = 0xFF)

GtInstrument = recordtype('GtInstrument',
    [('inst_num', 0), ('attack_decay', 0), ('sustain_release', 0), ('wave_ptr', 0), ('pulse_ptr', 0),
    ('filter_ptr', 0), ('vib_speedtable_ptr', 0), ('vib_delay', 0), ('gateoff_timer', 0x02),
    ('hard_restart_1st_frame_wave', 0x09), ('inst_name', '')])
