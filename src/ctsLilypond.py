import sys
import os
import copy
from fractions import Fraction

from ctsErrors import *
from ctsKey import ChirpKey
from ctsBase import *
from ctsChirp import ChirpSong, Note
from ctsMChirp import MChirpSong
import ctsMidi

lp_pitches = {'sharps': ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"],
              'flats':  ["c", "des", "d", "ees", "e", "f", "ges", "g", "aes", "a", "bes", "b"]
              }

lp_durations = {
    Fraction(4, 1): '1', Fraction(3, 1): '2.', Fraction(2, 1): '2', Fraction(3, 2): '4.', Fraction(1, 1):'4',
    Fraction(3, 4): '8.', Fraction(1, 2): '8', Fraction(3, 8): '16.', Fraction(1, 4): '16',
    Fraction(3, 16): '32.', Fraction(1, 8): '32', Fraction(3, 32): '64.', Fraction(1, 16): '64'
}

current_pitch_set = lp_pitches['sharps']
current_clef = 'treble'
current_ottava = 0

def lp_pitch_to_note_name(note_num, pitches, octave_offset=3):
    """
    Gets the Lilypond note name for a given pitch.
        :param note_num:       MIDI note number
        :param pitches:        Set of pitches to use (sharp or flat)
        :param octave_offset:  Octave offset (the default is 4, which is the lilypond standard)
        :return:               Lilypond pitch name
    """
    if not 0 <= note_num <= 127:
        raise ChiptuneSAKValueError("Illegal note number %d" % note_num)
    octave_num = ((note_num - C0_MIDI_NUM) // 12) - octave_offset
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

def clef(t_range, current_clef):
    avg = sum(t_range) / len(t_range)
    clef = current_clef
    if current_clef == 'treble' and avg < 60:
        clef = 'bass'
    elif current_clef == 'bass' and avg > 60:
        clef = 'treble'
    return clef

def ottava(note_num, clef, current_ottava):
    ottava = current_ottava
    bass_transitions = (41 - 3*current_ottava, 66 + 3*current_ottava)
    treble_transitions = (55 + 3*current_ottava, 84 - 3*current_ottava)
    if clef == 'bass':
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


def measure_to_lilypond(measure, ppq):
    """
    Converts contents of a measure into Lilypond text
        :param measure: A ctsMeasure.Measure object
        :param ppq:     ppq from the song that made the measure.
        :return:        Lilypond text encoding the measure content.
    """
    global current_pitch_set, current_clef, current_ottava
    global current_key_signature, current_time_signature
    measure_contents = []
    measure_notes = [e.note_num for e in measure.events if isinstance(e, Note)]
    if len(measure_notes) > 0:
        measure_range = (min(measure_notes), max(measure_notes))
        measure_clef = clef(measure_range, current_clef)
        if measure_clef != current_clef:
            current_clef = measure_clef
            measure_contents.append("\\clef %s" % current_clef)
    for e in measure.events:
        if isinstance(e, Note):
            note_ottava = ottava(e.note_num, current_clef, current_ottava)
            if note_ottava != current_ottava:
                current_ottava = note_ottava
                measure_contents.append("\\ottava #%d" % current_ottava)
            f = Fraction(e.duration / ppq).limit_denominator(64)
            if f in lp_durations:
                measure_contents.append(
                    "%s%s%s" % (lp_pitch_to_note_name(e.note_num, current_pitch_set),
                                lp_durations[f], '~' if e.tied_from else ''))
            else:
                measure_contents.append(make_lp_notes(lp_pitch_to_note_name(e.note_num, current_pitch_set),
                                                      e.duration, ppq))

        elif isinstance(e, Rest):
            f = Fraction(e.duration / ppq).limit_denominator(64)
            if f in lp_durations:
                measure_contents.append("r%s" % (lp_durations[f]))
            else:
                measure_contents.append(make_lp_notes('r', e.duration, ppq))

        elif isinstance(e, Triplet):
            measure_contents.append('\\tuplet 3/2 {')
            for te in e.content:
                if isinstance(te, Note):
                    measure_contents.append(make_lp_notes(lp_pitch_to_note_name(te.note_num, current_pitch_set),
                                            te.duration * Fraction(3/2), ppq))
                elif isinstance(te, Rest):
                    measure_contents.append(make_lp_notes('r', te.duration * Fraction(3 / 2), ppq))

            measure_contents.append('}')

        elif isinstance(e, MeasureMarker):
            measure_contents.append('|')

        elif isinstance(e, TimeSignatureEvent):
            if e.num != current_time_signature.num or e.denom != current_time_signature.denom:
                measure_contents.append('\\time %d/%d' % (e.num, e.denom))
                current_time_signature = copy.copy(e)

        elif isinstance(e, KeySignatureEvent):
            if e.key.key_signature != current_key_signature:
                key_name = e.key.key_name
                current_pitch_set = lp_pitches[e.key.accidentals()]
                key_name = key_name.replace('#', 'is')
                key_name = key_name.replace('b', 'es')
                if e.key.key_signature.type == 'minor':
                    measure_contents.append('\\key %s \\minor' % (key_name.lower()[:-1]))
                else:
                    measure_contents.append('\\key %s \\major' % (key_name.lower()))
                current_key_signature = copy.copy(e.key.key_signature)

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
    global current_pitch_set, current_clef, current_ottava
    global current_key_signature, current_time_signature
    # Set these to the default so that they will change on the first measure.
    current_time_signature = TimeSignatureEvent(0, 4, 4)
    current_key_signature = ChirpKey('C').key_signature
    output = []
    ks = mchirp_song.get_key_signature(measures[0].start_time)
    if ks.start_time < measures[0].start_time:
        measures[0].events.insert(0, KeySignatureEvent(measures[0].start_time, ks.key))

    ts = mchirp_song.get_time_signature(measures[0].start_time)
    if ts.start_time < measures[0].start_time:
        measures[0].events.insert(0, TimeSignatureEvent(measures[0].start_time, ts.num, ts.denom))

    output.append('\\version "2.18.2"')
    output.append('''
        \\paper { 
        indent=0\\mm line-width=120\\mm oddHeaderMarkup = ##f
        evenHeaderMarkup = ##f oddFooterMarkup = ##f evenFooterMarkup = ##f 
        page-breaking = #ly:one-line-breaking }
    ''')
    note_range = (min(e.note_num for m in measures for e in m.events if isinstance(e, Note)),
                  max(e.note_num for m in measures for e in m.events if isinstance(e, Note)))
    current_clef = clef(note_range, 'treble')
    current_ottava = 0
    output.append('\\new Staff  {')
    output.append('\\clef %s' % current_clef)
    for im, m in enumerate(measures):
        measure_contents = measure_to_lilypond(m, mchirp_song.metadata.ppq)
        output.append(' '.join(measure_contents))
    output.append('}')
    return '\n'.join(output)


def song_to_lilypond(mchirp_song, auto_sort=False):
    """
    Converts a song to Lilypond format. Optimized for multi-page PDF output of the song.
    Recommended lilypond command:

    lilypond <filename>

        :param mchirp_song:    ChirpSong to convert to Lilypond format
        :return:        Lilypond text for the song.
    """
    global current_pitch_set, current_clef, current_ottava
    global current_key_signature, current_time_signature
    # Set these to the default, so that they will change on the first measure.
    current_time_signature = TimeSignatureEvent(0, 4, 4)
    current_key_signature = ChirpKey('C').key_signature
    current_pitch_set = lp_pitches['sharps']  # default is sharps
    output = []
    output.append('\\version "2.18.2"')
    output.append('\\header {')
    if len(mchirp_song.metadata.name) > 0:
        output.append(' title = "%s"' % mchirp_song.metadata.name)
    output.append('composer = "%s"' % mchirp_song.metadata.composer)
    output.append('}')
    #  ---- end of headers ----
    tracks = [t for t in mchirp_song.tracks]
    if auto_sort:
        tracks = sorted([t for t in mchirp_song.tracks], key=avg_pitch, reverse=True)
    output.append('\\new StaffGroup <<')
    for it, t in enumerate(tracks):
        measures = copy.copy(t.measures)
        track_range = (min(e.note_num for m in t.measures for e in m.events if isinstance(e, Note)),
                       max(e.note_num for m in t.measures for e in m.events if isinstance(e, Note)))
        current_clef = clef(track_range, 'treble')
        current_ottava = 0
        output.append('\\new Staff \\with { instrumentName = #"%s" } {' % t.name)
        output.append('\\clef %s' % current_clef)
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
    estimated_q = song.estimate_quantization()
    print(estimated_q)
    song.quantize(*estimated_q)
    song.remove_polyphony()
    # ctsMidi.chirp_to_midi(song, '../test/data/tripletTest_q.mid')
    m_song = MChirpSong(song)
    out = song_to_lilypond(m_song, auto_sort=True)
    os.chdir('../test/temp')
    out_filename = os.path.splitext(os.path.split(in_filename)[1])[0] + '.ly'
    with open(out_filename, 'w') as f:
        f.write(out)
    # TODO:  Put this functionality into a function and move all the files to a temp directory
    #subprocess.call('lilypond -ddelete-intermediate-files -dbackend=eps -dresolution=600 --png %s' % out_filename, shell=True)
    subprocess.call('lilypond %s' % out_filename, shell=True)
