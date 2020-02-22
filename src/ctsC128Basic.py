# Lower MChirp to C128 BASIC PLAY commands
# returns ascii representation of the program
#
# TODOs:
# - Don't hardcode the tempo

import sys
import os
import math
import collections
from fractions import Fraction
#import cbmcodecs
import ctsMidi
from ctsConstants import PITCHES, BASIC_LINE_MAX_C128
from ctsBase import Rest
from ctsChirp import Note
from ctsMChirp import MChirpSong
from ctsErrors import ChiptuneSAKValueError, ChiptuneSAKContentError
import ctsGenPrg

# These types are similar to standard notes and rests but with voice added
BasicNote = collections.namedtuple('BasicNote', ['start_time', 'note_num', 'duration', 'voice'])
BasicRest = collections.namedtuple('BasicRest', ['start_time', 'duration', 'voice'])

# These appear to be the only allowed note durations for C128 BASIC
basic_durations = {
    Fraction(6, 1): "w.", Fraction(4, 1): 'w',
    Fraction(3, 1): 'h.', Fraction(2, 1): 'h',
    Fraction(3, 2): 'q.', Fraction(1, 1): 'q',
    Fraction(3, 4): 'i.', Fraction(1, 2): 'i',
    Fraction(1, 4): 's'
}


def sort_order(c):
    """
    Sort function for measure contents.
    Items are sorted by time and then, for equal times, by duration (decreasing) and voice
    """
    if isinstance(c, BasicNote):
        return (c.start_time, -c.duration, c.voice)
    elif isinstance(c, BasicRest):
        return (c.start_time, -c.duration, c.voice)


def basic_pitch_to_note_name(note_num, octave_offset=-2):
    """
    Gets note name for a given MIDI pitch
    """
    if not 0 <= note_num <= 127:
        raise ChiptuneSAKValueError("Illegal note number %d" % note_num)
    octave = (note_num // 12) + octave_offset
    octave = max(octave, 0)
    octave = min(octave, 6)
    pitch = note_num % 12
    return (PITCHES[pitch][::-1], octave)  # Accidentals come BEFORE note name so reverse standard


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
    Trims the note lengths in a ChirpSong to only those allowed in C128 Basic
    """
    for i_t, t in enumerate(song.tracks):
        for i_n, n in enumerate(t.notes):
            f = Fraction(n.duration / song.metadata.ppq).limit_denominator(8)
            if f not in basic_durations:
                for d in sorted(basic_durations, reverse=True):
                    if f >= d:
                        n.duration = d * song.metadata.ppq
                        break
                song.tracks[i_t].notes[i_n] = n  # Trim the note in place


def measures_to_basic(mchirp_song):
    """
    Converts an MChirpSong to C128 Basic command strings.
    :param mchirp_song:
    :return:
    """
    commands = []
    n_measures = len(mchirp_song.tracks[0].measures)  # in mchirp, all tracks have the same number of measures.
    last_voice = 0
    last_octave = -10
    last_duration = 0
    for im in range(n_measures):
        contents = []
        # Combine events from all three voices into a single list corresponding to the measure
        for v in range(len(mchirp_song.tracks)):
            m = mchirp_song.tracks[v].measures[im]
            # If the voice doesn't have any notes in the measure, just ignore it.
            note_count = sum(1 for e in m.events if isinstance(e, Note))
            if note_count == 0:
                continue

            # Extract the notes and rests and put them into a list.
            for e in m.events:
                if isinstance(e, Note):
                    if not e.tied_to:
                        contents.append(BasicNote(e.start_time, e.note_num, e.duration, v + 1))
                elif isinstance(e, Rest):
                    contents.append(BasicRest(e.start_time, e.duration, v + 1))

        # Use the sort order to sort all the events in the measure
        contents.sort(key=sort_order)
        measure_commands = []
        # Last voice gets reset at the start of each measure.
        last_voice = 0
        for e in contents:
            #  We only care about notes and rests.  For now.
            if isinstance(e, BasicNote):
                d_name = basic_duration_to_name(e.duration, mchirp_song.metadata.ppq)
                note_name, octave = basic_pitch_to_note_name(e.note_num)
                current_command = []  # Build the command for this note
                if e.voice != last_voice:
                    current_command.append(' v%d' % e.voice)
                if octave != last_octave:
                    current_command.append('o%s' % octave)
                if e.duration != last_duration:
                    current_command.append(d_name)
                current_command.append(note_name.lower())
                measure_commands.append(''.join(current_command))
                # Set all the state variables
                last_voice = e.voice
                last_octave = octave
                last_duration = e.duration
            elif isinstance(e, BasicRest):
                d_name = basic_duration_to_name(e.duration, mchirp_song.metadata.ppq)
                current_command = []
                if e.voice != last_voice:
                    current_command.append(' v%d' % e.voice)
                if e.duration != last_duration:
                    current_command.append(d_name)
                current_command.append('r')
                measure_commands.append(''.join(current_command))
                # Set the state variables
                last_voice = e.voice
                last_duration = e.duration

        finished_basic_line = (''.join(measure_commands) + ' m').strip()
        if len(finished_basic_line) > BASIC_LINE_MAX_C128:
            raise ChiptuneSAKContentError("C128 BASIC line too long")
        commands.append(finished_basic_line)

    return commands


def midi_to_C128_BASIC(mchirp_song):
    """
    Convert mchirp into a C128 Basic program that plays the song.
    """
    basic_strings = measures_to_basic(mchirp_song)

    result = []
    current_line = 10
    result.append('%d rem %s' % (current_line, mchirp_song.metadata.name))
    current_line += 10
    # Tempo 1 is slowest, and 255 is fastest
    # TODO: Don't hardcode this value
    result.append('%d tempo 10' % (current_line))

    current_line = 100
    for measure_num, s in enumerate(basic_strings):
        result.append('%d %s$="%s"' % (current_line, num_to_str_name(measure_num), s))
        current_line += 10

    # Here's the envelope commands that would have created the set of defaults:
    """
             n,  A,  D,  S,  R, wf,  pw      instrument

    ENVELOPE 0,  0,  9,  0,  0,  2,  1536    piano
    ENVELOPE 1,  12, 0,  12, 0,  1           accordion
    ENVELOPE 2,  0,  0,  15, 0,  0           calliope
    ENVELOPE 3,  0,  5,  5,  0,  3           drum
    ENVELOPE 4,  9,  4,  4,  0,  0           flute
    ENVELOPE 5,  0,  9,  2,  1,  1           guitar
    ENVELOPE 6,  0,  9,  0,  0,  2,  512     harpsicord
    ENVELOPE 7,  0,  9,  9,  0,  2,  2048    organ
    ENVELOPE 8,  8,  9,  4,  1,  2,  512     trumpet
    ENVELOPE 9,  0,  9,  0,  0,  0           xylophone    
    """

    current_line = 7000  # data might reach line 6740
    # Note: U9 = volume 15
    # TODO: For each voice, provide a way to pick (or override) the default envelopes
    result.append('%d play"u9v1t6v2t0v3t0":rem init instruments' % (current_line))
    current_line += 10

    # Command likely out of scope:
    """
    FILTER [freq] [,lp] [,bp] [,hp] [,res]
       "Xn" in PLAY: Filter on (n=1), off (n=0)
    """

    # Create the PLAY lines at the end (like an orderlist for string patterns)
    # TODO: Can later repeat a measure by PLAYing its string more than once to
    # achieve measure-level compression
    PLAYS_PER_LINE = 8
    line_buf = []
    for measure_num in range(len(basic_strings)):
        if measure_num != 0 and measure_num % PLAYS_PER_LINE == 0:
            result.append('%d %s' % (current_line, ':'.join(line_buf)))
            line_buf = []
            current_line += 10
        line_buf.append("play %s$" % (num_to_str_name(measure_num)))
    if len(line_buf) > 0:
        result.append('%d %s' % (current_line, ':'.join(line_buf)))
        current_line += 10

    # debug = '\n'.join(line.encode('ascii').decode('petscii-c64en-lc') for line in result)
    return '\n'.join(result)


# Convert measure number to a BASIC string name
def num_to_str_name(num, upper=False):
    if num < 0 or num > 675:
        raise ChiptuneSAKValueError("number to convert to str var name out of range")
    if upper:
        offset = ord('A')
    else:
        offset = ord('a')
    str_name = chr((num//26)+offset) + chr((num%26)+offset)
    return str_name


# only for debugging
if __name__ == '__main__':
    pass

