# Lower MChirp to C128 BASIC PLAY commands

import collections
from chiptunesak import constants
from chiptunesak import base
from chiptunesak import gen_prg
from chiptunesak import chirp
from chiptunesak.errors import ChiptuneSAKValueError, ChiptuneSAKContentError

WHOLE_NOTE = 1152  # counter found in the PLAY routines in the BASIC ROM

# These are the defaults that can be overwritten by the BASIC ENVELOPE command
# Note: waveform (WF) is a little different in the BASIC, it's
#    0=triangle, 1=sawtooth, 2=pulse, 3=noise, and 4=ring modulation
C128_INSTRUMENTS = {
    'piano': 0,         # ADSR  0, 9,  0, 0, WF 2, PW 1536
    'accordion': 1,     # ADSR 12, 0, 12, 0, WF 1
    'calliope': 2,      # ADSR  0, 0, 15, 0, WF 0
    'drum': 3,          # ADSR  0, 5,  5, 0, WF 3
    'flute': 4,         # ADSR  9, 4,  4, 0, WF 0
    'guitar': 5,        # ADSR  0, 9,  2, 1, WF 1
    'harpsichord': 6,   # ADSR  0, 9,  0, 0, WF 2, PW  512
    'organ': 7,         # ADSR  0, 9,  9, 0, WF 2, PW 2048
    'trumpet': 8,       # ADSR  8, 9,  4, 1, WF 2, PW  512
    'xylophone': 9,     # ADSR  0, 9,  0, 0, WF 0
}

# These types are similar to standard notes and rests but with voice added
BasicNote = collections.namedtuple('BasicNote', ['start_time', 'note_num', 'duration', 'voice'])
BasicRest = collections.namedtuple('BasicRest', ['start_time', 'duration', 'voice'])

# These appear to be the only allowed note durations for C128 BASIC
basic_durations = {
    constants.Fraction(6, 1): "w.", constants.Fraction(4, 1): 'w',
    constants.Fraction(3, 1): 'h.', constants.Fraction(2, 1): 'h',
    constants.Fraction(3, 2): 'q.', constants.Fraction(1, 1): 'q',
    constants.Fraction(3, 4): 'i.', constants.Fraction(1, 2): 'i',
    constants.Fraction(1, 4): 's'
}


class C128Basic(base.ChiptuneSAKIO):
    """
    The IO interface for C128BASIC
    Supports to_bin() and to_file() conversions from mchirp to C128 BASIC
    options: format, arch, instruments
    """
    @classmethod
    def cts_type(cls):
        return 'C128Basic'

    def __init__(self):
        base.ChiptuneSAKIO.__init__(self)
        self.set_options(format='prg',
                         arch=constants.DEFAULT_ARCH,
                         instruments=['piano', 'piano', 'piano'])

    def set_options(self, **kwargs):
        """
        Sets the options for commodore export

        :param kwargs: keyword arguments for options
        :type kwargs: keyword arguments
        """
        for op, value in kwargs.items():
            op = op.lower()  # All option names must be lowercase
            if op not in ['arch', 'format', 'instruments', 'tempo_override', 'rem_override']:
                raise ChiptuneSAKValueError(f'Error: unknown option "{op}"')

            if op == 'arch':
                if value not in constants.ARCH.keys():
                    raise ChiptuneSAKValueError(f"Error: Invalid architecture setting {value}")
            elif op == 'format':
                if value == 'ascii':
                    value = 'bas'
                if value not in ['prg', 'bas']:
                    ChiptuneSAKValueError(f"Error: Invalid format setting {value}")
            elif op == 'instruments':
                if len(value) != 3:
                    raise ChiptuneSAKValueError("Error: 3 instruments required for C128")
                value = [v.lower() for v in value]
                if any(v not in C128_INSTRUMENTS for v in value):
                    raise ChiptuneSAKValueError("Error: Illegal instrument name(s)")
            elif op == 'tempo_override':
                if not 1 <= value <= 255:
                    # Note: some Commodore manuals erroneously show 0 as the slowest
                    # tempo.  "TEMPO 0" will throw a BASIC illegal quantity error.
                    raise ChiptuneSAKContentError("Error: tempo must be between 1 and 255")
            elif op == 'rem_override':
                value = value[:72].lower()

            self._options[op] = value

    def to_bin(self, mchirp_song, **kwargs):
        """
        Convert an MChirpSong into a C128 BASIC music program

        :param mchirp_song: mchirp data
        :type mchirp_song: MChirpSong
        :return: C128 BASIC program
        :rtype: str or bytearray

        :keyword options:  see `to_file()`
        """
        self.set_options(**kwargs)
        if mchirp_song.cts_type() != 'MChirp':
            raise Exception("Error: C128Basic to_bin() only supports mchirp so far")

        ascii_prog = self.export_mchirp_to_C128_BASIC(mchirp_song)

        if self.get_option('format') == 'bas':
            return ascii_prog

        tokenized_program = gen_prg.ascii_to_prg_c128(ascii_prog)
        return tokenized_program

    def to_file(self, mchirp_song, filename, **kwargs):
        """
        Converts and saves MChirpSong as a C128 BASIC music program

        :param mchirp_song: mchirp data
        :type mchirp_song: MChirpSong
        :param filename: path and filename
        :type filename: str

        :keyword options:
            * **arch** (str) - architecture name (see base for complete list)

            * **format** (str) - 'bas' for BASIC source code or 'prg' for prg

            * **instruments** (list of str) - list of 3 instruments for the three voices (in order).

                - Default is ['piano', 'piano', 'piano']
                - Supports the default C128 BASIC instruments:
                  0:'piano', 1:'accordion', 2:'calliope', 3:'drum', 4:'flute',
                  5:'guitar', 6:'harpsichord', 7:'organ', 8:'trumpet', 9:'xylophone

            * **tempo_override** (int) - override the computed tempo

            * **rem_override** (string) - use passed string for leading REM statement instead of filename
        """
        prog = self.to_bin(mchirp_song, **kwargs)

        if self.get_option('format') == 'bas':
            with open(filename, 'w') as out_file:
                out_file.write(prog)
        else:  # 'prg'
            with open(filename, 'wb') as out_file:
                out_file.write(prog)

    def export_mchirp_to_C128_BASIC(self, mchirp_song):
        """
        Convert mchirp into a C128 Basic program that plays the song.
        This method is invoked via the C128Basic ChiptuneSAKIO class

        :param mchirp_song: An mchirp song
        :type mchirp_song: MChirpSong
        :return: Returns an ascii BASIC program
        :rtype: str
        """
        basic_strings = measures_to_basic(mchirp_song)

        result = []
        current_line = 10

        if self.get_option('rem_override'):
            rem_desc = self.get_option('rem_override')
        else:
            rem_desc = mchirp_song.metadata.name.lower()

        result.append('%d rem %s' % (current_line, rem_desc))
        current_line += 10

        # Tempo 1 is slowest, and 255 is fastest
        if self.get_option('tempo_override'):
            tempo = self.get_option('tempo_override')
        else:
            tempo = (mchirp_song.metadata.qpm * WHOLE_NOTE
                     / constants.ARCH[self.get_option('arch')].frame_rate / 60 / 4)
            tempo = int(round(tempo))

        result.append('%d tempo %d' % (current_line, tempo))

        current_line = 100
        for measure_num, s in enumerate(basic_strings):
            tmp_line = '%d %s$="%s"' % (current_line, num_to_str_name(measure_num), s)
            if len(tmp_line) >= constants.BASIC_LINE_MAX_C128:
                # it's ok if space removed between line number and first character
                tmp_line = tmp_line.replace(" ", "")
                # If the line is still too long...
                if len(tmp_line) >= constants.BASIC_LINE_MAX_C128:
                    raise ChiptuneSAKContentError(
                        "C128 BASIC line too long: Line %d length %d" % (current_line, len(tmp_line)))
            result.append(tmp_line)

            current_line += 10

        current_line = 7000  # data might reach line 6740
        volume = 9
        # FUTURE: For each voice, provide a way to pick (or override) the default envelopes
        instr_assign = 'u%dv1t%dv2t%dv3t%d' % \
            (volume, *(C128_INSTRUMENTS[inst] for inst in self.get_option('instruments')))
        result.append('%d play"%s":rem init instruments' % (current_line, instr_assign))
        current_line += 10

        # FUTURE: Using FILTER command likely out of scope, but could be added as another option:
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

        return '\n'.join(result)


def sort_order(c):
    """
    Sort function for measure contents.
    Items are sorted by time and then, for equal times, by duration (decreasing) and voice

    :return: 3-tuple used for sorting
    :rtype: tuple
    """
    if isinstance(c, BasicNote):
        return (c.start_time, -c.duration, c.voice)
    elif isinstance(c, BasicRest):
        return (c.start_time, -c.duration, c.voice)


def pitch_to_basic_note_name(note_num, octave_offset=0):
    """
    Gets note name for a given MIDI pitch

    :return: note name string and octave number
    :rtype: str, int
    """
    note_name = base.pitch_to_note_name(note_num)[::-1]  # Reverse the note name
    return note_name[1:], note_name[0]


def duration_to_basic_name(duration, ppq):
    """
    Gets a note duration name for a given duration.

    :param duration: duration
    :type duration: int
    :param ppq: ppq (midi pulses per quarter note)
    :type ppq: int
    :return: C128 BASIC name for the duration
    :rtype: str
    """
    f = constants.Fraction(duration / ppq).limit_denominator(16)
    if f not in basic_durations:
        raise ChiptuneSAKValueError("Illegal note duration %s" % str(f))
    return basic_durations[f]


def trim_note_lengths(song):
    """
    Trims the note lengths in a ChirpSong to only those allowed in C128 Basic
    """
    for i_t, t in enumerate(song.tracks):
        for i_n, n in enumerate(t.notes):
            f = constants.Fraction(n.duration / song.metadata.ppq).limit_denominator(8)
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
            note_count = sum(1 for e in m.events if isinstance(e, chirp.Note))
            if note_count == 0:
                continue

            # Extract the notes and rests and put them into a list.
            for e in m.events:
                if isinstance(e, chirp.Note):
                    if not e.tied_to:
                        start_time = e.start_time
                        for d in base.decompose_duration(e.duration, ppq, basic_durations):
                            contents.append(BasicNote(start_time, e.note_num, d * ppq, v + 1))
                            start_time += d * ppq
                    else:
                        start_time = e.start_time
                        for d in base.decompose_duration(e.duration, ppq, basic_durations):
                            contents.append(BasicRest(start_time, d * ppq, v + 1))
                            start_time += d * ppq
                elif isinstance(e, base.Rest):
                    start_time = e.start_time
                    for d in base.decompose_duration(e.duration, ppq, basic_durations):
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
                d_name = duration_to_basic_name(e.duration, mchirp_song.metadata.ppq)
                note_name, octave = pitch_to_basic_note_name(e.note_num)
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
                d_name = duration_to_basic_name(e.duration, mchirp_song.metadata.ppq)
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


def num_to_str_name(num, upper=False):
    """
    Convert measure number to a BASIC variable name

    :param num: index for a BASIC variable name
    :type num: int
    :param upper: return upper case, defaults to False
    :type upper: bool, optional
    :return: C128 BASIC variable name
    :rtype: str
    """
    if num < 0 or num > 675:
        raise ChiptuneSAKValueError("number to convert to str var name out of range")
    if upper:
        offset = ord('A')
    else:
        offset = ord('a')
    str_name = chr((num // 26) + offset) + chr((num % 26) + offset)
    return str_name
