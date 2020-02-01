import copy
from ctsErrors import *
import ctsConstants
from ctsBase import *
from ctsChirp import ChirpSong, ChirpTrack, Note
import more_itertools as moreit

""" Utility functions for exporting to various formats from the ctsSong.ChirpSong representation """


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
        elif isinstance(c, Rest):
            return (c.start_time, 10)
        elif isinstance(c, MeasureMarker):
            return (c.start_time, 0)
        elif isinstance(c, TimeSignature):
            return (c.start_time, 1)
        elif isinstance(c, KeySignature):
            return (c.start_time, 2)
        elif isinstance(c, Tempo):
            return (c.start_time, 3)
        elif isinstance(c, Program):
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
        self.events.append(MeasureMarker(self.start_time, track.song.get_measure_beat(self.start_time).measure))
        end = self.start_time + self.duration
        last_note_end = self.start_time
        if carry:  # Deal with any notes carried over from the previous measure
            carry.start_time = self.start_time
            carry_end = self.start_time + carry.duration
            if carry.duration <= 0:
                raise ChiptuneSAKValueError("Illegal carry note duration %d" % carry.duration, str(carry))
            if carry_end > end:  # Does the carried note extend past the end of this measure?
                self.events.append(Note(self.start_time, carry.note_num, end - self.start_time, 100, tied=True))
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
                n.tied = True  # And mark it as tied to the next note
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
                if m.msg.type == 'program_change':  # Split out program changes
                    self.events.append(Program(m.start_time, m.msg.program))
                else:
                    self.events.append(m)

        #  Now add all the song-specific events to the measure.
        for ks in track.song.key_signature_changes:
            if self.start_time <= ks.start_time < end:
                # Key signature changes must occur at the start of the measure
                self.events.append(KeySignature(self.start_time, ks.key))

        for ts in track.song.time_signature_changes:
            if self.start_time <= ts.start_time < end:
                # Time signature changes must occur at the start of the measure
                self.events.append(TimeSignature(self.start_time, ts.num, ts.denom))

        for tm in track.song.tempo_changes:
            if self.start_time <= tm.start_time < end:
                # Tempo changes can happen anywhere in the measure
                self.events.append(Tempo(tm.start_time, tm.bpm))

        for m in track.song.other:
            if self.start_time <= m.start_time < end:
                # Leave the time of these messages alone
                self.events.append(m)

        self.events = sorted(self.events, key=self.sort_order)

        return carry

    def count_notes(self):
        return sum(1 for e in self.events if isinstance(e, Note))


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
        measure_starts = chirp_track.song.measure_starts()
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
        self.trim()

    def trim(self):
        """
        Trims all note-free measures from the end of the song.
        """
        while all(t.measures[-1].count_notes() == 0 for t in self.tracks):
            for t in self.tracks:
                t.measures.pop()

    def get_time_signature(self, time_in_ticks):
        current_time_signature = TimeSignature(0, 4, 4)
        for m in self.tracks[0].measures:
            if m.start_time > time_in_ticks:
                break
            else:
                ts = [e for e in m.events if isinstance(e, TimeSignature)]
                current_time_signature = ts[-1] if len(ts) > 0 else current_time_signature
        return current_time_signature

    def get_key_signature(self, time_in_ticks):
        current_key_signature = KeySignature(0, 'C')
        for m in self.tracks[0].measures:
            if m.start_time > time_in_ticks:
                break
            else:
                ks = [e for e in m.events if isinstance(e, KeySignature)]
                current_key_signature = ks[-1] if len(ks) > 0 else current_key_signature
        return current_key_signature


