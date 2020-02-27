import copy
from ctsErrors import *
from ctsBase import *
from ctsChirp import Note
import more_itertools as moreit

""" Utility functions for exporting to various formats from the ctsSong.ChirpSong representation """

class Triplet:
    def __init__(self, start_time=0, duration=0, notes=None):
        self.start_time = start_time
        self.duration = duration
        self.content = []

class Measure:
    @staticmethod
    def sort_order(c):
        """
        Sort function for measure contents.
        Items are sorted by time and then, for equal times, in this order:
            Time Signature
            Key Signature
            Tempo
            Other MIDI message(s)
            Notes and rests
        """
        if isinstance(c, Note):
            return (c.start_time, 10)
        elif isinstance(c, Triplet):
            return (c.start_time, 10)
        elif isinstance(c, Rest):
            return (c.start_time, 10)
        elif isinstance(c, MeasureMarker):
            return (c.start_time, 0)
        elif isinstance(c, TimeSignatureEvent):
            return (c.start_time, 1)
        elif isinstance(c, KeySignatureEvent):
            return (c.start_time, 2)
        elif isinstance(c, TempoEvent):
            return (c.start_time, 3)
        elif isinstance(c, ProgramEvent):
            return (c.start_time, 4)
        else:
            return (c.start_time, 5)

    def __init__(self, start_time, duration):
        """
        Creation for Measure object.  Populating the measure with events is a separate method populate()
            :param start_time:  Start time of the measure, in MIDI ticks
            :param duration:    Duration of the measure, in MIDI ticks
        """
        self.start_time = start_time
        self.duration = duration
        self.events = []

    def populate(self, track, carry=None):
        """
        Populates a single measure with notes, rests, and other events.
            :param track: Track from which events are to be imported
            :param carry: If last note in previous measure is continued in this measure, the note with remainining time
            :return: Carry note, if last note is to be carried into the next measure.
        """
        n_notes = len(track.notes)
        inote = 0
        while inote < n_notes and track.notes[inote].start_time < self.start_time:
            inote += 1
        # Measure number is obtained from the song.
        measure_number = track.chirp_song.get_measure_beat(self.start_time).measure
        self.events.append(MeasureMarker(self.start_time, measure_number))
        ppq = track.chirp_song.metadata.ppq
        end = self.start_time + self.duration
        last_note_end = self.start_time
        if carry:  # Deal with any notes carried over from the previous measure
            carry.tied_to = True
            carry.start_time = self.start_time
            carry_end = self.start_time + carry.duration
            if carry.duration <= 0:
                raise ChiptuneSAKValueError("Illegal carry note duration %d" % carry.duration, str(carry))
            if carry_end > end:  # Does the carried note extend past the end of this measure?
                self.events.append(Note(self.start_time, carry.note_num, end - self.start_time, 100, tied_from=True))
                carry.duration -= end - self.start_time
                last_note_end = end
            else:  # Carried note ends during this measure
                self.events.append(carry)
                last_note_end = self.start_time + carry.duration
                carry = None

        # Now iterate over the notes that begin during this measure
        while inote < n_notes and track.notes[inote].start_time < end:
            n = track.notes[inote]
            gap = n.start_time - last_note_end

            # Begin triplet processing
            while is_triplet(n, ppq):
                triplet_duration = 0
                triplet_start_time = self.start_time
                m_start = n.start_time - self.start_time
                beat_type = start_beat_type(m_start, ppq)
                if beat_type % 3 == 0:
                    beat_division = beat_type // 3
                    triplet_start_time = (n.start_time * beat_division // ppq) * ppq // beat_division
                    remainder = (n.start_time - triplet_start_time)
                    if gap < remainder:
                        raise ChiptuneSAKContentError("Undeciperable triplet in measure %d" % measure_number)
                    else:
                        triplet_duration = n.duration * 3
                else:
                    next_note = track.notes[inote + 1]
                    triplet_start_time = n.start_time
                    if next_note.start_time - n.start_time > n.duration * 2:
                        triplet_duration = n.duration * 3
                    elif not is_triplet(next_note, ppq):
                        raise ChiptuneSAKContentError("Incomplete triplet in measure %d" % measure_number)
                    elif next_note.duration >= n.duration:
                        triplet_duration = n.duration * 3
                    else:
                        triplet_duration = next_note.duration * 3
                if triplet_start_time + triplet_duration > end:
                    raise ChiptuneSAKContentError("Triplets past end of measure in measure %d" % measure_number)
                # Now find all notes that go in the triplet
                tp = Triplet(triplet_start_time, triplet_duration)
                tp_current_time = tp.start_time
                triplet_note_duration = tp.duration // 3
                triplet_end_time = tp.start_time + tp.duration
                tp_last_time = tp.start_time
                while n is not None and n.start_time < triplet_end_time:
                    tp_gap = n.start_time - tp_last_time
                    if tp_gap > 0:
                        while tp_current_time < n.start_time:
                            tp.content.append(Rest(tp_current_time, triplet_note_duration))
                            tp_current_time += triplet_note_duration
                            tp_last_time = tp_current_time
                    tp.content.append(n)
                    tp_current_time += n.duration
                    tp.last_time = tp_current_time
                    inote += 1
                    if inote < n_notes:
                        n = track.notes[inote]
                    else:
                        n = None
                while tp_current_time < triplet_end_time:
                    tp.content.append(Rest(tp_current_time, triplet_note_duration))
                    tp_current_time += triplet_note_duration
                    tp_last_time = tp_current_time
                self.events.append(tp)
                last_note_end = triplet_end_time
                if n is not None:
                    gap = n.start_time - triplet_end_time
                    if n.start_time >= end:
                        break
                else:
                    break
            if n is None or n.start_time >= end:
                break
            # continue normal note processing
            if gap > 0:  # Is there a rest before the note starts?
                self.events.append(Rest(last_note_end, gap))
                last_note_end = n.start_time
            note_end = n.start_time + n.duration  # Time that this note ends
            if note_end <= end:  # Note fits within the current measure
                self.events.append(n)
                last_note_end = note_end
            else:
                carry = copy.copy(n)  # Make a copy of the note to use for the carry
                duration = end - n.start_time
                n.duration = duration  # truncate the note to the end of the measure
                n.tied_from = True  # And mark it as tied to the next note
                self.events.append(n)
                last_note_end = end
                carry.duration -= duration  # Det the length of the carried note to the remaining time
            inote += 1  # Move to the next note

        gap = end - last_note_end
        if gap > 0:  # Is there a rest needed at the end of the measure?
            self.events.append(Rest(last_note_end, gap))
            last_note_end = end

        # Add any additional track-specific messages to the measure:
        for m in track.other:
            if self.start_time <= m.start_time < end:
                # Leave the time of these messages alone
                self.events.append(m)

        #  Now add all the song-specific events to the measure.
        for ks in track.chirp_song.key_signature_changes:
            if self.start_time <= ks.start_time < end:
                # Key signature changes must occur at the start of the measure
                self.events.append(KeySignatureEvent(self.start_time, ks.key))

        for ts in track.chirp_song.time_signature_changes:
            if self.start_time <= ts.start_time < end:
                # Time signature changes must occur at the start of the measure
                self.events.append(TimeSignatureEvent(self.start_time, ts.num, ts.denom))

        for tm in track.chirp_song.tempo_changes:
            if self.start_time <= tm.start_time < end:
                # Tempo changes can happen anywhere in the measure
                self.events.append(TempoEvent(tm.start_time, tm.bpm))

        self.events = sorted(self.events, key=self.sort_order)

        return carry

    def count_notes(self):
        return sum(1 for e in self.events if isinstance(e, Note))

    def get_notes(self):
        return [e for e in self.events if isinstance(e, Note)]

    def get_rests(self):
        return [e for e in self.events if isinstance(e, Rest)]



class MChirpTrack:
    def __init__(self, mchirp_song, chirp_track=None):
        self.mchirp_song = mchirp_song
        if chirp_track is not None:
            self.import_chirp_track(chirp_track)

    def import_chirp_track(self, chirp_track):
        """
        Converts a track into measures, each of which is a sorted list of notes and other events

            :param track: A ctsSongTrack that has been quantized and had polyphony removed
            :return:      List of Measure objects corresponding to the measures
        """
        if not chirp_track.is_quantized():
            raise ChiptuneSAKQuantizationError("Track must be quantized to populate measures.")
        if chirp_track.is_polyphonic():
            raise ChiptuneSAKPolyphonyError("Track must be non-polyphonic to populate measures.")
        measures_list = []
        measure_starts = chirp_track.chirp_song.measure_starts()
        # Artificially add an extra measure on the end to finish processing the notes in the last measure.
        measure_starts.append(2 * measure_starts[-1] - measure_starts[-2])
        # First add in the notes to the measure
        carry = None
        for start, end in moreit.pairwise(measure_starts):
            current_measure = Measure(start, end - start)
            carry = current_measure.populate(chirp_track, carry)
            measures_list.append(current_measure)
        self.measures = measures_list
        self.name = chirp_track.name
        self.channel = chirp_track.channel


class MChirpSong:
    def __init__(self, chirp_song=None):
        self.tracks = []
        self.name = ''
        self.stats = {}
        if chirp_song is not None:
            self.import_chirp_song(chirp_song)

    def import_chirp_song(self, chirp_song):
        """
        Gets all the measures from all the tracks in a song, and removes any empty (note-free) measures from the end.

            :param song: A ctsChirp.ChirpSong song
        """
        if not chirp_song.is_quantized():
            raise ChiptuneSAKQuantizationError("ChirpSong must be quantized before populating measures.")
        if chirp_song.is_polyphonic():
            raise ChiptuneSAKPolyphonyError("ChirpSong must not be polyphonic to populate measures.")
        for t in chirp_song.tracks:
            self.tracks.append(MChirpTrack(self, t))
        self.metadata = copy.deepcopy(chirp_song.metadata)
        self.other = copy.deepcopy(chirp_song.other)
        self.trim()

    def trim(self):
        """
        Trims all note-free measures from the end of the song.
        """

        if len(self.tracks) == 0:
            raise ChiptuneSAKContentError("No tracks in song")
        while all(t.measures[-1].count_notes() == 0 for t in self.tracks):
            for t in self.tracks:
                t.measures.pop()
                if len(t.measures) == 0:
                    raise ChiptuneSAKContentError("No measures left in track %s" % t.name)

    def get_time_signature(self, time_in_ticks):
        current_time_signature = TimeSignatureEvent(0, 4, 4)
        for m in self.tracks[0].measures:
            if m.start_time > time_in_ticks:
                break
            else:
                ts = [e for e in m.events if isinstance(e, TimeSignatureEvent)]
                current_time_signature = ts[-1] if len(ts) > 0 else current_time_signature
        return current_time_signature

    def get_key_signature(self, time_in_ticks):
        current_key_signature = KeySignatureEvent(0, 'C')
        for m in self.tracks[0].measures:
            if m.start_time > time_in_ticks:
                break
            else:
                ks = [e for e in m.events if isinstance(e, KeySignatureEvent)]
                current_key_signature = ks[-1] if len(ks) > 0 else current_key_signature
        return current_key_signature

