
import collections
import ctsSong
from ctsErrors import *
from ctsConstants import PITCHES

'''
This file contains functions required to export  MidiSimple songs to ML64 format.
'''

DURATION_NAMES = {
    # 2: '64', 3: '64d', 4: '32', 6: '32d',
    8: '16', 12: '16d', 16: '8', 24: '8d',
    32: '4', 48: '4d', 64: '2', 96: '2d', 128: '1', 192: '1d'
}

PPQ_SCALE = 32
MIN_NOTE_LENGTH = 8
MAX_NOTE_LENGTH = 192

ML64_OCTAVE_BASE = -1  # -1 means ML64 calls middle C (note 60) "C4".

NOTE_PRI = 4
PATCH_PRI = 3
MEASURE_PRI = 0

def get_note_name(note_num, octave_offset):
    ''' Gets the ML64 note name for a given MIDI pitch '''
    global ML64_OCTAVE_BASE, PITCHES
    octave = (note_num // 12) + ML64_OCTAVE_BASE + octave_offset
    pitch = note_num % 12
    return "%s%d" % (PITCHES[pitch], octave)


def get_duration_names(duration, ppq):
    ''' Returns a list of ML64 durations needed to create a given note length '''
    global PPQ_SCALE, DURATION_NAMES
    max_note_length = max(DURATION_NAMES)
    ret_val = []
    tmp = (PPQ_SCALE * duration) // ppq
    tmp_d, tmp_n = 0, '0'
    while tmp > max_note_length:
        ret_val.append(DURATION_NAMES[max_note_length])
        tmp -= max_note_length
    # While the time is not an even divisor, add together note times
    min_duration = min(DURATION_NAMES)
    while tmp not in DURATION_NAMES:
        if tmp < min_duration:
            raise ChiptuneSAKException('Illegal ML64 duration: %d; minimum allowed = %d' % (tmp, min_duration))
        for d in sorted(DURATION_NAMES):
            if d > tmp:
                ret_val.append(tmp_n)
                tmp -= tmp_d
                break
            tmp_d, tmp_n = (d, DURATION_NAMES[d])
    ret_val.append(DURATION_NAMES[tmp])
    return ret_val


class ML64Note:
    ''' Implements a ML64 note, rest, or continue command '''

    def __init__(self, type='note', note=0, duration_ticks=0, ppq=960, octave_offset=0):
        self.stats = collections.Counter()
        self.type = type.lower()
        self.octave_offset = octave_offset
        self.note_num = note
        if self.note_num == 0:
            self.type = 'rest'
        if self.type == 'note':
            self.note_name = get_note_name(self.note_num, self.octave_offset)
        elif self.type == 'rest':
            self.note_name = 'r'
        elif self.type == 'continue':
            self.note_name = 'c'
        else:
            self.note_name = '?'
        self.duration = duration_ticks
        self.duration_names = get_duration_names(self.duration, ppq)
        self.update_stats()

    def update_stats(self):
        if self.type == 'note':
            self.stats['note'] += 1
            self.stats['continue'] += len(self.duration_names) - 1
        elif self.type == 'rest' or self.type == 'continue':
            self.stats[self.type] += len(self.duration_names)

    def __str__(self):
        ''' Generate string for an ML64 command '''
        if self.type == 'note':
            if len(self.duration_names) <= 1:
                return "%s(%s)" % (self.note_name, self.duration_names[0])
            else:
                return "%s(%s)" % (self.note_name, self.duration_names[0]) + ''.join('c(%s)' % d for d in self.duration_names[1:])
        elif self.type == 'rest':
            return ''.join('r(%s)' % d for d in self.duration_names)
        elif self.type == 'continue':
            return ''.join('c(%s)' % d for d in self.duration_names)
        else:
            return '??'


def export_ML64(in_song, octave_offset=0, mode='standard'):
    ''' Exports a MidiSimple song to ML64 format.
        Only the first letter of the mode is important.  Can be:
          standard - minimum number of notes with approximate measure markings
          compact -  minimum size
          measures - exact measure markings and all notes fit into measures
        VERY IMPORTANT:  The song MUST be quantized to 16th time_series (ppq / 4) and have polyphony and
                         control notes removed before calling this function.
    '''
    if in_song.is_polyphonic():
        raise ChiptuneSAKException('Polyphonic song: cannot convert to ML64')

    mode = mode.lower()[0]
    if mode == 'm':
        return export_ML64_measures(in_song, octave_offset)

    overall_stats = collections.Counter()
    ppq = in_song.ppq
    output = ['ML64(1.3)']
    output.append('song(1)')
    output.append('tempo(%d)' % in_song.bpm)
    for it, t in enumerate(in_song.tracks):
        output.append('track(%d)' % (it + 1))
        track_ML64 = []
        last_note_end = 0
        for n in t.notes:
            if n.start_time > last_note_end:
                tmp_note = ML64Note('rest', 0, n.start_time - last_note_end, ppq)
                tmp_str = str(tmp_note)
                track_ML64.append((last_note_end, NOTE_PRI, tmp_str))
                overall_stats.update(tmp_note.stats)
            tmp_note = ML64Note('note', n.note_num, n.duration, ppq, octave_offset)
            tmp_str = str(tmp_note)
            track_ML64.append((n.start_time, NOTE_PRI, tmp_str))
            overall_stats.update(tmp_note.stats)
            last_note_end = n.start_time + n.duration
        for p in [m for m in t.other if m[1].type == 'program_change']:
            tmp_str = 'i(%d)' % p[1].program
            track_ML64.append((p[0], PATCH_PRI, tmp_str))
            overall_stats['program'] += 1
        if mode == 's':
            last_note_end = max(n.start_time + n.duration for t in in_song.tracks for n in t.notes)
            measures = [m[0] for m in in_song.measure_beats if m[2] == 1]
            for im, m in enumerate(measures):
                if m < last_note_end:
                    tmp_str = '\n[m%d]' % (im + 1)
                    track_ML64.append((m, MEASURE_PRI, tmp_str))
        track_ML64.sort(key=lambda e: (e[:2]))
        output.append(''.join(n[-1] for n in track_ML64).strip())
        output.append('track(-)')
    in_song.stats['ML64'] = overall_stats
    output.append('song(-)')
    output.append('ML64(-)')
    return '\n'.join(output)


def export_ML64_measures(in_song, octave_offset):
    """
    Exports ML64 delimited by measures.  Every measure be EXACTLY filled with ML64 notes; any notes that
    cross measure boundaries will be split into more than one and continues used.
    """
    overall_stats = collections.Counter()
    ppq = in_song.ppq
    output = ['ML64(1.3)']
    output.append('song(1)')
    output.append('tempo(%d)' % in_song.bpm)
    measures = [m.start_time for m in in_song.measure_beats if m.beat == 1]
    last_note_end = max(n.start_time + n.duration for t in in_song.tracks for n in t.notes)
    while measures[-1] < last_note_end:
        measures.append(2 * measures[-1] - measures[-2])
    for it, t in enumerate(in_song.tracks):
        output.append('track(%d)' % (it + 1))
        track_ML64 = []
        last_measure = measures[0]
        leftover = None
        # Find all time_series that start during the measure
        for n_m, m in enumerate(measures[1:]):
            measure_ML64 = [(last_measure, MEASURE_PRI, '[m%d]' % (n_m + 1))]
            leftover_flag = False
            measure_notes = [n for n in t.notes if n.start_time >= last_measure and n.start_time < m]
            # If there is still a note continuing from the last measure, insert a continuation note
            if leftover:
                measure_notes.insert(0, leftover)
                leftover_flag = True
            # If the measure is empty insert a note with pitch 0 (rest)
            elif len(measure_notes) == 0:
                measure_notes.insert(0, ctsSong.Note(0, last_measure, m - last_measure, 0))
            # If the measure starts with a rest, insert a rest.  THe logic below will deal with it if it's longer than
            #  the measure.
            elif measure_notes[0].start_time > last_measure:
                measure_notes.insert(0, ctsSong.Note(0, last_measure, measure_notes[0].start_time - last_measure, 0))
            n_notes = len(measure_notes)
            for i_n, n in enumerate(measure_notes):
                note_end = n.start_time + n.duration
                # Checking for note past end of measure has to come first in case the leftover note from the
                # last measure is long than this entire measure, in which case it gets truncated and carried yet again.
                if note_end > m:
                    leftover = ctsSong.Note(n.note_num, m, note_end - m, n.velocity)
                    note_end = m
                # Now we can emit any leftover note because it's guaranteed to fit into the measure.
                if leftover_flag:
                    tmp_note = ML64Note('continue', n.note_num, n.duration, ppq, octave_offset)
                    tmp_str = str(tmp_note)
                    measure_ML64.append((n.start_time, NOTE_PRI, tmp_str))
                    overall_stats.update(tmp_note.stats)
                    leftover_flag = False
                    leftover = None
                # Emit a note that fits into the measure
                else:
                    tmp_note = ML64Note('note', n.note_num, note_end - n.start_time, ppq, octave_offset)
                    tmp_str = str(tmp_note)
                    measure_ML64.append((n.start_time, NOTE_PRI, tmp_str))
                    overall_stats.update(tmp_note.stats)
                # Get the next note's start time.  If it is the last note in the measure, that is the start of the
                #  next measure.
                if i_n < n_notes - 1:
                    next_note_start = measure_notes[i_n + 1].start_time
                else:
                    next_note_start = m
                # Get any rests between time_series
                gap = next_note_start - note_end
                if gap > 0:
                    tmp_note = ML64Note('rest', 0, gap, ppq)
                    tmp_str = str(tmp_note)
                    measure_ML64.append((note_end, NOTE_PRI, tmp_str))
                    overall_stats.update(tmp_note.stats)

            # Now check for instrument changes during the measure
            measure_patch_changes = [p for p in t.other if
                                     p[0] >= last_measure and p[0] < m and p[1].type == 'program_change']
            for p in measure_patch_changes:
                tmp_str = 'i(%d)' % p[1].program
                measure_ML64.append((p[0], PATCH_PRI, tmp_str))
                overall_stats['program'] += 1

            # Move to the next measure
            last_measure = m
            # All the ML64 events are in the list, so sort them by time and priority.
            measure_ML64.sort(key=lambda e: (e[:2]))
            track_ML64.append(''.join(n[-1] for n in measure_ML64))
        output.append('\n'.join(track_ML64))
        output.append('track(-)')

    in_song.stats['ML64'] = overall_stats
    output.append('song(-)')
    output.append('ML64(-)')
    return '\n'.join(output)

if __name__ == '__main__':
    import sys
    in_song = ctsSong.Song(sys.argv[1])
    print("Original:", "polyphonic" if in_song.is_polyphonic() else 'non polyphonic')
    print("Original:", "quantized" if in_song.is_quantized() else 'non quantized')

    in_song.remove_control_notes()
    in_song.modulate(3, 2)
    in_song.quantize(in_song.ppq // 4, in_song.ppq // 4)  # Quantize to 16th time_series (assume no dotted 16ths allowed)

    print("Overall quantization = ", (in_song.qticks_notes, in_song.qticks_durations), "ticks")
    print("(%s, %s)" % (
    ctsSong.duration_to_note_name(in_song.qticks_notes, in_song.ppq),
        ctsSong.duration_to_note_name(in_song.qticks_durations, in_song.ppq)))
    # Note:  for ML64 ALWAYS remove_polyphony after quantization.
    in_song.remove_polyphony()
    print("After polyphony removal:", "polyphonic" if in_song.is_polyphonic() else 'non polyphonic')
    print("After quantization:", "quantized" if in_song.is_quantized() else 'non quantized')

    # print(sum(len(t.notes) for t in in_song.tracks))

    print(export_ML64(in_song, 0, mode='c'))
    print('------------------')
    print('\n'.join('%9ss: %d' % (k, in_song.stats['ML64'][k]) for k in in_song.stats['ML64']))
