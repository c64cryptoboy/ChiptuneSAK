import copy

from chiptunesak.base import *
from chiptunesak.chirp import Note


# This is not the required version:  use any version >= to this
LP_VERSION = '2.18.2'

# TODO:
# - Refactor common code out of export_clip_to_lilypond and export_song_to_lilypond?

lp_pitches = {
    'sharps': ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"],
    'flats': ["c", "des", "d", "ees", "e", "f", "ges", "g", "aes", "a", "bes", "b"],
}

lp_durations = {
    Fraction(4, 1): '1', Fraction(3, 1): '2.', Fraction(2, 1): '2', Fraction(3, 2): '4.', Fraction(1, 1): '4',
    Fraction(3, 4): '8.', Fraction(1, 2): '8', Fraction(3, 8): '16.', Fraction(1, 4): '16',
    Fraction(3, 16): '32.', Fraction(1, 8): '32', Fraction(3, 32): '64.', Fraction(1, 16): '64'
}


def lp_pitch_to_note_name(note_num, pitches, octave_offset=-3):
    """
    Gets the Lilypond note name for a given pitch.

    :param note_num:       MIDI note number
    :param pitches:        Set of pitches to use (sharp or flat)
    :param octave_offset:  Octave offset (the default is 4, which is the lilypond standard)
    :return:               Lilypond pitch name
    """
    if not 0 <= note_num <= 127:
        raise ChiptuneSAKValueError("Illegal note number %d" % note_num)
    octave_num = ((note_num - constants.C0_MIDI_NUM) // 12) + octave_offset
    if octave_num >= 0:
        octave = "'" * octave_num
    else:
        octave = "," * abs(octave_num)
    pitch = note_num % 12
    return "%s%s" % (pitches[pitch], octave)


def make_lp_notes(note_name, duration, ppq):
    """
    Makes a series of Lilypond notes/rests to fill a specified duration

    :param note_name:  Lilypond note name (from lp_pitch_to_note_name) or 'r' for rest.
    :param duration:   Duration of the note in ppq ticks
    :param ppq:        ppq from the song in which the note exists
    :return:           String representing the notes in Lilypond format
    """
    if duration <= 0:
        raise ChiptuneSAKValueError("Illegal note duration: %d" % duration)
    durs = decompose_duration(duration, ppq, lp_durations)
    if note_name == 'r':
        retval = ' '.join("%s%s" % (note_name, lp_durations[f]) for f in durs)
    else:
        retval = '~ '.join("%s%s" % (note_name, lp_durations[f]) for f in durs)
    return retval


def avg_pitch(track):
    """
    Gives the average pitch for a track

    :param track: an MChirpTrack
    :return: average pitch as MIDI note number
    """
    total = sum(n.note_num for measure in track.measures for n in measure.events if isinstance(n, Note))
    number = sum(1 for measure in track.measures for n in measure.events if isinstance(n, Note))
    if number == 0:
        raise ChiptuneSAKContentError("Track %s has no notes" % track.name)
    return total / number


class Lilypond(ChiptuneSAKIO):
    @classmethod
    def cts_type(cls):
        return 'Lilypond'

    def __init__(self):
        ChiptuneSAKIO.__init__(self)
        self.set_options(format='song')
        self.current_pitch_set = lp_pitches['sharps']
        self.current_clef = 'treble'
        self.current_ottava = 0

    @property
    def format(self):
        return self.get_option('format')[0].lower()

    def to_bin(self, mchirp_song, **kwargs):
        """
        Exports MChirp to lilypond text

        :param mchirp_song: song to export
        :type mchirp_song: MChirpSong
        :return: lilypond text
        :rtype: str

        :keyword options:
            * **format** (string) - format, either 'song' or 'clip'
            * **autosort** (bool) - sort tracks from highest to lowest average pitch
            * **measures** (list) - list of contiguous measures, from one track.
              Required for 'clip' format, ignored otherwise.
        """
        self.set_options(**kwargs)
        if self.format == 'c':
            measures = list(self.get_option('measures', []))
            return self.export_clip_to_lilypond(mchirp_song, measures)
        elif self.format == 's':
            return self.export_song_to_lilypond(mchirp_song)
        else:
            raise ChiptuneSAKValueError(f"Unrecognized format {self.format}")

    def to_file(self, mchirp_song, filename, **kwargs):
        """
        Exports MChirp to lilypond source file

        :param mchirp_song: song to export
        :type mchirp_song: MChirpSong
        :param filename:  filename to write
        :type filename: str
        :return: lilypond text
        :rtype: str

        :keyword options: see to_bin()
        """
        self.set_options(**kwargs)
        with open(filename, 'w') as f:
            f.write(self.to_bin(mchirp_song, **kwargs))

    def clef(self, t_range):
        avg = sum(t_range) / len(t_range)
        clef = self.current_clef
        if self.current_clef == 'treble' and avg < 60:
            clef = 'bass'
        elif self.current_clef == 'bass' and avg > 60:
            clef = 'treble'
        return clef

    def ottava(self, note_num):
        ottava = self.current_ottava
        bass_transitions = (41 - 3 * self.current_ottava, 66 + 3 * self.current_ottava)
        treble_transitions = (55 + 3 * self.current_ottava, 84 - 3 * self.current_ottava)
        if self.current_clef == 'bass':
            if note_num < bass_transitions[0]:
                ottava = -1
            elif note_num > bass_transitions[1]:
                ottava = 1
            else:
                ottava = 0
        else:
            if note_num < treble_transitions[0]:
                ottava = -1
            elif note_num > treble_transitions[1]:
                ottava = 1
            else:
                ottava = 0
        return ottava

    def measure_to_lilypond(self, measure):
        """
        Converts contents of a measure into Lilypond text

        :param measure: A ctsMeasure.Measure object
        :return:        Lilypond text encoding the measure content.
        """
        measure_contents = []
        measure_notes = [e.note_num for e in measure.events if isinstance(e, Note)]
        if len(measure_notes) > 0:
            measure_range = (min(measure_notes), max(measure_notes))
            measure_clef = self.clef(measure_range)
            if measure_clef != self.current_clef:
                self.current_clef = measure_clef
                measure_contents.append("\\clef %s" % self.current_clef)
        for e in measure.events:
            if isinstance(e, Note):
                note_ottava = self.ottava(e.note_num)
                if note_ottava != self.current_ottava:
                    self.current_ottava = note_ottava
                    measure_contents.append("\\ottava #%d" % self.current_ottava)
                f = Fraction(e.duration / self.ppq).limit_denominator(64)
                if f in lp_durations:
                    measure_contents.append(
                        "%s%s%s" % (lp_pitch_to_note_name(e.note_num, self.current_pitch_set),
                                    lp_durations[f], '~' if e.tied_from else ''))
                else:
                    measure_contents.append(make_lp_notes(
                        lp_pitch_to_note_name(e.note_num, self.current_pitch_set),
                        e.duration, self.ppq))

            elif isinstance(e, Rest):
                f = Fraction(e.duration / self.ppq).limit_denominator(64)
                if f in lp_durations:
                    measure_contents.append("r%s" % (lp_durations[f]))
                else:
                    measure_contents.append(make_lp_notes('r', e.duration, self.ppq))

            elif isinstance(e, Triplet):
                measure_contents.append('\\tuplet 3/2 {')
                for te in e.content:
                    if isinstance(te, Note):
                        te_duration = te.duration * Fraction(3 / 2)
                        f = Fraction(te_duration / self.ppq).limit_denominator(64)
                        if f in lp_durations:
                            measure_contents.append(
                                "%s%s%s" % (lp_pitch_to_note_name(te.note_num, self.current_pitch_set),
                                            lp_durations[f], '~' if te.tied_from else ''))
                        else:
                            measure_contents.append(make_lp_notes(
                                lp_pitch_to_note_name(te.note_num, self.current_pitch_set),
                                te_duration, self.ppq))

                    elif isinstance(te, Rest):
                        measure_contents.append(make_lp_notes('r', te.duration * Fraction(3 / 2), self.ppq))

                measure_contents.append('}')

            elif isinstance(e, MeasureMarker):
                measure_contents.append('|')

            elif isinstance(e, TimeSignatureEvent):
                if e.num != self.current_time_signature.num or e.denom != self.current_time_signature.denom:
                    measure_contents.append('\\time %d/%d' % (e.num, e.denom))
                    self.current_time_signature = copy.copy(e)

            elif isinstance(e, KeySignatureEvent):
                if e.key.key_signature != self.current_key_signature:
                    key_name = e.key.key_name
                    self.current_pitch_set = lp_pitches[e.key.accidentals()]
                    key_name = key_name.replace('#', 'is')
                    key_name = key_name.replace('b', 'es')
                    if e.key.key_signature.type == 'minor':
                        measure_contents.append('\\key %s \\minor' % (key_name.lower()[:-1]))
                    else:
                        measure_contents.append('\\key %s \\major' % (key_name.lower()))
                    self.current_key_signature = copy.copy(e.key.key_signature)

        return measure_contents

    def export_clip_to_lilypond(self, mchirp_song, measures):
        """
        Turns a set of measures into Lilypond suitable for use as a clip.  All the music will be on a single line
        with no margins.  It is recommended that this clip be turned into Lilypond using the command line:

        ``lilypond -ddelete-intermediate-files -dbackend=eps -dresolution=600 -dpixmap-format=pngalpha --png <filename>``

        :param mchirp_song: ChirpSong from which the measures were taken.
        :type mchirp_song: MChirpSong
        :param measures: List of measures.
        :type measures: list
        :return: Lilypond markup ascii
        :rtype: str
        """
        if len(measures) < 1:
            raise ChiptuneSAKContentError("No measures to export!")
        # Set these to the default so that they will change on the first measure.
        self.current_time_signature = TimeSignatureEvent(0, 4, 4)
        self.current_key_signature = key.ChirpKey('C').key_signature
        self.current_clef = 'treble'
        self.current_ottava = 0
        self.ppq = mchirp_song.metadata.ppq
        output = []
        ks = mchirp_song.get_key_signature(measures[0].start_time)
        if ks.start_time < measures[0].start_time:
            measures[0].events.insert(0, KeySignatureEvent(measures[0].start_time, ks.key))

        ts = mchirp_song.get_time_signature(measures[0].start_time)
        if ts.start_time < measures[0].start_time:
            measures[0].events.insert(0, TimeSignatureEvent(measures[0].start_time, ts.num, ts.denom))

        output.append('\\version "%s"' % LP_VERSION)
        output.append('''
            \\paper {
            indent=0\\mm line-width=120\\mm oddHeaderMarkup = ##f
            evenHeaderMarkup = ##f oddFooterMarkup = ##f evenFooterMarkup = ##f
            page-breaking = #ly:one-line-breaking }
        ''')
        note_range = (min(e.note_num for m in measures for e in m.events if isinstance(e, Note)),
                      max(e.note_num for m in measures for e in m.events if isinstance(e, Note)))
        self.current_clef = self.clef(note_range)
        self.current_ottava = 0
        output.append('\\new Staff  {')
        output.append('\\clef %s' % self.current_clef)
        for im, m in enumerate(measures):
            measure_contents = self.measure_to_lilypond(m)
            output.append(' '.join(measure_contents))
        output.append('}')
        return '\n'.join(output)

    def export_song_to_lilypond(self, mchirp_song):
        """
        Converts a song to Lilypond format. Optimized for multi-page PDF output of the song.
        Recommended lilypond command:

        ``lilypond <filename>``

        :param mchirp_song: ChirpSong to convert to Lilypond format
        :type mchirp_song: MChirpSong
        :return: Lilypond markup ascii
        :rtype: str
        """

        # Set these to the default, so that they will change on the first measure.
        self.current_time_signature = TimeSignatureEvent(0, 4, 4)
        self.current_key_signature = key.ChirpKey('C').key_signature
        self.current_clef = 'treble'
        self.current_ottava = 0
        self.ppq = mchirp_song.metadata.ppq
        output = []
        output.append('\\version "%s"' % LP_VERSION)
        output.append('\\header {')
        if len(mchirp_song.metadata.name) > 0:
            output.append(' title = "%s"' % mchirp_song.metadata.name)
        output.append('composer = "%s"' % mchirp_song.metadata.composer)
        output.append('}')
        #  ---- end of headers ----
        tracks = [t for t in mchirp_song.tracks]
        if self.get_option('autosort', False):
            tracks = sorted([t for t in mchirp_song.tracks], key=avg_pitch, reverse=True)
        output.append('\\new StaffGroup <<')
        for it, t in enumerate(tracks):
            self.current_time_signature = TimeSignatureEvent(0, 4, 4)
            self.current_key_signature = key.ChirpKey('C').key_signature
            measures = copy.copy(t.measures)
            track_range = (min(e.note_num for m in t.measures for e in m.events if isinstance(e, Note)),
                           max(e.note_num for m in t.measures for e in m.events if isinstance(e, Note)))
            self.current_clef = self.clef(track_range)
            self.current_ottava = 0
            output.append('\\new Staff \\with { instrumentName = #"%s" } {' % t.name)
            output.append('\\clef %s' % self.current_clef)
            for im, m in enumerate(measures):
                output.append("%% measure %d" % (im + 1))
                measure_contents = self.measure_to_lilypond(m)
                output.append(' '.join(measure_contents))
            output.append('\\bar "||"')
            output.append('}')
        output.append('>>\n')
        return '\n'.join(output)
