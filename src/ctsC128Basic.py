# Lower MChirp to C128 BASIC PLAY commands
# returns ascii representation of the program
#
# TODOs:
# - 

import collections
from ctsConstants import *
from ctsBase import Rest, decompose_duration, note_name_to_pitch
from ctsChirp import Note
from ctsErrors import ChiptuneSAKValueError, ChiptuneSAKContentError

WHOLE_NOTE = 1152 # counter found in the PLAY routines in the BASIC ROM

# Note: waveform (WF) is a little different in the BASIC, it's
#    0=triangle, 1=sawtooth, 2=pulse, 3=noise, and 4=ring modulation
C128_INSTRUMENTS = {
    'piano': 0,         # ADSR 0,9,0,0, WF 2, PW 1536
    'accordion': 1,     # ADSR 12,0,12,0, WF 1 
    'calliope': 2,      # ADSR 0,0,15,0, WF 0
    'drum': 3,          # ADSR 0,5,5,0, WF 3
    'flute': 4,         # ADSR 9,4,4,0, WF 0
    'guitar': 5,        # ADSR 0,9,2,1, WF 1
    'harpsichord': 6,   # ADSR 0,9,0,0, WF 2, PW 512
    'organ': 7,         # ADSR 0,9,9,0, WF 2, PW 2048
    'trumpet': 8,       # ADSR 8,9,4,1, WF 2, PW 512
    'xylophone': 9,     # ADSR 0,9,0,0, WF 0
}

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


def basic_pitch_to_note_name(note_num, octave_offset=0):
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
    f = Fraction(duration/ppq).limit_denominator(16)
    if f not in basic_durations:
        raise ChiptuneSAKValueError("Illegal note duration %s" % str(f))
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
    ppq = mchirp_song.metadata.ppq
    for im in range(n_measures):
        contents = []
        # Combine events from all three voices into a single list corresponding to the measure
        for v in range(min(3, len(mchirp_song.tracks))):
            m = mchirp_song.tracks[v].measures[im]
            # If the voice doesn't have any notes in the measure, just ignore it.
            note_count = sum(1 for e in m.events if isinstance(e, Note))
            if note_count == 0:
                continue

            # Extract the notes and rests and put them into a list.
            for e in m.events:
                if isinstance(e, Note):
                    if not e.tied_to:
                        start_time = e.start_time
                        for d in decompose_duration(e.duration, ppq, basic_durations):
                            contents.append(BasicNote(start_time, e.note_num, d * ppq, v + 1))
                            start_time += d * ppq
                    else:
                        start_time = e.start_time
                        for d in decompose_duration(e.duration, ppq, basic_durations):
                            contents.append(BasicRest(start_time, d * ppq, v + 1))
                            start_time += d * ppq
                elif isinstance(e, Rest):
                    start_time = e.start_time
                    for d in decompose_duration(e.duration, ppq, basic_durations):
                        contents.append(BasicRest(start_time, d * ppq, v + 1))
                        start_time += d * ppq

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
        commands.append(finished_basic_line)

    return commands


def midi_to_C128_BASIC(mchirp_song, instrum=('piano', 'piano', 'piano'), arch='NTSC'):
    """
    Convert mchirp into a C128 Basic program that plays the song.

    :param mchirp_song: An mchirp song
    :type mchirp_song: MChirpSong
    :param instrum: tuple of instrument string names, defaults to ('piano', 'piano', 'piano')
    :type instrum: tuple, optional
    :param arch: Commodore architecture, defaults to 'NTSC'
    :type arch: str, optional
    :raises ChiptuneSAKContentError: Various content errors
    :raises ChiptuneSAKValueError: Various value errors
    :return: Returns a binary BASIC file
    :rtype: bytes
    """
    basic_strings = measures_to_basic(mchirp_song)

    result = []
    current_line = 10
    result.append('%d rem %s' % (current_line, mchirp_song.metadata.name))
    current_line += 10
    # Tempo 1 is slowest, and 255 is fastest
    tempo = mchirp_song.metadata.qpm * WHOLE_NOTE / ARCH[arch].frame_rate / 60 / 4
    tempo = int(tempo + 0.5)
    result.append('%d tempo %d' % (current_line, tempo))

    current_line = 100
    for measure_num, s in enumerate(basic_strings):
        tmp_line = '%d %s$="%s"' % (current_line, num_to_str_name(measure_num), s)
        if len(tmp_line) >= BASIC_LINE_MAX_C128:
            # it's ok if space removed between line number and first character
            tmp_line = tmp_line.replace(" ", "")
            # If the line is still too long...
            if len(tmp_line) >= BASIC_LINE_MAX_C128:
                raise ChiptuneSAKContentError(
                    "C128 BASIC line too long: Line %d length %d" % (current_line, len(tmp_line)))
        result.append(tmp_line)

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
    ENVELOPE 6,  0,  9,  0,  0,  2,  512     harpsichord
    ENVELOPE 7,  0,  9,  9,  0,  2,  2048    organ
    ENVELOPE 8,  8,  9,  4,  1,  2,  512     trumpet
    ENVELOPE 9,  0,  9,  0,  0,  0           xylophone    
    """

    current_line = 7000  # data might reach line 6740
    # Note: U9 = volume 15
    volume = 9
    # TODO: For each voice, provide a way to pick (or override) the default envelopes
    instruments = 'u%dv1t%dv2t%dv3t%d' % (volume, *(C128_INSTRUMENTS[inst] for inst in instrum))
    result.append('%d play"%s":rem init instruments' % (current_line, instruments))
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
    str_name = chr((num // 26)+offset) + chr((num % 26)+offset)
    return str_name
