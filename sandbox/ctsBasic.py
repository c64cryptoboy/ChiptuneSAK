import sys
import sandboxPath
import collections
from fractions import Fraction
from ctsBase import *
from ctsChirp import Note
from ctsMChirp import MChirpSong

BasicNote = collections.namedtuple('BasicNote', ['start_time', 'note_num', 'duration', 'voice'])
BasicRest = collections.namedtuple('BasicRest', ['start_time', 'duration', 'voice'])

basic_durations = {
    Fraction(6, 1): "W.", Fraction(4, 1): 'W',
    Fraction(3, 1): 'H.', Fraction(2, 1): 'H',
    Fraction(3, 2): 'Q.', Fraction(1, 1): 'Q',
    Fraction(3, 4): 'I.', Fraction(1, 2): 'I',
    Fraction(1, 4): 'S'
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


def basic_pitch_to_note_name(note_num, octave_offset=-2):
    """
    Gets note name for a given MIDI pitch
    """
    if not 0 <= note_num <= 127:
        raise ChiptuneSAKValueError("Illegal note number %d" % note_num)
    octave = (note_num // 12) + octave_offset
    pitch = note_num % 12
    return (PITCHES[pitch], octave)

def basic_duration_to_name(duration, ppq):
    f = Fraction(duration / ppq).limit_denominator(8)
    if f not in basic_durations:
        raise ChiptuneSAKValueError("Illegal note duration for BASIC: %s" % str(f))
    return basic_durations[f]

def trim_note_lengths(song):
    for i_t, t in enumerate(song.tracks):
        for i_n, n in enumerate(t.notes):
            f = Fraction(n.duration / song.metadata.ppq).limit_denominator(8)
            if f not in basic_durations:
                for d in sorted(basic_durations, reverse=True):
                    if f > d:
                        n.duration = d * song.metadata.ppq
                        break
                song.tracks[i_t].notes[i_n] = n


def measures_to_basic(mchirp_song):
    commands = []
    n_measures = len(mchirp_song.tracks[0].measures)
    for im in range(n_measures):
        contents = []
        for v in range(len(mchirp_song.tracks)):
            m = mchirp_song.tracks[v].measures[im]
            for e in m.events:
                if isinstance(e, Note):
                    contents.append(BasicNote(e.start_time, e.note_num, e.duration, v+1))
                elif isinstance(e, Rest):
                    contents.append(BasicRest(e.start_time, e.duration, v+1))
        contents.sort(key=sort_order)
        measure_commands = []
        for e in contents:
            if isinstance(e, BasicNote):
                d_name = basic_duration_to_name(e.duration, mchirp_song.metadata.ppq)
                note_name, octave = basic_pitch_to_note_name(e.note_num)
                measure_commands.append('V%dO%s%s%s' % (e.voice, octave, d_name,note_name))
            elif isinstance(e, BasicRest):
                l_name = basic_duration_to_name(e.duration, mchirp_song.metadata.ppq)
                measure_commands.append('V%d%sR' % (e.voice, l_name))
        commands.append(' '.join(measure_commands) + ' M')
    return '\n'.join(commands)

if __name__ == '__main__':
    import ctsMidi
    song = ctsMidi.midi_to_chirp(sys.argv[1])
    song.quantize_from_note_name('16')
    song.remove_polyphony()
    trim_note_lengths(song)
    mchirp_song = MChirpSong(song)

    result = measures_to_basic(mchirp_song)

    print(result)

