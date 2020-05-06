from ctsBase import *
import ctsChirp
from ctsConstants import PITCHES

'''
This file contains functions required to export MidiSimple songs to ML64 format.
'''

ml64_durations = {
    Fraction(6, 1): '1d', Fraction(4, 1): '1', Fraction(3, 1): '2d', Fraction(2, 1): '2',
    Fraction(3, 2): '4d', Fraction(1, 1): '4', Fraction(3, 4): '8d', Fraction(1, 2): '8',
    Fraction(1, 4): '16'
}

def pitch_to_ml64_note_name(note_num, octave_offset=0):
    """
    Gets note name for a given MIDI pitch
    """
    if not 0 <= note_num <= 127:
        raise ChiptuneSAKValueError("Illegal note number %d" % note_num)
    octave_num = ((note_num - C0_MIDI_NUM) // 12) + octave_offset
    pitch = note_num % 12
    return "%s%d" % (PITCHES[pitch], octave_num)


def make_ml64_notes(note_name, duration, ppq):
    durs = decompose_duration(duration, ppq, ml64_durations)
    if note_name == 'r' or note_name == 'c':
        retval = ''.join("%s(%s)" % (note_name, ml64_durations[f]) for f in durs)
    else:
        retval = "%s(%s)" % (note_name, ml64_durations[durs[0]])
        if len(durs) > 1:
            retval += ''.join("c(%s)" % (ml64_durations[f]) for f in durs[1:])
    return retval


def ml64_sort_order(c):
    """
    Sort function for measure contents.
    Items are sorted by time and then, for equal times, in this order:
     *  Patch Change
     *   Tempo
     *   Notes and rests
    """
    if isinstance(c, ctsChirp.Note):
        return (c.start_time, 10)
    elif isinstance(c, Rest):
        return (c.start_time, 10)
    elif isinstance(c, MeasureMarker):
        return (c.start_time, 1)
    elif isinstance(c, TempoEvent):
        return (c.start_time, 3)
    elif isinstance(c, ProgramEvent):
        return (c.start_time, 2)
    else:
        return (c.start_time, 5)


def events_to_ml64(events, song, last_continue=False):
    """
    Takes a list of events (such as a measure or a track) and converts it to ML64 commands. If the previous
    list (such as the previous measure) had notes that were not completed, set last_continue.
    :param events:
    :type events:
    :param song:
    :type song:
    :param last_continue:
    :type last_continue:
    :return:
    :rtype: tuple
    """
    content = []
    stats = collections.Counter()
    for e in events:
        if isinstance(e, ctsChirp.Note):
            if last_continue:
                tmp_note = make_ml64_notes('c', e.duration, song.metadata.ppq)
            else:
                tmp_note = make_ml64_notes(pitch_to_ml64_note_name(e.note_num), e.duration, song.metadata.ppq)
            content.append(tmp_note)
            last_continue = e.tied_from
            stats['note'] += 1
            stats['continue'] += tmp_note.count('c(')
        elif isinstance(e, Rest):
            tmp_note = make_ml64_notes('r', e.duration, song.metadata.ppq)
            content.append(tmp_note)
            last_continue = False
            stats['rest'] += tmp_note.count('r(')
        elif isinstance(e, MeasureMarker):
            content.append('[m%d]' % e.measure_number)
        elif isinstance(e, ProgramEvent):
            content.append('i(%d)' % e.program)
            stats['program'] += 1
    return (content, stats, last_continue)


class ML64(ChiptuneSAKIO):

    @classmethod
    def io_type(cls):
        return "ML64"

    def __init__(self):
        ChiptuneSAKIO.__init__(self)
        self.options['format'] = 'standard'

    @property
    def format(self):
        return self.options['format'][0].lower()

    def to_bin(self, song):
        tmp_type = str(type(song))
        if tmp_type == "<class 'ctsChirp.ChirpSong'>":
            if self.format == 'm':
                raise ChiptuneSAKTypeError("Cannot export Chirp song to Measures format")
            else:
                return self.export_chirp_to_ml64(song)
        elif tmp_type == "<class 'ctsMChirp.MChirpSong'>":
            if self.format != 'm':
                tmp_song = ctsChirp.ChirpSong(song)
                tmp_song.quantize(*tmp_song.estimate_quantization())
                return self.export_chirp_to_ml64(tmp_song)
            else:
                return self.export_mchirp_to_ml64(song)
        else:
            raise ChiptuneSAKTypeError("Cannot export object of type {tmp_type} to ML64")

    def to_file(self, song, filename):
        with open(filename, 'w') as f:
            f.write(self.to_bin(song))

    def export_chirp_to_ml64(self, chirp_song):
        """
        Export song to ML64 format, with a minimum number of notes, either with or without measure comments.
        With measure comments, the comments appear within the measure but are not guaranteed to be exactly at the
        beginning of the measure, as tied notes will take precedence.  In compact mode, the ML64 emitted is almost
        as small as possible.
        :param chirp_song:
        :type chirp_song:
        :param ml64_format:
        :type ml64_format: str
        """
        output = []
        if not chirp_song.is_quantized():
            raise ChiptuneSAKQuantizationError("ChirpSong must be quantized for export to ML64")
        if any(t.qticks_notes < chirp_song.metadata.ppq // 4 for t in chirp_song.tracks):
            raise ChiptuneSAKQuantizationError("ChirpSong must be quantized to 16th notes or larger for ML64")
        if chirp_song.is_polyphonic():
            raise ChiptuneSAKPolyphonyError("All tracks must be non-polyphonic for export to ML64")

        mode = self.format

        stats = collections.Counter()
        output.append('ML64(1.3)')
        output.append('song(1)')
        output.append('tempo(%d)' % chirp_song.metadata.qpm)

        for it, t in enumerate(chirp_song.tracks):
            output.append('track(%d)' % (it + 1))
            track_events = []
            last_note_end = 0
            # Create a list of events for the entire track
            for n in t.notes:
                if n.start_time > last_note_end:
                    track_events.append(Rest(last_note_end, n.start_time - last_note_end))
                track_events.append(n)
                last_note_end = n.start_time + n.duration
            track_events.extend(t.program_changes)
            if mode == 's':  # Add measures for standard format
                last_note_end = max(n.start_time + n.duration for t in chirp_song.tracks for n in t.notes)
                measures = [m.start_time for m in chirp_song.measures_and_beats() if m.beat == 1]
                for im, m in enumerate(measures):
                    if m < last_note_end:
                        track_events.append(MeasureMarker(m, im + 1))
            track_events.sort(key=ml64_sort_order)
            # Now send the entire list of events to the ml64 creator
            track_content, stats, *_ = events_to_ml64(track_events, chirp_song)
            output.append(''.join(track_content).strip())
            output.append('track(-)')
        output.append('song(-)')
        output.append('ML64(-)')
        chirp_song.stats['ML64'] = stats
        return '\n'.join(output)

    def export_mchirp_to_ml64(self, mchirp_song):
        """
        Export the song in ML64 format, grouping notes into measures.  The measure comments are guaranteed to
        appear at the beginning of each measure; tied notes will be split to accommodate the measure markers.
        :param mchirp_song: An mchirp song
        :type mchirp_song: MChirpSong
        """
        output = []
        stats = collections.Counter()
        ppq = mchirp_song.metadata.ppq
        output.append('ML64(1.3)')
        output.append('song(1)')
        output.append('tempo(%d)' % mchirp_song.metadata.qpm)

        for it, t in enumerate(mchirp_song.tracks):
            output.append('track(%d)' % (it + 1))
            measures = t.measures
            last_continue = False
            for im, measure in enumerate(measures):
                measure_content, tmp_stats, last_continue = events_to_ml64(measure.events, mchirp_song, last_continue)
                output.append(''.join(measure_content))
                stats.update(tmp_stats)
            output.append('track(-)')
        output.append('song(-)')
        output.append('ML64(-)')
        mchirp_song.stats['ML64'] = stats
        return '\n'.join(output)

