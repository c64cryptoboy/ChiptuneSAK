import sys
import os
import sandboxPath

from ctsErrors import *
import ctsConstants
import ctsSong
from fractions import Fraction
from ctsExportUtil import populate_measures

import more_itertools as moreit

lp_pitches = ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"]

lp_durations = {
    Fraction(4, 1):'1', Fraction(3, 1):'2.', Fraction(2, 1):'2', Fraction(3, 2):'4.', Fraction(1, 1):'4',
    Fraction(3, 4):'8.', Fraction(1, 2):'8', Fraction(3, 8):'16.', Fraction(1, 4):'16',
    Fraction(3, 16):'32.', Fraction(1, 8):'32', Fraction(3, 32):'64.', Fraction(1, 16):'64'
}


def lp_pitch_to_note_name(note_num, octave_offset=4):
    """
    Gets note name for a given MIDI pitch
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
    durs = []
    remainder = duration
    while remainder > 0:
        if remainder < min(lp_durations):
            raise ChiptuneSAKValueError("Illegal duration: %d (ppq = %d)" % (remainder, ppq))
        for f in sorted(lp_durations, reverse=True):
            if remainder >= f * ppq:
                durs.append(f)
                remainder -= f * ppq
                break
    if note_name == 'r':
        return ' '.join("%s%s" % (note_name, lp_durations[f]) for f in durs)
    return '~ '.join("%s%s" % (note_name, lp_durations[f]) for f in durs)


def song_to_lilypond(song, format='full'):
    output = []
    if not song.is_quantized():
        raise ChiptuneSAKQuantizationError("Song must be quantized for export to Lilypond")
    if song.is_polyphonic():
        raise ChiptuneSAKPolyphonyError("All tracks must be non-polyphonic for export to Lilypond")

    output.append('\\version "2.18.2"')
    format = format.lower()
    if format == 'full':
        pass
    elif format == 'png':
        output.append('''
            \\paper { 
            indent=0\\mm line-width=120\\mm oddHeaderMarkup = ##f
            evenHeaderMarkup = ##f oddFooterMarkup = ##f evenFooterMarkup = ##f 
            page-breaking = #ly:one-line-breaking }
        ''')
    else:
        raise ChiptuneSAKValueError("Unknown format " + format)
    if len(song.name) > 0:
        output.append('\\header { title = "%s" }' % song.name)
    output.append('\\new StaffGroup <<')
    for it, t in enumerate(song.tracks):
        measures = populate_measures(song, t)
        track_range = (min(n.note_num for n in t.notes), max(n.note_num for n in t.notes))
        output.append('\\new Staff \\with { instrumentName = #"%s" } {' % t.name)
        if track_range[0] < 48:
            output.append('\\clef bass')
        for im, m in enumerate(measures):
            measure_contents = []
            output.append("%% measure %d" % (im + 1))
            for e in m:
                if isinstance(e, ctsSong.Note):
                    f = Fraction(e.duration / song.ppq).limit_denominator(64)
                    if f in lp_durations:
                        measure_contents.append("%s%s%s" % (lp_pitch_to_note_name(e.note_num), lp_durations[f], '~' if e.tied else ''))
                    else:
                        measure_contents.append(make_lp_notes(lp_pitch_to_note_name(e.note_num), e.duration, song.ppq))

                elif isinstance(e, ctsSong.Rest):
                    f = Fraction(e.duration / song.ppq).limit_denominator(64)
                    if f in lp_durations:
                        measure_contents.append("r%s" % (lp_durations[f]))
                    else:
                        measure_contents.append(make_lp_notes('r', e.duration, song.ppq))

                elif isinstance(e, ctsSong.TimeSignature):
                    measure_contents.append('\\time %d/%d' % (e.num, e.denom))

                elif isinstance(e, ctsSong.KeySignature):
                    key = e.key
                    key.replace('#', 'is')
                    key.replace('b', 'es')
                    measure_contents.append('\\key %s \\major' % (key.lower()))

            measure_contents.append('|')
            output.append(' '.join(measure_contents))
        output.append('}')
    output.append('>>\n')

    return '\n'.join(output)


if __name__ == '__main__':
    import subprocess
    in_filename = '../test/bach_invention_4.mid'
    song = ctsSong.Song(in_filename)
    song.remove_control_notes()
    song.estimate_quantization()
    song.quantize()
    song.remove_polyphony()
    song.export_midi('../test/bach_invention_4a.mid')
    out = song_to_lilypond(song, 'full')
    os.chdir('../Test/temp')
    out_filename = 'bach_invention_4.ly'
    with open(out_filename, 'w') as f:
        f.write(out)
    # TODO:  Put this functionality into a function and move all the files to a temp directory
    #subprocess.call('lilypond -ddelete-intermediate-files -dbackend=eps -dresolution=600 --png %s' % out_filename, shell=True)
    subprocess.call('lilypond %s' % out_filename, shell=True)
