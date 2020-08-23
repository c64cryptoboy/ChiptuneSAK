# Midi Simple Processing Library
#

import copy
import bisect
import more_itertools as moreit
from chiptunesak.base import *
from chiptunesak import mchirp
from chiptunesak import rchirp
from chiptunesak import constants


class Note:
    """
    This class represents a note in human-friendly form:  as a note with a start time,
    a duration, and a velocity.
    """

    def __init__(self, start, note, duration, velocity=100, tied_from=False, tied_to=False):
        self.note_num = note        #: MIDI note number
        self.start_time = start     #: In ticks since tick 0
        self.duration = duration    #: In ticks
        self.velocity = velocity    #: MIDI velocity 0-127
        self.tied_from = tied_from  #: Is the next note tied from this note?
        self.tied_to = tied_to      #: Is this note tied from the previous note?

    def __eq__(self, other):
        """ Two notes are equal when their note numbers and durations are the same """
        return (self.note_num == other.note_num) and (self.duration == other.duration)

    def split(self, tick_position):
        """
        Splits a note into two notes at time tick_position, if the tick position falls
        within the note's duration.

        :param tick_position: position to split at
        :type tick_position: int
        :return: list with split note
        :rtype: list of Note
        """
        if tick_position < self.start_time or tick_position >= self.start_time + self.duration:
            return [self]
        else:
            new_duration = self.start_time + self.duration - tick_position
            new_note = Note(tick_position, self.note_num, new_duration, self.velocity, tied_to=True)
            self.duration = tick_position - self.start_time
            self.tied_from = True
            return [n for n in [self, new_note] if n.duration > 0]

    def __str__(self):
        return "pit=%3d  st=%4d  dur=%4d  vel=%4d, tfrom=%d tto=%d" \
               % (self.note_num, self.start_time, self.duration, self.velocity, self.tied_from, self.tied_to)


class ChirpTrack:
    """
    This class represents a track (or a voice) from a song.  It is basically a list of Notes with some
    other context information.

    ASSUMPTION: The track contains notes for only ONE instrument (midi channel).  Tracks with notes
    from more than one instrument will produce undefined results.
    """

    # Define the message types to preserve as a static variable
    other_message_types = ['pitchwheel', 'control_change']

    def __init__(self, chirp_song, mchirp_track=None):
        self.chirp_song = chirp_song  #: Parent song
        self.name = 'none'  #: Track name
        self.channel = 0  #: This track's midi channel.  Each track should have notes from only one channel.
        self.notes = []  #: The notes in the track
        self.program_changes = []  #: Program (patch) changes in the track
        self.other = []  #: Other events in the track (includes voice changes and pitchwheel)
        self.qticks_notes = chirp_song.qticks_notes  #: Not start quantization from song
        self.qticks_durations = chirp_song.qticks_durations  #: Note duration quantization
        if mchirp_track is not None:
            if not isinstance(mchirp_track, mchirp.MChirpTrack):
                raise ChiptuneSAKTypeError("ChirpTrack init can only import MChirpTrack objects")
            else:
                self.import_mchirp_track(mchirp_track)

    def import_mchirp_track(self, mchirp_track):
        """
        Imports an  MChirpTrack

        :param mchirp_track: track to import
        :type mchirp_track: MChirpTrack
        """
        def _anneal_notes(notes):
            """
            This function anneals, or combines, notes that crossed measure boundaries.  It's a local
            function that only exists here.
            """
            ret_val = []
            current_note = None
            for n in notes:
                if current_note is not None:
                    assert current_note.tied_from, "Continued note should be tied from: %s" % current_note
                    assert n.tied_to, "Note should be tied to since last note was tied from: %s" % n
                    assert n.start_time == current_note.start_time + current_note.duration, "Tied notes not adjacent"
                    current_note.duration += n.duration
                    if n.tied_from:
                        current_note.tied_from = n.tied_from
                    else:
                        ret_val.append(current_note)
                        current_note = None
                else:
                    if n.tied_from:
                        current_note = copy.copy(n)
                    else:
                        ret_val.append(n)
                        current_note = None
            return ret_val

        self.name = mchirp_track.name
        self.channel = mchirp_track.channel
        # Preserve the quantization from the MChirp
        self.qticks_notes, self.qticks_durations = mchirp_track.qticks_notes, mchirp_track.qticks_durations
        temp_notes = [e for m in mchirp_track.measures for e in m.events if isinstance(e, Note)]
        temp_triplets = [e for m in mchirp_track.measures for e in m.events if isinstance(e, Triplet)]
        temp_notes.extend([e for tp in temp_triplets for e in tp.content if isinstance(e, Note)])
        self.program_changes = [e for m in mchirp_track.measures for e in m.events if isinstance(e, ProgramEvent)]
        self.other = [e for m in mchirp_track.measures for e in m.events if isinstance(e, OtherMidiEvent)]
        temp_notes.sort(key=lambda n: n.start_time)
        self.notes = _anneal_notes(temp_notes)
        self.notes.sort(key=lambda n: (n.start_time, -n.note_num))
        self.program_changes.sort(key=lambda e: e.start_time)
        self.other.sort(key=lambda n: n.start_time)

    def estimate_quantization(self):
        """
        This method estimates the optimal quantization for note starts and durations from the note
        data itself. This version only uses the current track for the optimization.  If the track
        is a part with long notes or not much movement, I recommend using the get_quantization()
        on the entire song instead. Many pieces have fairly well-defined note start spacing, but
        no discernable duration quantization, so in that case the default is half the note start
        quantization.  These values are easily overridden.

        :return: tuple of quantization values for (start, duration)
        :rtype: tuple of ints
        """
        tmpNotes = [n.start_time for n in self.notes]
        self.qticks_notes = find_quantization(tmpNotes, self.chirp_song.metadata.ppq)
        tmpNotes = [n.duration for n in self.notes]
        self.qticks_durations = find_duration_quantization(tmpNotes, self.qticks_notes)
        if self.qticks_durations < self.qticks_notes:
            self.qticks_durations = self.qticks_notes // 2
        return (self.qticks_notes, self.qticks_durations)

    def quantize(self, qticks_notes=None, qticks_durations=None):
        """
        This method applies quantization to both note start times and note durations.  If you
        want either to remain unquantized, simply specify either qticks parameter to be 1, so
        that it will quantize to the nearest tick (i.e. leave everything unchanged)

        :param qticks_notes: Resolution of note starts in ticks
        :type qticks_notes: int
        :param qticks_durations: Resolution of note durations in ticks.  Also length of shortest note.
        :type qticks_durations: int
        """
        # Update the members to reflect the quantization applied
        if qticks_notes:
            self.qticks_notes = qticks_notes
        if qticks_durations:
            self.qticks_durations = qticks_durations

        for i, n in enumerate(self.notes):
            # Store the "before" values for statistics
            start_before = n.start_time
            duration_before = n.duration
            # Quantize the start times and durations
            n.start_time = quantize_fn(n.start_time, self.qticks_notes)
            n.duration = quantize_fn(n.duration, self.qticks_durations)
            # Never quantize a note duration to less than the minimum
            if n.duration < self.qticks_durations:
                n.duration = self.qticks_durations
            self.notes[i] = n

        # Quantize the other MIDI messages in the track
        for i, m in enumerate(self.other):
            self.other[i] = OtherMidiEvent(quantize_fn(m.start_time, self.qticks_notes), m.msg)

    def quantize_long(self, qticks):
        """
        Quantizes only notes longer than 3/4 qticks; quantizes both start time and duration.
        This function is useful for quantization that also preserves some ornaments, such as
        grace notes.

        :param qticks: Quantization for notes and durations
        :type qticks: int
         """
        min_length = qticks * 3 // 4
        for i, n in enumerate(self.notes):
            if n.duration >= min_length:
                n.start_time = quantize_fn(n.start_time, qticks)
                n.duration = quantize_fn(n.duration, qticks)
                self.notes[i] = n
        self.notes.sort(key=lambda n: (n.start_time, -n.note_num))

    def merge_notes(self, max_merge_length_ticks):
        """
        Merges immediately adjacent notes if they are short and have the same note number.

        :param max_merge_length_ticks: Length of the longest note to merge, in ticks
        :type max_merge_length_ticks: int
        """
        ret_notes = []
        last = self.notes[0]
        for n in self.notes[1:]:
            if n.start_time == last.start_time + last.duration \
                    and n.note_num == last.note_num \
                    and n.duration <= max_merge_length_ticks:
                last.duration += n.duration
                continue
            else:
                ret_notes.append(last)
            last = n
        ret_notes.append(last)
        self.notes = ret_notes
        self.notes.sort(key=lambda n: (n.start_time, -n.note_num))

    def remove_short_notes(self, max_duration_ticks):
        """
         Removes notes shorter than max_duration_ticks from the track.

        :param max_duration_ticks: maximum duration of notes to remove, in ticks
        :type max_duration_ticks: int
        """
        ret_notes = []
        for n in self.notes:
            if n.duration > max_duration_ticks:
                ret_notes.append(n)
        self.notes = ret_notes
        self.notes.sort(key=lambda n: (n.start_time, -n.note_num))

    def set_min_note_len(self, min_len_ticks):
        """
        Sets the minimum note length for the track.  Notes shorter than min_len_ticks will
        be lengthened and any notes that overlap will have their start times adjusted to allow
        the new longer note.

        :param min_len_ticks: Minimum note length
        :type min_len_ticks: int
        """
        self.notes.sort(key=lambda n: (n.start_time, -n.note_num))  # Notes must be sorted
        for i, n in enumerate(self.notes):
            if 0 < n.duration < min_len_ticks:
                n.duration = min_len_ticks
                self.notes[i] = n
                last_end = n.start_time + n.duration
                j = i + 1
                while j < len(self.notes):
                    if self.notes[j].start_time < last_end:
                        tmp_end = self.notes[j].start_time + self.notes[j].duration
                        self.notes[j].start_time = last_end
                        self.notes[j].duration = tmp_end - self.notes[j].start_time
                        j += 1
                    else:
                        break
        self.notes = [n for n in self.notes if n.duration >= min_len_ticks]
        self.notes.sort(key=lambda n: (n.start_time, -n.note_num))  # Notes must be sorted

    def remove_polyphony(self):
        """
        This function eliminates polyphony, so that in each channel there is only one note
        active at a time. If a chord is struck all at the same time, it will retain the highest
        note. Otherwise, when a new note is started, the previous note is truncated.
        """
        ret_notes = []
        last = self.notes[0]
        for n in self.notes[1:]:
            if n.start_time == last.start_time:
                continue
            elif n.start_time < last.start_time + last.duration:
                last.duration = n.start_time - last.start_time
            if last.duration > 0:
                ret_notes.append(last)
            last = n
        ret_notes.append(last)
        self.notes = ret_notes
        self.notes.sort(key=lambda n: (n.start_time, -n.note_num))

    def is_polyphonic(self):
        """
        Returns whether the track is polyphonic; if any notes overlap it is.

        :return: True if track is polyphonic.
        :rtype: bool
        """
        return any(b.start_time - a.start_time < a.duration for a, b in moreit.pairwise(self.notes))

    def is_quantized(self):
        """
        Returns whether the current track is quantized or not.  Since a quantization of 1 is
        equivalent to no quantization, a track quantized to tick will return False.

        :return: True if the track is quantized.
        :rtype: bool
        """
        if self.qticks_notes < 2 or self.qticks_durations < 2:
            return False
        return all(n.start_time % self.qticks_notes == 0
                   and n.duration % self.qticks_durations == 0
                   for n in self.notes)

    def remove_keyswitches(self, ks_max=8):
        """
        Removes all MIDI notes with values less than or equal to ks_max. Some MIDI devices
        and applications use these extremely low notes to convey patch change or other
        information, so removing them (especially if you do not want polyphony) is a good idea.

        :param ks_max: maximum note number for keyswitches in the track (often 8)
        :type ks_max: int
        """
        self.notes = [n for n in self.notes if n.note_num > ks_max]

    def truncate(self, max_tick):
        """
        Truncate the track to max_tick

        :param max_tick:  maximum tick number for events to start (track will play to end of
            any notes started)
        :type max_tick: int
        """
        self.notes = [n for n in self.notes if n.start_time <= max_tick]
        self.program_changes = [p for p in self.program_changes if p.start_time <= max_tick]
        self.other = [e for e in self.other if e.start_time <= max_tick]

    def transpose(self, semitones):
        """
        Transposes track in-place by semitones, which can be positive (transpose up) or
        negative (transpose down)

        :param semitones:  Number of semitones to transpose
        """
        for i, n in enumerate(self.notes):
            new_note_num = n.note_num + semitones
            if 0 <= new_note_num <= 127:
                self.notes[i].note_num = new_note_num
            else:
                self.notes[i].duration = 0  # Set duration to zero for later deletion
        self.notes = [n for n in self.notes if n.duration > 0]

    def modulate(self, num, denom):
        """
        Modulates this track metrically by a factor of num / denom

        :param num:   Numerator of modulation
        :param denom: Denominator of modulation
        """
        f = Fraction(num, denom).limit_denominator(32)
        num = f.numerator
        denom = f.denominator
        # Change the start times of all the "other" events
        for i, (t, m) in enumerate(self.other):
            t = (t * num) // denom
            self.other[i] = OtherMidiEvent(t, m)

        # Change all the note start times and durations
        for i, n in enumerate(self.notes):
            n.start_time = (n.start_time * num) // denom
            n.duration = (n.duration * num) // denom
            self.notes[i] = n
        # Now adjust the quantizations in case quantization has been applied to reflect the
        # new lengths
        self.qticks_notes = (self.qticks_notes * num) // denom
        self.qticks_durations = (self.qticks_durations * num) // denom

    def scale_ticks(self, scale_factor):
        """
        Scales the ticks for this track by scale_factor.

        :param scale_factor:
        """
        for i, (t, m) in enumerate(self.other):
            t = int(round(t * scale_factor, 0))
            self.other[i] = OtherMidiEvent(t, m)
        for i, p in enumerate(self.program_changes):
            t = int(round(p.start_time * scale_factor, 0))
            self.program_changes[i] = ProgramEvent(t, p.program)
        # Change all the note start times and durations
        for i, n in enumerate(self.notes):
            n.start_time = int(round(n.start_time * scale_factor, 0))
            n.duration = int(round(n.duration * scale_factor, 0))
            self.notes[i] = n
        self.qticks_notes = int(round(self.qticks_notes * scale_factor, 0))
        self.qticks_durations = int(round(self.qticks_durations * scale_factor, 0))

    def move_ticks(self, offset_ticks):
        """
        Moves all the events in this track by offset_ticks.  Any events that would have a time
        in ticks less than 0 are set to time zero.

        :param offset_ticks:
        :type offset_ticks: int (signed)
        """
        for i, (t, m) in enumerate(self.other):
            t = max(t + offset_ticks, 0)
            self.other[i] = OtherMidiEvent(t, m)
        for i, p in enumerate(self.program_changes):
            t = max(p.start_time + offset_ticks, 0)
            self.program_changes[i] = ProgramEvent(t, p.program)
        # Change all the note start times and durations
        for i, n in enumerate(self.notes):
            n.start_time = max(n.start_time + offset_ticks, 0)
            self.notes[i] = copy.copy(n)

    def set_program(self, program):
        '''
        Sets the default program (instrument) for the track at the start and
        removes any existing program changes.

        :param program: program number
        :type program: int
        '''
        self.program_changes = [ProgramEvent(0, int(program))]

    def __str__(self):
        ret_val = "Track: %s (channel %d)\n" % (self.name, self.channel)
        return ret_val + '\n'.join(str(n) for n in self.notes)


class ChirpSong(ChiptuneSAKBase):
    """
    This class represents a song. It stores notes in an intermediate representation that
    approximates traditional music notation (as pitch-duration).  It also stores other
    information, such as time signatures and tempi, in a similar way.
    """
    @classmethod
    def cts_type(cls):
        return 'Chirp'

    def __init__(self, mchirp_song=None):
        ChiptuneSAKBase.__init__(self)
        self.metadata = SongMetadata()
        self.metadata.ppq = constants.DEFAULT_MIDI_PPQN  #: Pulses (ticks) per quarter note. Default is 960.
        self.qticks_notes = self.metadata.ppq  #: Quantization for note starts, in ticks
        self.qticks_durations = self.metadata.ppq  #: Quantization for note durations, in ticks
        self.tracks = []  #: List of ChirpTrack tracks
        self.other = []  #: List of all meta events that apply to the song as a whole
        self.midi_meta_tracks = []  #: list of all the midi tracks that only contain metadata
        self.midi_note_tracks = []  #: list of all the tracks that contain notes
        self.time_signature_changes = []  #: List of time signature changes
        self.key_signature_changes = []  #: List of key signature changes
        self.tempo_changes = []  #: List of tempo changes
        if mchirp_song is not None:
            if mchirp_song.cts_type() != 'MChirp':
                raise ChiptuneSAKTypeError("ChirpSong init can only import MChirpSong objects")
            else:
                self.import_mchirp_song(mchirp_song)

    def reset_all(self):
        """
        Clear all tracks and reinitialize to default values
        """
        self.metadata = SongMetadata()
        self.metadata.ppq = constants.DEFAULT_MIDI_PPQN  #: Pulses (ticks) per quarter note.
        self.qticks_notes = self.metadata.ppq  #: Quantization for note starts, in ticks
        self.qticks_durations = self.metadata.ppq  #: Quantization for note durations, in ticks
        self.tracks = []  #: List of ChirpTrack tracks
        self.other = []  #: List of all meta events that apply to the song as a whole
        self.midi_meta_tracks = []  #: list of all the midi tracks that only contain metadata
        self.midi_note_tracks = []  #: list of all the tracks that contain notes
        self.time_signature_changes = []  #: List of time signature changes
        self.key_signature_changes = []  #: List of key signature changes
        self.tempo_changes = []  #: List of tempo changes

    def to_rchirp(self, **kwargs):
        """
        Convert to RChirp.  This calls the creation of an RChirp object

        :return: new RChirp object
        :rtype: rchirp.RChirpSong
        """
        self.set_options(**kwargs)
        self.set_metadata()
        return rchirp.RChirpSong(self)

    def to_mchirp(self, **kwargs):
        """
        Convert to MChirp.  This calls the creation of an MChirp object

        :return: new MChirp object
        :rtype: MChirpSong
        """
        self.set_options(**kwargs)
        self.set_metadata()
        return mchirp.MChirpSong(self)

    def import_mchirp_song(self, mchirp_song):
        """
        Imports an MChirpSong

        :param mchirp_song:
        :type mchirp_song: MChirpSong
        """
        self.reset_all()
        for t in mchirp_song.tracks:
            self.tracks.append(ChirpTrack(self, t))
        self.metadata = copy.deepcopy(mchirp_song.metadata)
        # Now transfer over key signature, time signature, and tempo changes
        # these are stored inside measures for ALL tracks so we only have to extract them from one.
        t = mchirp_song.tracks[0]
        self.time_signature_changes = [e for m in t.measures for e in m.events if isinstance(e, TimeSignatureEvent)]
        self.key_signature_changes = [e for m in t.measures for e in m.events if isinstance(e, KeySignatureEvent)]
        self.tempo_changes = [e for m in t.measures for e in m.events if isinstance(e, TempoEvent)]
        self.other = copy.deepcopy(mchirp_song.other)
        self.set_metadata()

    def set_metadata(self):
        """
        Sets the song metadata to reflect the current status of the song.  This function cleans up
        any redundant item signature, key signature, or tempo changes (two events that have the same
        timestamp) and keeps the last one it finds, then sets the metadata values to the first of each
        respectively.
        """
        # Eliminate redundant time signature changes
        if len(self.time_signature_changes) > 1:
            new_ts_changes = []
            current_ts = self.time_signature_changes[0]
            for i in range(1, len(self.time_signature_changes)):
                if self.time_signature_changes[i].start_time > self.time_signature_changes[i - 1].start_time:
                    new_ts_changes.append(current_ts)
                current_ts = self.time_signature_changes[i]
            new_ts_changes.append(current_ts)
            self.time_signature_changes = new_ts_changes

        # Set the time signature.  Note that this is a change event
        if len(self.time_signature_changes) > 0:
            self.metadata.time_signature = self.time_signature_changes[0]

        # Eliminate redundant key signature changes
        if len(self.key_signature_changes) > 1:
            new_ks_changes = []
            current_ks = self.key_signature_changes[0]
            for i in range(1, len(self.key_signature_changes)):
                if self.key_signature_changes[i].start_time > self.key_signature_changes[i - 1].start_time:
                    new_ks_changes.append(current_ks)
                current_ks = self.key_signature_changes[i]
            new_ks_changes.append(current_ks)
            self.key_signature_changes = new_ks_changes

        # Set the key signature; note that this is a change event
        if len(self.key_signature_changes) > 0:
            self.metadata.key_signature = self.key_signature_changes[0]

        # Eliminate redundant tempo changes
        if len(self.tempo_changes) > 1:
            new_qpm_changes = []
            current_ks = self.tempo_changes[0]
            for i in range(1, len(self.tempo_changes)):
                if self.tempo_changes[i].start_time > self.tempo_changes[i - 1].start_time:
                    new_qpm_changes.append(current_ks)
                current_ks = self.tempo_changes[i]
            new_qpm_changes.append(current_ks)
            self.tempo_changes = new_qpm_changes

        # Set the qpm; this is different because it is not a change event
        if len(self.tempo_changes) > 0:
            self.metadata.qpm = self.tempo_changes[0].qpm

    def estimate_quantization(self):
        """
        This method estimates the optimal quantization for note starts and durations from the note
        data itself. This version all note data in the tracks. Many pieces have no discernable
        duration quantization, so in that case the default is half the note start quantization.
        These values are easily overridden.
        """
        tmp_notes = [n.start_time for t in self.tracks for n in t.notes]
        self.qticks_notes = find_quantization(tmp_notes, self.metadata.ppq)
        tmp_durations = [n.duration for t in self.tracks for n in t.notes]
        self.qticks_durations = find_duration_quantization(tmp_durations, self.qticks_notes)
        if self.qticks_durations < self.qticks_notes:
            self.qticks_durations = self.qticks_notes // 2
        return (self.qticks_notes, self.qticks_durations)

    def quantize(self, qticks_notes=None, qticks_durations=None):
        """
        This method applies quantization to both note start times and note durations.  If you
        want either to remain unquantized, simply specify a qticks parameter to be 1 (quantization
        of 1 tick).

        :param qticks_notes:     Quantization for note starts, in MIDI ticks
        :type qticks_notes: int
        :param qticks_durations: Quantization for note durations, in MIDI ticks
        :type qticks_durations: int
        """

        if qticks_notes:
            self.qticks_notes = qticks_notes
        if qticks_durations:
            self.qticks_durations = qticks_durations
        for t in self.tracks:
            t.quantize(self.qticks_notes, self.qticks_durations)

        for i, m in enumerate(self.tempo_changes):
            self.tempo_changes[i] = TempoEvent(quantize_fn(m.start_time, self.qticks_notes), m.qpm)
        for i, m in enumerate(self.time_signature_changes):
            self.time_signature_changes[i] = \
                TimeSignatureEvent(quantize_fn(m.start_time, self.qticks_notes), m.num, m.denom)
        for i, m in enumerate(self.key_signature_changes):
            self.key_signature_changes[i] = KeySignatureEvent(quantize_fn(m.start_time, self.qticks_notes), m.key)
        for i, m in enumerate(self.other):
            self.other[i] = OtherMidiEvent(quantize_fn(m.start_time, self.qticks_notes), m.msg)

    def quantize_from_note_name(self, min_note_duration_string, dotted_allowed=False, triplets_allowed=False):
        """
        Quantize song with more user-friendly input than ticks.  Allowed quantizations are the keys for the
        constants.DURATION_STR dictionary.  If an input contains a '.' or a '-3' the corresponding
        values for dotted_allowed and triplets_allowed will be overridden.

        :param min_note_duration_string:  Quantization note value
        :type min_note_duration_string: str
        :param dotted_allowed:  If true, dotted notes are allowed
        :type dotted_allowed: bool
        :param triplets_allowed:  If true, triplets (of the specified quantization) are allowed
        :type triplets_allowed: bool
        """

        if '.' in min_note_duration_string:
            dotted_allowed = True
            min_note_duration_string = min_note_duration_string.replace('.', '')
        if '-3' in min_note_duration_string:
            triplets_allowed = True
            min_note_duration_string = min_note_duration_string.replace('-3', '')
        qticks = int(self.metadata.ppq * constants.DURATION_STR[min_note_duration_string])
        if dotted_allowed:
            qticks //= 2
        if triplets_allowed:
            qticks //= 3
        self.quantize(qticks, qticks)

    def is_quantized(self):
        """
        Has the song been quantized?  This requires that all the tracks have been quantized
        with their current qticks_notes and qticks_durations values.

        :return:  Boolean True if all tracks in the song are quantized
        """
        return all(t.is_quantized() for t in self.tracks)

    def explode_polyphony(self, i_track):
        """
        'Explodes' a single track into multi-track polyphony.  The new tracks replace the old
        track in the song's list of tracks, so later tracks will be pushed to higher indexes.
        The new tracks are named using the name of the original track with '_sx' appended, where
        x is a number for the split notes.
        The polyphony is split using a first-available-track algorithm, which works well for splitting chords.

        :param i_track:  zero-based index of the track for the song (ignore the meta track - first track is 0)
        :type i_track: int
        """
        def _get_available_tracks(note, current_notes):
            ret = []
            for it, n in enumerate(current_notes):
                if note.start_time >= n.start_time + n.duration:
                    ret.append(it)
            # ret.sort(key=lambda n: (-current_notes[n].note_num))
            return ret
        old_track = self.tracks.pop(i_track)
        old_track.notes.sort(key=lambda n: (n.start_time, -n.note_num))
        new_tracks = [ChirpTrack(self)]
        current_notes = [Note(0, 0, 0, 0)]
        for note in old_track.notes:
            possible = _get_available_tracks(note, current_notes)
            if len(possible) == 0:
                new_tracks.append(ChirpTrack(self))
                new_tracks[-1].notes.append(note)
                current_notes.append(note)
            else:
                it = possible[0]
                new_tracks[it].notes.append(note)
                current_notes[it] = note
        for i, t in enumerate(new_tracks):
            new_tracks[i].other = copy.deepcopy(old_track.other)
            new_tracks[i].channel = old_track.channel
            new_tracks[i].name = old_track.name + ' s%d' % i
        for t in new_tracks[::-1]:
            self.tracks.insert(i_track, t)

    def remove_polyphony(self):
        """
        Eliminate polyphony from all tracks.
        """
        for t in self.tracks:
            t.remove_polyphony()

    def is_polyphonic(self):
        """
        Is the song polyphonic?  Returns true if ANY of the tracks contains polyphony of any kind.

        :return: Boolean True if any track in the song is polyphonic
        :rtype: bool
        """
        return any(t.is_polyphonic() for t in self.tracks)

    def remove_keyswitches(self, ks_max=8):
        """
        Some MIDI programs use extremely low notes as a signaling mechanism.
        This method removes notes with pitch <= ks_max from all tracks.

        :param ks_max:  Maximum note number for the control notes
        :type ks_max: int
        """
        for t in self.tracks:
            t.remove_keyswitches(ks_max)

    def truncate(self, max_tick):
        """
        Truncate the song to max_tick

        :param max_tick:  maximum tick number for events to start (song will play to end of any
            notes started)
        :type max_tick: int
        """
        self.time_signature_changes = [ts for ts in self.time_signature_changes if ts.start_time <= max_tick]
        self.key_signature_changes = [ks for ks in self.key_signature_changes if ks.start_time <= max_tick]
        self.tempo_changes = [t for t in self.tempo_changes if t.start_time <= max_tick]
        self.other = [e for e in self.other if e.start_time <= max_tick]
        for t in self.tracks:
            t.truncate(max_tick)

    def transpose(self, semitones, minimize_accidentals=True):
        """
        Transposes the song by semitones

        :param semitones:  number of semitones to transpose by.  Positive transposes to higher pitch.
        :type semitones: int
        :param minimize_accidentals: True to choose key signature to minimize number of accidentals
        :type minimize_accidentals: bool
        """
        # First, transpose key signatures
        for ik, ks in enumerate(self.key_signature_changes):
            new_key = ks.key.transpose(semitones)
            if minimize_accidentals:
                new_key.minimize_accidentals()
            self.key_signature_changes[ik] = KeySignatureEvent(ks.start_time, new_key)
            if ik == 0:
                self.metadata.key_signature = self.key_signature_changes[0]

        # Now transpose the tracks
        for it, t in enumerate(self.tracks):
            self.tracks[it].transpose(semitones)

    def modulate(self, num, denom):
        """
        This method performs metric modulation.  It does so by multiplying the length of all notes by num/denom,
        and also automatically adjusts the time signatures and tempos such that the resulting music will sound
        identical to the original.

        :param num:    Numerator of metric modulation
        :type num: int
        :param denom:  Denominator of metric modulation
        :type denom: int
        """
        f = Fraction(num, denom).limit_denominator(32)
        num = f.numerator
        denom = f.denominator
        # First adjust the time signatures
        for i, ts in enumerate(self.time_signature_changes):
            # The time signature always has to be whole numbers so if the new numerator is not an integer fix that
            #  by multiplying by 3/2
            t, n, d = ts
            new_time_signature = (n * num, d * denom)
            if num < denom:
                if all((v % 4) == 0 for v in new_time_signature):
                    factor = new_time_signature[1] // 4
                    if all((v % factor) == 0 for v in new_time_signature):
                        new_time_signature = (v // factor for v in new_time_signature)
            self.time_signature_changes[i] = TimeSignatureEvent((t * num) // denom, *new_time_signature)
            if i == 0:
                self.metadata.time_signature = self.time_signature_changes[0]
        # Now the key signatures
        for i, ks in enumerate(self.key_signature_changes):
            # The time signature always has to be whole numbers so if the new numerator is not an integer fix that
            #  by multiplying by 3/2
            t, k = ks
            self.key_signature_changes[i] = KeySignatureEvent((t * num) // denom, k)
        # Next the tempos
        for i, tm in enumerate(self.tempo_changes):
            t, qpm = tm
            self.tempo_changes[i] = TempoEvent((t * num) // denom, (qpm * num) // denom)
        # Now all the rest of the meta messages
        for i, ms in enumerate(self.other):
            t, m = ms
            self.other[i] = OtherMidiEvent((t * num) // denom, m)
        # Finally, modulate each track
        for i, _ in enumerate(self.tracks):
            self.tracks[i].modulate(num, denom)
        # Now adjust the quantizations in case quantization has been applied to reflect the new lengths
        self.qticks_notes = (self.qticks_notes * num) // denom
        self.qticks_durations = (self.qticks_durations * num) // denom
        # Now adjust everything to be self-consistent
        self.set_metadata()

    def scale_ticks(self, scale_factor):
        """
        Scales the ticks for all events in the song.  Multiplies the time for each event by scale_factor.
        This method also changes the ppq by the scale factor.

        :param scale_factor: Floating-point scale factor to multiply all events.
        :type scale_factor: float
        """
        self.metadata.ppq = int(round(self.metadata.ppq * scale_factor, 0))
        # First adjust the time signatures
        for i, ts in enumerate(self.time_signature_changes):
            # The time signature always has to be whole numbers so if the new numerator is not an integer fix that
            #  by multiplying by 3/2
            t = int(round(ts.start_time * scale_factor, 0))
            self.time_signature_changes[i] = TimeSignatureEvent(t, ts.num, ts.denom)
        # Now the key signature changes
        for i, ks in enumerate(self.key_signature_changes):
            t = int(round(ks.start_time * scale_factor, 0))
            self.key_signature_changes[i] = KeySignatureEvent(t, ks.key)
        # Next the tempos
        for i, tm in enumerate(self.tempo_changes):
            t = int(round(tm.start_time * scale_factor, 0))
            self.tempo_changes[i] = TempoEvent(t, tm.qpm)
        # Now all the rest of the meta messages
        for i, ms in enumerate(self.other):
            t = int(round(ms.start_time * scale_factor, 0))
            self.other[i] = OtherMidiEvent(t, ms.msg)
        # Now adjust the quantizations in case quantization has been applied to reflect the new lengths
        self.qticks_notes = int(round(self.qticks_notes * scale_factor, 0))
        self.qticks_durations = int(round(self.qticks_durations * scale_factor, 0))
        # Finally, scale each track
        for i, _ in enumerate(self.tracks):
            self.tracks[i].scale_ticks(scale_factor)

    def move_ticks(self, offset_ticks):
        """
        Moves all notes in the song a given number of ticks.  Adds the offset to the current tick for every event.
        If the resulting event has a negative starting time in ticks, it is set to 0.

        :param offset_ticks:  Offset in ticks
        :type offset_ticks: int
        """
        # First adjust the time signatures
        for i, ts in enumerate(self.time_signature_changes):
            # The time signature always has to be whole numbers so if the new numerator is not an integer fix that
            #  by multiplying by 3/2
            t = max(ts.start_time + offset_ticks, 0)
            self.time_signature_changes[i] = TimeSignatureEvent(t, ts.num, ts.denom)
        # Now the key signature changes
        for i, ks in enumerate(self.key_signature_changes):
            t = max(ks.start_time + offset_ticks, 0)
            self.key_signature_changes[i] = KeySignatureEvent(t, ks.key)
        # Next the tempos
        for i, tm in enumerate(self.tempo_changes):
            t = max(tm.start_time + offset_ticks, 0)
            self.tempo_changes[i] = TempoEvent(t, tm.qpm)
        # Now all the rest of the meta messages
        for i, ms in enumerate(self.other):
            t = max(ms.start_time + offset_ticks, 0)
            self.other[i] = OtherMidiEvent(t, ms.msg)
        # Finally, offset each track
        for i, _ in enumerate(self.tracks):
            self.tracks[i].move_ticks(offset_ticks)

    def set_qpm(self, qpm):
        """
        Sets the tempo in QPM for the entire song.  Any existing tempo events will be removed.

        :param qpm: quarter-notes per minute tempo
        :type qpm: int
        """
        self.metadata.qpm = qpm
        self.tempo_changes = [TempoEvent(0, qpm)]

    def set_time_signature(self, num, denom):
        """
        Sets the time signature for the entire song.  Any existing time signature changes will be removed.

        :param num:
        :type num:
        :param denom:
        :type num:
        """
        self.time_signature_changes = [TimeSignatureEvent(0, num, denom)]

    def set_key_signature(self, new_key):
        """
        Sets the key signature for the entire song.  Any existing key signatures and changes will be removed.

        :param new_key: Key signature.  String such as 'A#' or 'Abm'
        :type new_key: str
        """
        self.key_signature_changes = [KeySignatureEvent(0, key.ChirpKey(new_key))]

    def end_time(self):
        """
        Finds the end time of the last note in the song.

        :return: Time (in ticks) of the end of the last note in the song.
        :rtype: int
        """
        return max(n.start_time + n.duration for t in self.tracks for n in t.notes)

    def measure_starts(self):
        """
        Returns the starting time for measures in the song.  Calculated using time_signature_changes.

        :return: List of measure starting times in MIDI ticks
        :rtype: list
        """
        return [m.start_time for m in self.measures_and_beats() if m.beat == 1]

    def measures_and_beats(self):
        """
        Returns the positions of all measures and beats in the song.  Calculated using time_signature_changes.

        :return: List of MeasureBeat objects for each beat of the song.
        :rtype: list
        """
        measures = []
        max_time = self.end_time()
        time_signature_changes = sorted(self.time_signature_changes)
        if len(time_signature_changes) == 0 or time_signature_changes[0].start_time != 0:
            raise ChiptuneSAKValueError("No starting time signature")
        last = time_signature_changes[0]
        t, m, b = 0, 1, 1
        for s in time_signature_changes:
            while t < s.start_time:
                measures.append(Beat(t, m, b))
                t += (self.metadata.ppq * 4) // last.denom
                b += 1
                if b > last.num:
                    m += 1
                    b = 1
            last = s
        while t <= max_time:
            measures.append(Beat(t, m, b))
            t += (self.metadata.ppq * 4) // last.denom
            b += 1
            if b > last.num:
                m += 1
                b = 1
        return measures

    def get_measure_beat(self, time_in_ticks):
        """
        This method returns a (measure, beat) tuple for a given time; the time is greater than or
        equal to the returned measure and beat but less than the next.  The result should be
        interpreted as the time being during the measure and beat returned.

        :param time_in_ticks:  Time during the song, in MIDI ticks
        :type time_in_ticks: int
        :return:  MeasureBeat object with the current measure and beat
        :rtype: MeasureBeat
        """
        measure_beats = self.measures_and_beats()
        # Make a list of start times from the list of measure-beat times.
        tmp = [m.start_time for m in measure_beats]
        # Find the index of the desired time in the list.
        pos = bisect.bisect_right(tmp, time_in_ticks)
        # Return the corresponding measure/beat
        return measure_beats[pos - 1]

    def get_active_time_signature(self, time_in_ticks):
        """
        Get the active time signature at a given time (in ticks) during the song.

        :param time_in_ticks:  Time during the song, in MIDI ticks
        :type time_in_ticks: int
        :return: Active time signature at the time
        :rtype: TimeSignatureChange
        """
        itime = 0
        if len(self.time_signature_changes) == 0 or self.time_signature_changes[0].start_time != 0:
            raise ChiptuneSAKValueError("No starting time signature")
        n_time_signature_changes = len(self.time_signature_changes)
        while itime < n_time_signature_changes and self.time_signature_changes[itime].start_time < time_in_ticks:
            itime += 1
        return self.time_signature_changes[itime - 1]

    def get_active_key_signature(self, time_in_ticks):
        """
        Get the active key signature at a given time (in ticks) during the song.

        :param time_in_ticks: Time during the song, in MIDI ticks
        :type time_in_ticks: int
        :return: Key signature active at the time
        :rtype: KeySignatureChange
        """
        ikey = 0
        if len(self.key_signature_changes) == 0 or self.key_signature_changes[0].start_time != 0:
            raise ChiptuneSAKValueError("No starting time signature")
        n_key_signature_changes = len(self.key_signature_changes)
        while ikey < n_key_signature_changes and self.key_signature_changes[ikey].start_time < time_in_ticks:
            ikey += 1
        return self.key_signature_changes[ikey - 1]


# --------------------------------------------------------------------------------------
#
#  Utility functions
#
# --------------------------------------------------------------------------------------

def quantization_error(t_ticks, q_ticks):
    """
    Calculate the error, in ticks, for the given time for a quantization of q ticks.

    :param t_ticks: time in ticks
    :type t_ticks: int
    :param q_ticks: quantization in ticks
    :type q_ticks: int
    :return: quantization error, in ticks
    :rtype: int
    """
    j = t_ticks // q_ticks
    return int(min(abs(t_ticks - q_ticks * j), abs(t_ticks - q_ticks * (j + 1))))


def objective_error(note_start_times, test_quantization):
    """
    This is the objective function for getting the error for the entire set of notes for a
    given quantization in ticks.  The function used here could be a sum, RMS, or other
    statistic, but empirical tests indicate that the max used here works well and is robust.

    :param note_start_times: note start times in ticks
    :type note_start_times: list of int
    :param test_quantization: test quantization, in ticks
    :type test_quantization: int
    :return: objective error function value
    :rtype: int
    """
    return max(quantization_error(n, test_quantization) for n in note_start_times)


def find_quantization(time_series, ppq):
    """
    Find the optimal quantization in ticks to use for a given set of times.  The algorithm given
    here is by no means universal or guaranteed, but it usually gives a sensible answer.

    The algorithm works as follows:
    - Starting with quarter notes, obtain the error from quantization of the entire set of times.
    - Then obtain the error from quantization by 2/3 that value (i.e. triplets).
    - Then go to the next power of two (e.g. 8th notes, a6th notes, etc.) and repeat

    A minimum in quantization error will be observed at the "right" quantization.  In either case
    above, the next quantization tested will be incommensurate (either a factor of 2/3 or a factor
    of 3/4) which will make the quantization error worse.

    Thus, the first minimum that appears will be the correct value.

    The algorithm does not seem to work as well for note durations as it does for note starts, probably
    because performed music rarely has clean note cutoffs.

    :param time_series: a series times, usually note start times, in ticks
    :type time_series: list of int
    :param ppq: ppq value (ticks per quarter note)
    :type ppq: int
    :return: quantization in ticks
    :rtype: int
    """
    last_err = len(time_series) * ppq
    last_q = ppq
    note_value = 4
    while note_value <= 128:  # We have arbitrarily chosen 128th notes as the fastest possible
        test_quantization = ppq * 4 // note_value
        e = objective_error(time_series, test_quantization)
        # print(test_quantization, e) # This was useful for observing the behavior of real-world music
        if e == 0:  # Perfect quantization!  We are done.
            return test_quantization
        # If this is worse than the last one, the last one was the right one.
        elif e > last_err:
            return last_q
        last_q = test_quantization
        last_err = e

        # Now test the quantization for triplets of the current note value.
        test_quantization = test_quantization * 2 // 3
        e = objective_error(time_series, test_quantization)
        # print(test_quantization, e) # This was useful for observing the behavior of real-world music
        if e == 0:  # Perfect quantization!  We are done.
            return test_quantization
            # If this is worse than the last one, the last one was the right one.
        elif e > last_err:
            return last_q
        last_q = test_quantization
        last_err = e

        # Try the next power of two
        note_value *= 2
    return 1  # Return a 1 for failed quantization means 1 tick resolution


def find_duration_quantization(durations, qticks_note):
    """
    The duration quantization is determined from the shortest note length.
    The algorithm starts from the estimated quantization for note starts.

    :param durations: durations from which to estimate quantization
    :type durations: list of int
    :param qticks_note: quantization already determined for note start times
    :type qticks_note: int
    :return: estimated duration quantization, in ticks
    :rtype: int
    """
    min_length = min(durations)
    if not (min_length > 0):
        raise ChiptuneSAKQuantizationError("Illegal minimum note length (%d)" % min_length)
    current_q = qticks_note
    ratio = min_length / current_q
    while ratio < 0.9:
        # Try a triplet
        tmp_q = current_q
        current_q = current_q * 3 // 2
        ratio = min_length / current_q
        if ratio > 0.9:
            break
        current_q = tmp_q // 2
        ratio = min_length / current_q
    return current_q


def quantize_fn(t, qticks):
    """
    This function quantizes a time or duration to a certain number of ticks.  It snaps to the
    nearest quantized value.

    :param t: a start time or duration, in ticks
    :type t: int
    :param qticks: quantization in ticks
    :type qticks: int
    :return: quantized start time or duration
    :rtype: int
    """
    current = t // qticks
    next = current + 1
    current *= qticks
    next *= qticks
    if abs(t - current) <= abs(next - t):
        return current
    else:
        return next
