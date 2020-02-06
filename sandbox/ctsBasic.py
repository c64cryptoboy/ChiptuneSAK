import sandboxPath
import collections
from fractions import Fraction
from ctsBase import *
from ctsChirp import Note
from ctsMChirp import MChirpSong

BasicNote = collections.namedtuple('BasicNote', ['start_time', 'note_num', 'duration', 'voice'])
BasicRest = collections.namedtuple('BasicRest', ['start_time', 'duration', 'voice'])

basic_durations = {
    Fraction(4, 1): '1', Fraction(3, 1): '2.', Fraction(2, 1): '2', Fraction(3, 2): '4.', Fraction(1, 1):'4',
    Fraction(3, 4): '8.', Fraction(1, 2): '8', Fraction(3, 8): '16.', Fraction(1, 4): '16',
    Fraction(3, 16): '32.', Fraction(1, 8): '32', Fraction(3, 32): '64.', Fraction(1, 16): '64'
}

def sort_order(c):
    """
    Sort function for measure contents.
    Items are sorted by time and then, for equal times, in this order:
        Time Signature
        Key Signature
        Tempo
        Other MIDI message(s)
        Notes and rests
    """
    if isinstance(c, BasicNote):
        return (c.start_time, -c.duration, c.voice, 10)
    elif isinstance(c, BasicRest):
        return (c.start_time, -c.duration, c.voice, 10)


def duration_to_name(duration, ppq):
    for f in sorted(basic_durations, reverse=True):
        if duration >= f * ppq:
            return basic_durations[f]
    return '?'

def measures_to_basic(mchirp_song):
    commands = []
    for i in range(len(mchirp_song.tracks[0].measures)):
        contents = []
        for v in range(len(mchirp_song.tracks)):
            m = mchirp_song.tracks[v].measures[i]
            for e in m:
                if isinstance(e, Note):
                    contents.append(BasicNote(e.start_time, e.note_num, e.duration, v+1))
                elif isinstance(e, Rest):
                    contents.append(BasicRest(e.start_time, e.duration, v+1))
        contents.sort(key=sort_order)
        measure_commands = []
        for e in contents:
            if isinstance(e, BasicNote):
                l_name = duration_to_name(e.duration, mchirp_song.ppq)
                n = pitch_to_note_name(e.note_num)
                measure_commands.append('V%d%s%s' % (e.voice, n, l_name))
            elif isinstance(e, BasicRest):
                l_name = duration_to_name(e.duration, mchirp_song.ppq)
                measure_commands.append('V%dR%s' % (e.voice, l_name))
        commands.append(' '.join(measure_commands))
    return '\n'.join(measure_commands)

