import sys
import sandboxPath
import copy

from ctsErrors import *
import ctsConstants
import ctsSong
from fractions import Fraction
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



def make_measures(song, track):
    def sort_order(c):
        if isinstance(c, ctsSong.Note):
            return (c.start_time, 10)
        elif isinstance(c, ctsSong.Rest):
            return (c.start_time, 10)
        elif isinstance(c, ctsSong.TimeSignature):
            return (c.start_time, 1)
        elif isinstance(c, ctsSong.KeySignature):
            return (c.start_time, 2)
        elif isinstance(c, ctsSong.Tempo):
            return (c.start_time, 3)
        else:
            return (c.start_time, 5)

    measure_starts = [m.start_time for m in song.measure_beats if m.beat == 1]
    n_notes = len(track.notes)
    retval = []
    inote = 0
    carry = None
    last_note_end = 0
    # First add in the notes to the measure
    for start, end in moreit.pairwise(measure_starts):
        current_measure = []
        if carry:
            carry.start_time = start
            carry_end = start + carry.duration
            if carry_end >= end:
                current_measure.append(ctsSong.Note(carry.note_num, start, end-start, 100, held=True))
                carry.duration -= end - start
                last_note_end = end
            else:
                current_measure.append(carry)
                last_note_end = start + carry.duration
                carry = None
        else:
            last_note_end = start
        while inote < n_notes and track.notes[inote].start_time < end:
            n = track.notes[inote]
            gap = n.start_time - last_note_end
            if gap > 0:
                current_measure.append(ctsSong.Rest(last_note_end, gap))
                last_note_end = n.start_time
            note_end = n.start_time + n.duration
            if note_end <= end:
                inote += 1
                last_note_end = note_end
                current_measure.append(n)
            else:
                carry = copy.deepcopy(n)
                duration = end - n.start_time
                n.duration = duration
                n.held = True
                current_measure.append(n)
                last_note_end = end
                carry.duration -= duration
                inote += 1
        gap = end - last_note_end
        if gap > 0:
            current_measure.append(ctsSong.Rest(last_note_end, gap))
            last_note_end = end

        for ks in song.key_signature_changes:
            if start <= ks.start_time < end:
                current_measure.append(ctsSong.KeySignature(start, ks.key))
        for ts in song.time_signature_changes:
            if start <= ts.start_time < end:
                current_measure.append(ctsSong.TimeSignature(start, ts.num, ts.denom))
        current_measure = sorted(current_measure, key=sort_order)
        retval.append(current_measure)
    return retval


def song_to_lilypond(song, tracks=None):
    output = []
    if not song.is_quantized():
        raise ChiptuneSAKQuantizationError("Song must be quantized for export to Lilypond")
    if song.is_polyphonic():
        raise ChiptuneSAKPolyphonyError("All tracks must be non-polyphonic for export to Lilypond")

    # output.append('''
    # \\version "2.18.2"
    # \\paper{
    # indent=0\\mm
    # line-width=120\\mm
    # oddHeaderMarkup = ##f
    # evenHeaderMarkup = ##f
    # oddFooterMarkup = ##f
    # evenFooterMarkup = ##f
    # }
    # ''')
    # page-breaking = #ly:one-line-breaking
    if len(song.name) > 0:
        output.append('\\header { title = "%s" }' % song.name)
    output.append('\\new StaffGroup <<')
    for it, t in enumerate(song.tracks):
        measures = make_measures(song, t)
        track_range = (min(n.note_num for n in t.notes), max(n.note_num for n in t.notes))
        print(track_range)
        output.append('\\new Staff \\with { instrumentName = #"%s" } {' % t.name)
        if track_range[0] < 48:
            output.append('\\clef bass')
        for im, m in enumerate(measures):
            output.append("%% measure %d" % (im + 1))
            for e in m:
                if isinstance(e, ctsSong.Note):
                    f = Fraction(e.duration / song.ppq).limit_denominator(64)
                    if f in lp_durations:
                        output.append("%s%s%s" % (lp_pitch_to_note_name(e.note_num), lp_durations[f], '~' if e.held else ''))
                    else:
                        print('note = ',make_lp_notes(lp_pitch_to_note_name(e.note_num), e.duration, song.ppq), e)
                        output.append(make_lp_notes(lp_pitch_to_note_name(e.note_num), e.duration, song.ppq))

                elif isinstance(e, ctsSong.Rest):
                    f = Fraction(e.duration / song.ppq).limit_denominator(64)
                    if f in lp_durations:
                        output.append("r%s" % (lp_durations[f]))
                    else:
                        print('note = ',make_lp_notes('r', e.duration, song.ppq), e)
                        output.append(make_lp_notes('r', e.duration, song.ppq))

                elif isinstance(e, ctsSong.TimeSignature):
                    output.append('\\time %d/%d' % (e.num, e.denom))

                elif isinstance(e, ctsSong.KeySignature):
                    print(e)
                    output.append('\\key %s \\major' % (e.key.lower()))

            output.append('|')
        output.append('}')
    output.append('>>\n')

    return '\n'.join(output)


if __name__ == '__main__':
    import subprocess
    in_filename = '../test/Yofa.mid'
    song = ctsSong.Song(in_filename)
    song.remove_control_notes()
    song.estimate_quantization()
    song.quantize()
    song.remove_polyphony()
    out = song_to_lilypond(song)
    out_filename = 'Yofa.ly'
    with open(out_filename, 'w') as f:
        f.write(out)
    #subprocess.call('lilypond -ddelete-intermediate-files -dbackend=eps -dresolution=600 --png %s' % out_filename, shell=True)
    subprocess.call('lilypond %s' % out_filename, shell=True)
