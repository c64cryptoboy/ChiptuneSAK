import collections
from fractions import Fraction
import ctsSong
from ctsErrors import *
import ctsExportUtil
from ctsConstants import PITCHES

'''
This file contains functions required to export  MidiSimple songs to ML64 format.
'''

ml64_durations = {
    Fraction(6, 1): '1d', Fraction(4, 1): '1', Fraction(3, 1): '2d', Fraction(2, 1): '2',
    Fraction(3, 2): '4d', Fraction(1, 1): '4', Fraction(3, 4): '8d', Fraction(1, 2): '8',
    Fraction(3, 8): '16d', Fraction(1, 4): '16'
}

ML64MeasureMarker = collections.namedtuple('ML64MeasureMarker', ['start_time', 'measure_number'])


def pitch_to_ml64_note_name(note_num, octave_offset=1):
    """
    Gets note name for a given MIDI pitch
    """
    if not 0 <= note_num <= 127:
        raise ChiptuneSAKValueError("Illegal note number %d" % note_num)
    octave_num = (note_num // 12) - octave_offset
    pitch = note_num % 12
    return "%s%d" % (PITCHES[pitch], octave_num)


def make_ml64_notes(note_name, duration, ppq):
    durs = []
    remainder = duration
    while remainder > 0:
        if remainder < min(ml64_durations):
            raise ChiptuneSAKValueError("Illegal duration: %d (ppq = %d)" % (remainder, ppq))
        for f in sorted(ml64_durations, reverse=True):
            if remainder >= f * ppq:
                durs.append(f)
                remainder -= f * ppq
                break
    if note_name == 'r' or note_name == 'c':
        retval = ''.join("%s(%s)" % (note_name, ml64_durations[f]) for f in durs)
    else:
        retval = "%s(%s)" % (note_name, ml64_durations[durs[0]])
        if len(durs) > 1:
            retval += ''.join("c%s" % (ml64_durations[f]) for f in durs[1:])
    return retval


def ml64_sort_order(c):
    """
    Sort function for measure contents.
    Items are sorted by time and then, for equal times, in this order:
        Patch Change
        Tempo
        Notes and rests
    """
    if isinstance(c, ctsSong.Note):
        return (c.start_time, 10)
    elif isinstance(c, ctsSong.Rest):
        return (c.start_time, 10)
    elif isinstance(c, ML64MeasureMarker):
        return (c.start_time, 1)
    elif isinstance(c, ctsSong.Tempo):
        return (c.start_time, 3)
    elif isinstance(c, ctsSong.Program):
        return (c.start_time, 2)
    else:
        return (c.start_time, 5)


def export_ml64(song, format='standard'):
    output = []
    if not song.is_quantized():
        raise ChiptuneSAKQuantizationError("Song must be quantized for export to ML64")
    if any(t.qticks_notes < song.ppq // 4 for t in song.tracks):
        raise ChiptuneSAKQuantizationError("Song must be quantized to 16th notes or larger for ML64")
    if song.is_polyphonic():
        raise ChiptuneSAKPolyphonyError("All tracks must be non-polyphonic for export to ML64")

    mode = format.lower()[0]
    if mode == 'm':
        return export_ml64_measures(song)

    stats = collections.Counter()
    ppq = song.ppq
    output.append('ML64(1.3)')
    output.append('song(1)')
    output.append('tempo(%d)' % song.bpm)

    for it, t in enumerate(song.tracks):
        output.append('track(%d)' % (it + 1))
        track_events = []
        last_note_end = 0
        # Create a list of events for the entire track
        for n in t.notes:
            if n.start_time > last_note_end:
                track_events.append(ctsSong.Rest(last_note_end, n.start_time - last_note_end))
            track_events.append(n)
            last_note_end = n.start_time + n.duration
        for p in [m for m in t.other if m.msg.type == 'program_change']:
            track_events.append(ctsSong.Program(p.start_time, str(p.msg.program)))
        if mode == 's':  # Add measures for standard format
            last_note_end = max(n.start_time + n.duration for t in song.tracks for n in t.notes)
            measures = [m.start_time for m in song.measure_beats if m.beat == 1]
            for im, m in enumerate(measures):
                if m < last_note_end:
                    track_events.append(ML64MeasureMarker(m, im + 1))
        track_events.sort(key=ml64_sort_order)
        # Now send the entire list of events to the ml64 creator
        track_content, stats, *_ = events_to_ml64(track_events, song)
        output.append(''.join(track_content).strip())
        output.append('track(-)')
    output.append('song(-)')
    output.append('ML64(-)')
    song.stats['ML64'] = stats
    return '\n'.join(output)


def export_ml64_measures(song):
    output = []
    if not song.is_quantized():
        raise ChiptuneSAKQuantizationError("Song must be quantized for export to ML64")
    if any(t.qticks_notes < song.ppq // 4 for t in song.tracks):
        raise ChiptuneSAKQuantizationError("Song must be quantized to 16th notes or larger for ML64")
    if song.is_polyphonic():
        raise ChiptuneSAKPolyphonyError("All tracks must be non-polyphonic for export to ML64")

    stats = collections.Counter()
    ppq = song.ppq
    output.append('ML64(1.3)')
    output.append('song(1)')
    output.append('tempo(%d)' % song.bpm)

    for it, t in enumerate(song.tracks):
        output.append('track(%d)' % (it + 1))
        measures = ctsExportUtil.populate_measures(song, t)
        last_continue = False
        for im, measure in enumerate(measures):
            measure_content, tmp_stats, last_continue = events_to_ml64(measure, song, last_continue)
            measure_content.insert(0, '[m%d]' % (im + 1))
            output.append(''.join(measure_content))
            stats.update(tmp_stats)
        output.append('track(-)')
    output.append('song(-)')
    output.append('ML64(-)')
    song.stats['ML64'] = stats
    return '\n'.join(output)


def events_to_ml64(events, song, last_continue=False):
    """
    Takes a list of events (such as a measure or a track) and converts it to ML64 commands. If the previous
    list (such as the previous measure) had notes that were not completed, set last_continue.
    """
    content = []
    stats = collections.Counter()
    for e in events:
        if isinstance(e, ctsSong.Note):
            if last_continue:
                tmp_note = make_ml64_notes('c', e.duration, song.ppq)
            else:
                tmp_note = make_ml64_notes(pitch_to_ml64_note_name(e.note_num), e.duration, song.ppq)
            content.append(tmp_note)
            last_continue = e.tied
            stats['note'] += 1
            stats['continue'] += tmp_note.count('c(')
        elif isinstance(e, ctsSong.Rest):
            tmp_note = make_ml64_notes('r', e.duration, song.ppq)
            content.append(tmp_note)
            last_continue = False
            stats['rest'] += tmp_note.count('r(')
        elif isinstance(e, ML64MeasureMarker):
            content.append('\n[m%d]' % e.measure_number)
        elif isinstance(e, ctsSong.Program):
            content.append('i(%s)' % e.program)
            stats['program'] += 1
    return (content, stats, last_continue)


if __name__ == '__main__':
    import sys

    in_song = ctsSong.Song(sys.argv[1])
    print("Original:", "polyphonic" if in_song.is_polyphonic() else 'non polyphonic')
    print("Original:", "quantized" if in_song.is_quantized() else 'non quantized')

    in_song.remove_control_notes()
    # in_song.modulate(3, 2)
    in_song.quantize(in_song.ppq // 4,
                     in_song.ppq // 4)  # Quantize to 16th time_series (assume no dotted 16ths allowed)

    print("Overall quantization = ", (in_song.qticks_notes, in_song.qticks_durations), "ticks")
    print("(%s, %s)" % (
        ctsSong.duration_to_note_name(in_song.qticks_notes, in_song.ppq),
        ctsSong.duration_to_note_name(in_song.qticks_durations, in_song.ppq)))
    # Note:  for ML64 ALWAYS remove_polyphony after quantization.
    in_song.remove_polyphony()
    print("After polyphony removal:", "polyphonic" if in_song.is_polyphonic() else 'non polyphonic')
    print("After quantization:", "quantized" if in_song.is_quantized() else 'non quantized')

    # print(sum(len(t.notes) for t in in_song.tracks))

    print(export_ml64(in_song, format='m'))
    print('------------------')
    print('\n'.join('%9ss: %d' % (k, in_song.stats['ML64'][k]) for k in in_song.stats['ML64']))
