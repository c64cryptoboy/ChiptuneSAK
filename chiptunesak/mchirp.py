import copy
from chiptunesak.base import *
from chiptunesak import chirp
import more_itertools as moreit

""" Definition and methods for mchirp.MChirpSong representation """


class Measure:
    @staticmethod
    def _sort_order(c):
        """
        Sort function for measure contents.
        Items are sorted by time and then, for equal times, in this order:
            Time Signature
            Key Signature
            Tempo
            Other MIDI message(s)
            Notes and rests
        """
        if isinstance(c, chirp.Note):
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

    def process_triplets(self, measure_notes, ppq):
        """
        Processes and accounts for all triplets in the measure

        :param measure_notes: list of notes in the measure
        :type measure_notes: list of notes/triplets
        :param ppq: pulses per quarter from song
        :type ppq: int
        :return: new measure contents
        :rtype: list of notes/triplet
        """
        triplets = [n for n in measure_notes if is_triplet(n, ppq)]
        while len(triplets) > 0:
            shortest_triplet = sorted(triplets, key=lambda t: (t.duration, t.start_time))[0]
            t_start = shortest_triplet.start_time - self.start_time
            beat_type = start_beat_type(t_start, ppq)
            if beat_type % 3 == 0:  # This happens when the triplet does NOT start on a beat
                beat_division = beat_type // 3  # Get the beat size from the offset from the triplet start
                # The triplet start time is the previous beat of the required size
                triplet_start_time = (shortest_triplet.start_time * beat_division // ppq) * ppq // beat_division
                # Deduce the triplet length from the position of the note; it is on sub-beat 2 or 3
                min_duration = min(shortest_triplet.duration, shortest_triplet.start_time - triplet_start_time)
                triplet_duration = 3 * min_duration
                while triplet_start_time + triplet_duration <= shortest_triplet.start_time:
                    triplet_start_time += triplet_duration
            else:  # Note is on the beat so triplet starts on the beat
                triplet_start_time = shortest_triplet.start_time
                # Assume the note is a triplet (remember it is the shortest) unless proven otherwise
                triplet_duration = 3 * shortest_triplet.duration
                # Triplet cannot cross measure boundaries
                if triplet_start_time + triplet_duration > self.start_time + self.duration:
                    triplet_duration //= 2
                # All notes inside the triplet have to be triplets themselves
                if any(not is_triplet(n, ppq) for n in measure_notes if
                       triplet_start_time <= n.start_time < triplet_start_time + triplet_duration):
                    triplet_duration //= 2
            # Make a new triplet with the right start time and duration
            new_triplet = Triplet(triplet_start_time, triplet_duration)
            # Now take notes and fill in the triplet
            measure_notes = self.populate_triplet(new_triplet, measure_notes)
            # Check for any remaining triplets in the measure. Interstingly, the triplet object is not a triplet-note!
            triplets = [n for n in measure_notes if is_triplet(n, ppq)]
        # Sort the measure notes before returning
        return sorted(measure_notes, key=lambda n: n.start_time)

    def populate_triplet(self, triplet, measure_notes):
        """
        Given a triplet, populate it from the ntoes in the measure, splitting them if required

        :param triplet: triplet to be populated
        :type triplet: Triplet
        :param measure_notes: notes in the measure
        :type measure_notes: list of notes
        :return: measure notes now including triplet
        :rtype: list of notes/triplets
        """
        triplet_end = triplet.start_time + triplet.duration
        # We will make a new list of notes to return
        new_measure_notes = []
        for n in measure_notes:
            note_end = n.start_time + n.duration
            # Notes that start before the triplet and end after the triplet has started
            if n.start_time < triplet.start_time and note_end > triplet.start_time:
                assert note_end <= triplet_end, "Error in triplet processing!"
                new_notes = n.split(triplet.start_time)
                new_measure_notes.append(new_notes[0])
                triplet.content.append(new_notes[-1])
            # Notes that start inside the triplet
            elif triplet.start_time <= n.start_time < triplet_end:
                if note_end > triplet_end:
                    new_notes = n.split(triplet_end)
                    triplet.content.append(new_notes[0])
                    new_measure_notes.append(new_notes[-1])
                else:
                    triplet.content.append(n)
            # Notes not involved in the triplet
            else:
                new_measure_notes.append(n)

        # Add rests inside the triplet
        triplet.content.sort(key=lambda n: n.start_time)
        triplet_rests = []
        current_position = triplet.start_time
        for n in triplet.content:
            if n.start_time > current_position:
                triplet_rests.append(Rest(current_position, n.start_time - current_position))
            current_position = n.start_time + n.duration
        if current_position < triplet_end:
            triplet_rests.append(Rest(current_position, triplet_end - current_position))
        triplet.content.extend(triplet_rests)
        triplet.content.sort(key=lambda n: n.start_time)
        assert sum(c.duration for c in triplet.content) == triplet.duration, "Triplet content does not sum to length!"
        # Add the triplet to the measure events
        new_measure_notes.append(triplet)
        return sorted(new_measure_notes, key=lambda n: n.start_time)

    def add_rests(self, measure_notes):
        """
        Add rests to a measure content

        :param measure_notes: notes in the measure
        :type measure_notes: list of notes
        :return: new list of events including rests
        :rtype: list of events in measure
        """
        rests = []
        measure_notes.sort(key=lambda n: n.start_time)
        current_time = self.start_time
        for n in measure_notes:
            if n.start_time > current_time:
                rests.append(Rest(current_time, n.start_time - current_time))
            current_time = n.start_time + n.duration
        if current_time < self.start_time + self.duration:
            rests.append(Rest(current_time, self.start_time + self.duration - current_time))
        measure_notes.extend(rests)
        return sorted(measure_notes, key=lambda n: n.start_time)

    def populate(self, track, carry=None):
        """
        Populates a single measure with notes, rests, and other events.

        :param track: Track from which events are to be imported
        :param carry: If last note in previous measure is continued in this measure, the note with
            remaining time
        :return: Carry note, if last note is to be carried into the next measure.
        """
        ppq = track.chirp_song.metadata.ppq
        end = self.start_time + self.duration

        # Measure number is obtained from the song.
        measure_number = track.chirp_song.get_measure_beat(self.start_time).measure
        self.events.append(MeasureMarker(self.start_time, measure_number))

        # Find all the notes that start in this measure; not the fastest but it works
        measure_notes = [copy.copy(n) for n in track.notes if self.start_time <= n.start_time < end]

        # Add in carry from previous measure
        if carry is not None:
            measure_notes.insert(0, copy.copy(carry))
            carry = None

        # Process any notes carried out of the measure
        for n in measure_notes[::-1][:1]:
            note_end = n.start_time + n.duration
            if note_end > end:
                n, carry = tuple(n.split(end))
                break  # only one note can possible go past the end

        measure_notes = self.process_triplets(measure_notes, ppq)
        measure_notes = self.add_rests(measure_notes)
        self.events.extend(copy.deepcopy(measure_notes))

        # Add program changes to measure:
        for pc in track.program_changes:
            if self.start_time <= pc.start_time < end:
                # Leave the time of these messages alone
                self.events.append(pc)

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
                self.events.append(TempoEvent(tm.start_time, tm.qpm))

        self.events = sorted(self.events, key=self._sort_order)

        return carry

    def count_notes(self):
        return sum(1 for e in self.events if isinstance(e, chirp.Note))

    def get_notes(self):
        return [e for e in self.events if isinstance(e, chirp.Note)]

    def get_rests(self):
        return [e for e in self.events if isinstance(e, Rest)]


class MChirpTrack:
    def __init__(self, mchirp_song, chirp_track=None):
        self.measures = []  #: List of measures in the track
        self.name = ''      #: Track name
        self.channel = 0    #: Midi channel number
        self.mchirp_song = mchirp_song  #: parent MChirpSong
        self.qticks_notes = mchirp_song.qticks_notes  #: Inherit quantization from song
        self.qticks_durations = mchirp_song.qticks_durations  #: Inherit quantization from song
        if chirp_track is not None:
            if not isinstance(chirp_track, chirp.ChirpTrack):
                raise ChiptuneSAKTypeError("MChirpTrack init can only import ChirpTrack objects.")
            else:
                self.import_chirp_track(chirp_track)

    def import_chirp_track(self, chirp_track):
        """
        Converts a track into measures, each of which is a sorted list of notes and other events

        :param chirp_track: A ctsSongTrack that has been quantized and had polyphony removed
        :type chirp_track: ChirpTrack
        :return: List of Measure objects corresponding to the measures
        """
        if not chirp_track.is_quantized():
            raise ChiptuneSAKQuantizationError("Track must be quantized to populate measures.")
        if chirp_track.is_polyphonic():
            raise ChiptuneSAKPolyphonyError("Track must be non-polyphonic to populate measures.")
        self.qticks_notes = chirp_track.qticks_notes
        self.qticks_durations = chirp_track.qticks_durations
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


class MChirpSong(ChiptuneSAKBase):
    @classmethod
    def cts_type(cls):
        return 'MChirp'

    def __init__(self, chirp_song=None):
        ChiptuneSAKBase.__init__(self)
        self.tracks = []
        self.metadata = SongMetadata()  #: Metadata
        self.qticks_notes = self.metadata.ppq  #: Quantization for note starts, in ticks
        self.qticks_durations = self.metadata.ppq  #: Quantization for note durations, in ticks
        self.other = []  #: Other MIDI events not used in measures
        if chirp_song is not None:
            if chirp_song.cts_type() != 'Chirp':
                raise ChiptuneSAKTypeError("MChirpSong init can only import ChirpSong objects")
            else:
                self.import_chirp_song(chirp_song)

    def to_chirp(self, **kwargs):
        self.set_options(**kwargs)
        return chirp.ChirpSong(self)

    def import_chirp_song(self, chirp_song):
        """
        Gets all the measures from all the tracks in a song, and removes any empty (note-free) measures from the end.

        :param chirp_song: A chirp.ChirpSong song
        :type chirp_song: ChirpSong
        """
        if not chirp_song.is_quantized():
            raise ChiptuneSAKQuantizationError("ChirpSong must be quantized before populating measures.")
        if chirp_song.is_polyphonic():
            raise ChiptuneSAKPolyphonyError("ChirpSong must not be polyphonic to populate measures.")
        for t in chirp_song.tracks:
            self.tracks.append(MChirpTrack(self, t))
        self.metadata = copy.deepcopy(chirp_song.metadata)
        self.qticks_notes, self.qticks_durations = chirp_song.qticks_notes, chirp_song.qticks_durations
        self.other = copy.deepcopy(chirp_song.other)
        self.trim()
        if chirp_song.get_option('trim_partial', False):
            self.trim_partial_measures()

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

    def trim_partial_measures(self):
        """
        Trims any partial measures from the end of the file
        """
        if all(isinstance(t.measures[-1].events[-1], Rest) for t in self.tracks):
            for t in self.tracks:
                t.measures.pop()
                if len(t.measures) == 0:
                    raise ChiptuneSAKContentError("No measures left in track %s" % t.name)

    def get_time_signature(self, time_in_ticks):
        """
        Finds the active key signature at a given time in the song

        :param time_in_ticks:
        :return: The last time signature change event before the given time.
        """
        current_time_signature = TimeSignatureEvent(0, 4, 4)
        for m in self.tracks[0].measures:
            if m.start_time > time_in_ticks:
                break
            else:
                ts = [e for e in m.events if isinstance(e, TimeSignatureEvent)]
                current_time_signature = ts[-1] if len(ts) > 0 else current_time_signature
        return current_time_signature

    def get_key_signature(self, time_in_ticks):
        """
        Finds the active key signature at a given time in the song

        :param time_in_ticks:
        :return: The last key signature change event before the given time.
        """
        current_key_signature = KeySignatureEvent(0, 'C')
        for m in self.tracks[0].measures:
            if m.start_time > time_in_ticks:
                break
            else:
                ks = [e for e in m.events if isinstance(e, KeySignatureEvent)]
                current_key_signature = ks[-1] if len(ks) > 0 else current_key_signature
        return current_key_signature
