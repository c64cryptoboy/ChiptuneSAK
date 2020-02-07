import sys
import sandboxPath
import collections
from fractions import Fraction
from ctsBase import *
from ctsChirp import Note
from ctsMChirp import MChirpSong
import ctsMidi

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
    Items are sorted by time and then, for equal times, by duration (decreasing) and voice
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
    return (PITCHES[pitch][::-1], octave)  # Accidentals come BEFORE note name


def basic_duration_to_name(duration, ppq):
    """
    Gets a note duration name for a given duration.
    """
    f = Fraction(duration / ppq).limit_denominator(8)
    if f not in basic_durations:
        raise ChiptuneSAKValueError("Illegal note duration for BASIC: %s" % str(f))
    return basic_durations[f]


def trim_note_lengths(song):
    """
    Trims the note lengths in a  ChirpSong to only those allowed in C128 basic
    """
    for i_t, t in enumerate(song.tracks):
        for i_n, n in enumerate(t.notes):
            f = Fraction(n.duration / song.metadata.ppq).limit_denominator(8)
            if f not in basic_durations:
                for d in sorted(basic_durations, reverse=True):
                    if f >= d:
                        n.duration = d * song.metadata.ppq
                        break
                song.tracks[i_t].notes[i_n] = n   # Trim the note in place


def measures_to_basic(mchirp_song):
    """
    Converts an MChirpSong to C128 Basic command strings.
    :param mchirp_song:
    :return:
    """
    commands = []
    n_measures = len(mchirp_song.tracks[0].measures)
    last_voice = 0
    last_octave = -10
    last_duration = 0
    for im in range(n_measures):
        contents = []
        for v in range(len(mchirp_song.tracks)):
            m = mchirp_song.tracks[v].measures[im]

            # If this voice doesn't have any notes in the measure, just ignore it.
            note_count = sum(1 for e in m.events if isinstance(e, Note))
            if note_count == 0:
                continue

            for e in m.events:
                if isinstance(e, Note):
                    contents.append(BasicNote(e.start_time, e.note_num, e.duration, v+1))
                elif isinstance(e, Rest):
                    contents.append(BasicRest(e.start_time, e.duration, v+1))
        contents.sort(key=sort_order)
        measure_commands = []
        # Last voice gets reset at the start of each measure.
        """
        For this initial version, I make the following assumptions:
        -  current voice is global, but NOT preserved between measures
        -  current octave is global and preserved between measures and voice changes
        -  current note length is global and IS preserved between measures and voice changes
        
        I chose these assumptions because they gave the closest approximation to the hand-coded example.
        The most likely incorrect assumption is that the octaves may be stored separately for the 3
        voices.
        
        If any of these assumptions is not correct, fixing the code should be fairly simple.
        """
        last_voice = 0
        for e in contents:
            if isinstance(e, BasicNote):
                d_name = basic_duration_to_name(e.duration, mchirp_song.metadata.ppq)
                note_name, octave = basic_pitch_to_note_name(e.note_num)
                current_command = []
                if e.voice != last_voice:
                    current_command.append('V%d' % e.voice)
                if octave != last_octave:
                    current_command.append('O%s' % octave)
                if e.duration != last_duration:
                    current_command.append(d_name)
                current_command.append(note_name)
                measure_commands.append(''.join(current_command))
                # Set all the state variables
                last_voice = e.voice
                last_octave = octave
                last_duration = e.duration
            elif isinstance(e, BasicRest):
                d_name = basic_duration_to_name(e.duration, mchirp_song.metadata.ppq)
                current_command = []
                if e.voice != last_voice:
                    current_command.append('V%d' % e.voice)
                if e.duration != last_duration:
                    current_command.append(d_name)
                current_command.append('R')
                measure_commands.append(''.join(current_command))
                # Set the state variables
                last_voice = e.voice
                last_duration = e.duration
        commands.append(' '.join(measure_commands) + ' M')
    return commands


def midi_to_C128_BASIC(filename):
    song = ctsMidi.midi_to_chirp(filename)
    song.quantize_from_note_name('16')
    song.remove_polyphony()
    trim_note_lengths(song)
    if len(song.metadata.name) == 0:
        song.metadata.name = filename
    mchirp_song = MChirpSong(song)

    basic_strings = measures_to_basic(mchirp_song)

    result = []
    current_line = 1
    result.append('%d REM %s' % (current_line * 10, song.metadata.name))
    current_line += 1
    result.append('%d TEMPO 10' % (current_line * 10))
    current_line += 1
    result.append('%d PLAY"V1T0V2T0V3T0"' % (current_line * 10))
    current_line += 1

    for s in basic_strings:
        result.append('%d PLAY "%s"' % (current_line * 10, s))
        current_line += 1

    print('\n'.join(line.lower() for line in result))


if __name__ == '__main__':
    midi_to_C128_BASIC(sys.argv[1])


