import sys
import os
import copy
from fractions import Fraction

from ctsErrors import *
from ctsBase import *
from ctsChirp import ChirpSong, Note
from ctsMChirp import MChirpSong
import ctsMidi

lp_pitches = ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"]

lp_durations = {
    Fraction(4, 1): '1', Fraction(3, 1): '2.', Fraction(2, 1): '2', Fraction(3, 2): '4.', Fraction(1, 1):'4',
    Fraction(3, 4): '8.', Fraction(1, 2): '8', Fraction(3, 8): '16.', Fraction(1, 4): '16',
    Fraction(3, 16): '32.', Fraction(1, 8): '32', Fraction(3, 32): '64.', Fraction(1, 16): '64'
}


def lp_pitch_to_note_name(note_num, octave_offset=4):
    """
    Gets the Lilypond note name for a given pitch.
        :param note_num:       MIDI note number
        :param octave_offset:  Octave offset (the default is 4, which is the lilypond standard)
        :return:               Lilypond pitch name
    """
    if not 0 <= note_num <= 127:
        raise ChiptuneSAKValueError("Illegal note number %d" % note_num)
    octave_num = (note_num // 12) - octave_offset
    if octave_num >= 0:
        octave = "'" * octave_num
    else:
        octave = "," * abs(octave_num)
    pitch = note_num % 12
    return "%s%s" % (lp_pitches[pitch], octave)


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
    durs = []
    remainder = duration
    min_duration = int(min(lp_durations) * ppq)
    while remainder > 0:
        if remainder < min_duration:
            raise ChiptuneSAKValueError("Illegal duration: %d (min allowed = %d)" % (remainder, min_duration))
        for f in sorted(lp_durations, reverse=True):
            if remainder >= f * ppq:
                durs.append(f)
                remainder -= f * ppq
                break
    if note_name == 'r':
        retval = ' '.join("%s%s" % (note_name, lp_durations[f]) for f in durs)
    else:
        retval = '~ '.join("%s%s" % (note_name, lp_durations[f]) for f in durs)
    return retval

def measure_to_lilypond(measure, ppq):
    """
    Converts contents of a measure into Lilypond text
        :param measure: A ctsMeasure.Measure object
        :param ppq:     ppq from the song that made the measure.
        :return:        Lilypond text encoding the measure content.
    """
    measure_contents = []
    current_time_signature = TimeSignature(0, 4, 4)
    current_key_signature = KeySignature(0, "C")
    for e in measure.events:
        if isinstance(e, Note):
            f = Fraction(e.duration / ppq).limit_denominator(64)
            if f in lp_durations:
                measure_contents.append(
                    "%s%s%s" % (lp_pitch_to_note_name(e.note_num), lp_durations[f], '~' if e.tied else ''))
            else:
                measure_contents.append(make_lp_notes(lp_pitch_to_note_name(e.note_num), e.duration, song.metadata.ppq))

        elif isinstance(e, Rest):
            f = Fraction(e.duration / song.metadata.ppq).limit_denominator(64)
            if f in lp_durations:
                measure_contents.append("r%s" % (lp_durations[f]))
            else:
                measure_contents.append(make_lp_notes('r', e.duration, song.metadata.ppq))

        elif isinstance(e, MeasureMarker):
            measure_contents.append('|')

        elif isinstance(e, TimeSignature):
            if e.num != current_time_signature.num or e.denom != current_time_signature.denom:
                measure_contents.append('\\time %d/%d' % (e.num, e.denom))
                current_time_signature = copy.copy(e)

        elif isinstance(e, KeySignature):
            if e.key != current_key_signature.key:
                key = e.key
                key.replace('#', 'is')
                key.replace('b', 'es')
                if key[-1] == 'm':
                    measure_contents.append('\\key %s \\minor' % (key.lower()[:-1]))
                else:
                    measure_contents.append('\\key %s \\major' % (key.lower()))
                current_key_signature = copy.copy(e)

    return measure_contents


def clip_to_lilypond(mchirp_song, measures):
    """
    Turns a set of measures into Lilypond suitable for use as a clip.  All the music will be on a single line
    with no margins.  It is recommended that this clip be turned into Lilypond using the command line:

    lilypond -ddelete-intermediate-files -dbackend=eps -dresolution=600 -dpixmap-format=pngalpha --png <filename>

        :param mchirp_song:     ChirpSong from which the measures were taken.
        :param measures: List of measures.
        :return:         Lilypond text.
    """
    output = []
    ks = mchirp_song.get_key_signature(measures[0].start_time)
    if ks.start_time < measures[0].start_time:
        measures[0].events.insert(0, KeySignature(measures[0].start_time, ks.key))

    ts = mchirp_song.get_time_signature(measures[0].start_time)
    if ts.start_time < measures[0].start_time:
        measures[0].events.insert(0, TimeSignature(measures[0].start_time, ts.num, ts.denom))

    output.append('\\version "2.18.2"')
    output.append('''
        \\paper { 
        indent=0\\mm line-width=120\\mm oddHeaderMarkup = ##f
        evenHeaderMarkup = ##f oddFooterMarkup = ##f evenFooterMarkup = ##f 
        page-breaking = #ly:one-line-breaking }
    ''')
    note_range = (min(e.note_num for m in measures for e in m.events if isinstance(e, Note)),
                  max(e.note_num for m in measures for e in m.events if isinstance(e, Note)))
    output.append('\\new Staff  {')
    if note_range[0] < 48:
        output.append('\\clef bass')
    for im, m in enumerate(measures):
        measure_contents = measure_to_lilypond(m, mchirp_song.metadata.ppq)
        output.append(' '.join(measure_contents))
    output.append('}')
    return '\n'.join(output)


def song_to_lilypond(mchirp_song):
    """
    Converts a song to Lilypond format. Optimized for multi-page PDF output of the song.
    Recommended lilypond command:

    lilypond <filename>

        :param mchirp_song:    ChirpSong to convert to Lilypond format
        :return:        Lilypond text for the song.
    """
    output = []
    output.append('\\version "2.18.2"')
    output.append('\\header {')
    if len(mchirp_song.metadata.name) > 0:
        output.append(' title = "%s"' % mchirp_song.metadata.name)
    output.append('composer = "%s"' % mchirp_song.metadata.composer)
    output.append('}')
    #  ---- end of headers ----
    output.append('\\new StaffGroup <<')
    for it, t in enumerate(mchirp_song.tracks):
        measures = copy.copy(t.measures)
        track_range = (min(e.note_num for m in t.measures for e in m.events if isinstance(e, Note)),
                       max(e.note_num for m in t.measures for e in m.events if isinstance(e, Note)))
        output.append('\\new Staff \\with { instrumentName = #"%s" } {' % t.name)
        if track_range[0] < 48:
            output.append('\\clef bass')
        for im, m in enumerate(measures):
            output.append("%% measure %d" % (im + 1))
            measure_contents = measure_to_lilypond(m, mchirp_song.metadata.ppq)
            output.append(' '.join(measure_contents))
        output.append('\\bar "||"')
        output.append('}')
    output.append('>>\n')
    return '\n'.join(output)


if __name__ == '__main__':
    import subprocess
    in_filename = sys.argv[1]
    song = ctsMidi.midi_to_chirp(in_filename)
    song.remove_control_notes()
    song.quantize_from_note_name('32')
    song.remove_polyphony()
    m_song = MChirpSong(song)
    out = song_to_lilypond(m_song)
    os.chdir('../test/temp')
    out_filename = os.path.splitext(os.path.split(in_filename)[1])[0] + '.ly'
    with open(out_filename, 'w') as f:
        f.write(out)
    # TODO:  Put this functionality into a function and move all the files to a temp directory
    #subprocess.call('lilypond -ddelete-intermediate-files -dbackend=eps -dresolution=600 --png %s' % out_filename, shell=True)
    subprocess.call('lilypond %s' % out_filename, shell=True)
