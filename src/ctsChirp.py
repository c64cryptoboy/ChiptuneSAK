# Midi Simple Processing Library
#
# 2019, David Knapp / David Youd
#
# Recommended Python version installed >= 3.7.4
# Must first install midi: https://github.com/olemb/mido/blob/master/docs/installing.rst
#    pip install mido
#

import sys
import copy
import bisect
import more_itertools as moreit
from ctsErrors import *
from ctsConstants import *
from ctsBase import *

class Note:
    """
    This class represents a note in human-friendly form:  as a note with a start time, a duration, and
    a velocity. 
    """

    def __init__(self, start, note, duration, velocity=100, tied_from=False, tied_to=False):
        self.note_num = note  # MIDI note number
        self.start_time = start  # In ticks since tick 0
        self.duration = duration  # In ticks
        self.velocity = velocity  # MIDI velocity 0-127
        self.tied_from = tied_from  # Is the next note tied from this note?
        self.tied_to = tied_to  # Is this note ties from the previous note?

    def __eq__(self, other):
        """ Two notes are equal when their note numbers and durations are the same """
        return (self.note_num == other.note_num) and (self.duration == other.duration)

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
    other_message_types = ['program_change', 'pitchwheel', 'control_change']

    def __init__(self, chirp_song, mchirp_track=None):
        self.chirp_song = chirp_song  # Parent song
        self.name = 'none'  # Track name
        self.channel = 0  # This track's midi channel.  Each track should have notes from only one channel.
        self.notes = []  # The notes in the track
        self.other = []  # Other events in the track (includes voice changes and pitchwheel)
        self.qticks_notes = chirp_song.qticks_notes  # Inherit quantization from song
        self.qticks_durations = chirp_song.qticks_durations  # inherit quantization from song
        if mchirp_track is not None:
            self.import_mchirp_track(mchirp_track)

    def import_mchirp_track(self, mchirp_track):
        """
        Imports an  MChirpTrack
            :param mchirp_track:
        """
        self.name = mchirp_track.name
        self.channel = mchirp_track.channel
        continued_note = None
        for m in mchirp_track.measures:
            for e in m.events:
                if isinstance(e, Note):
                    if continued_note is not None:
                        continued_note.duration += e.duration
                        if not e.tied_from:
                            self.notes.append(continued_note)
                            continued_note = None
                    else:
                        new_note = Note(e.start_time, e.note_num, e.duration, e.velocity)
                        if e.tied_from:
                            continued_note = copy.copy(new_note)
                        else:
                            self.notes.append(new_note)
                            continued_note = None
                elif isinstance(e, OtherMidi):
                    self.other.append(e)
        self.notes.sort(key=lambda n: (n.start_time, -n.note_num))
        self.other.sort(key=lambda n: n.start_time)

    def estimate_quantization(self):
        """ 
        This method estimates the optimal quantization for note starts and durations from the note
        data itself. This version only uses the current track for the optimization.  If the track
        is a part with long notes or not much movement, I recommend using the get_quantization()
        on the entire song instead. Many pieces have fairly well-defined note start spacing, but 
        no discernable duration quantization, so in that case the default is half the note start 
        quantization.  These values are easily overridden.
        """
        tmpNotes = [n.start_time for n in self.notes]
        self.qticks_notes = find_quantization(self.chirp_song.metadata.ppq, tmpNotes)
        tmpNotes = [n.duration for n in self.notes]
        self.qticks_durations = find_quantization(self.chirp_song.metadata.ppq, tmpNotes)
        if self.qticks_durations < self.qticks_notes:
            self.qticks_durations = self.qticks_notes // 2
        return (self.qticks_notes, self.qticks_durations)

    def quantize(self, qticks_notes=None, qticks_durations=None):
        """
        This method applies quantization to both note start times and note durations.  If you 
        want either to remain unquantized, simply specify either qticks parameter to be 1, so
        that it will quantize to the nearest tick (i.e. leave everything unchanged)
        """
        note_start_changes = []
        duration_changes = []
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
            # Update the statistics
            note_start_changes.append(n.start_time - start_before)
            duration_changes.append(n.duration - duration_before)

        # Quantize the other MIDI messages in the track
        for i, m in enumerate(self.other):
            self.other[i] = OtherMidi(quantize_fn(m.start_time, self.qticks_notes), m.msg)

        # Return the statistics about changes
        return (note_start_changes, duration_changes)

    def remove_polyphony(self):
        """
        This function eliminates polyphony, so that in each channel there is only one note
        active at a time. If a chord is struck all at the same time, it will retain the highest
        note.
        """
        deleted = 0
        truncated = 0
        ret_notes = []
        last = self.notes[0]
        for n in self.notes[1:]:
            if n.start_time == last.start_time:
                deleted += 1
                continue
            elif n.start_time < last.start_time + last.duration:
                last.duration = n.start_time - last.start_time
                truncated += 1
            if last.duration <= 0:
                deleted += 1
            ret_notes.append(last)
            last = n
        ret_notes.append(last)
        self.notes = ret_notes
        self.notes.sort(key=lambda n: (n.start_time, -n.note_num))
        return (deleted, truncated)

    def is_polyphonic(self):
        return any(b.start_time - a.start_time < a.duration for a, b in moreit.pairwise(self.notes))

    def is_quantized(self):
        if self.qticks_notes < 4 or self.qticks_durations < 4:
            return False
        return all(n.start_time % self.qticks_notes == 0
                   and n.duration % self.qticks_durations == 0
                   for n in self.notes)

    def remove_control_notes(self, control_max=8):
        """
        Removes all MIDI notes with values less than or equal to control_max.
        Some MIDI devices and applications use these extremely low notes to
        convey patch change or other information, so removing them (especially 
        you don't want polyphony) is a good idea.
        """
        self.notes = [n for n in self.notes if n.note_num > control_max]

    def transpose(self, semitones):
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
        """
        # Change the start times of all the "other" events
        for i, (t, m) in enumerate(self.other):
            t = (t * num) // denom
            self.other[i] = OtherMidi(t, m)

        # Change all the note start times and durations
        for i, n in enumerate(self.notes):
            n.start_time = (n.start_time * num) // denom
            n.duration = (n.duration * num) // denom
            self.notes[i] = n

    def scale_ticks(self, scale_factor):
        """
        Scales the ticks for this track by scale_factor.
            :param scale_factor:
        """
        for i, (t, m) in enumerate(self.other):
            t = int(round(t * scale_factor, 0))
            self.other[i] = OtherMidi(t, m)
        # Change all the note start times and durations
        for i, n in enumerate(self.notes):
            n.start_time = int(round(n.start_time * scale_factor, 0))
            n.duration = int(round(n.duration * scale_factor, 0))
            self.notes[i] = n
        self.qticks_notes = int(round(self.qticks_notes * scale_factor, 0))
        self.qticks_durations = int(round(self.qticks_durations * scale_factor, 0))

    def move_ticks(self, offset_ticks):
        """
        Moves all the events in this track by offset_ticks.  Any events that would have a time in ticks less than 0 are
        set to time zero.
            :param offset_ticks:
        """
        for i, (t, m) in enumerate(self.other):
            t = max(t + offset_ticks, 0)
            self.other[i] = OtherMidi(t, m)
        # Change all the note start times and durations
        for i, n in enumerate(self.notes):
            n.start_time = max(n.start_time + offset_ticks, 0)
            self.notes[i] = n

    def __str__(self):
        ret_val = "Track: %s (channel %d)\n" % (self.name, self.channel)
        return ret_val + '\n'.join(str(n) for n in self.notes)


class ChirpSong:
    """
    This class represents a song. It stores notes in an intermediate representation that
    approximates traditional music notationh (as pitch-duration).  It also stores other 
    information, such as time signatures and tempi, in a similar way.
    """

    def __init__(self, mchirp_song=None):
        self.reset_all()
        if mchirp_song is not None:
            self.import_mchirp_song(mchirp_song)

    def reset_all(self):
        """ 
        Clear all tracks and reinitialize to default values
        """
        self.metadata = SongMetadata()
        self.metadata.ppq = 960  # Pulses (ticks) per quarter note. Default is 960, which is commonly used.
        self.qticks_notes = self.metadata.ppq  # Quantization for note starts, in ticks
        self.qticks_durations = self.metadata.ppq  # Quantization for note durations, in ticks
        self.tracks = []  # List of ChirpTrack tracks
        self.other = []  # List of all meta events that apply to the song as a whole
        self.midi_meta_tracks = []  # list of all the midi tracks that only contain metadata
        self.midi_note_tracks = []  # list of all the tracks that contain notes
        self.time_signature_changes = []  # List of time signature changes
        self.key_signature_changes = []  # List of key signature changes
        self.tempo_changes = []  # List of tempo changes
        self.stats = {}  # Statistics about the song

    def import_mchirp_song(self, mchirp_song):
        """
        Imports an MChirpSong
            :param mchirp_song:
        """
        for t in mchirp_song.tracks:
            self.tracks.append(ChirpTrack(self, t))
        self.metadata = copy.deepcopy(mchirp_song.metadata)
        # Now transfer over key signature, time signature, and tempo changes
        # these are stored inside measures for ALL tracks so we only have to extract them from one.
        t = mchirp_song.tracks[0]
        self.time_signature_changes = [e for m in t.measures for e in m.events if isinstance(e, TimeSignature)]
        self.key_signature_changes= [e for m in t.measures for e in m.events if isinstance(e, KeySignature)]
        self.tempo_changes = [e for m in t.measures for e in m.events if isinstance(e, Tempo)]
        self.other = copy.deepcopy(mchirp_song.other)

    def estimate_quantization(self):
        """ 
        This method estimates the optimal quantization for note starts and durations from the note
        data itself. This version all note data in the tracks. Many pieces have no discernable 
        duration quantization, so in that case the default is half the note start quantization.  
        These values are easily overridden.
        """
        tmp_notes = [n.start_time for t in self.tracks for n in t.notes]
        self.qticks_notes = find_quantization(self.metadata.ppq, tmp_notes)
        tmp_durations = [n.duration for t in self.tracks for n in t.notes]
        self.qticks_durations = find_duration_quantization(self.metadata.ppq, tmp_durations, self.qticks_notes)
        if self.qticks_durations < self.qticks_notes:
            self.qticks_durations = self.qticks_notes // 2
        return (self.qticks_notes, self.qticks_durations)

    def quantize(self, qticks_notes=None, qticks_durations=None):
        """
        This method applies quantization to both note start times and note durations.  If you
        want either to remain unquantized, simply specify a qticks parameter to be 1 (quantization
        of 1 tick).

            :param qticks_notes:     Quantization for note starts, in MIDI ticks
            :param qticks_durations: Quantization for note durations, in MIDI ticks
        """

        self.stats['Note Start Deltas'] = collections.Counter()
        self.stats['Duration Deltas'] = collections.Counter()
        if qticks_notes:
            self.qticks_notes = qticks_notes
        if qticks_durations:
            self.qticks_durations = qticks_durations
        for t in self.tracks:
            note_start_changes, duration_changes = t.quantize(self.qticks_notes, self.qticks_durations)
            self.stats['Note Start Deltas'].update(note_start_changes)
            self.stats['Duration Deltas'].update(duration_changes)

        for i, m in enumerate(self.tempo_changes):
            self.tempo_changes[i] = Tempo(quantize_fn(m.start_time, self.qticks_notes), m.bpm)
        for i, m in enumerate(self.time_signature_changes):
            self.time_signature_changes[i] = TimeSignature(quantize_fn(m.start_time, self.qticks_notes), m.num, m.denom)
        for i, m in enumerate(self.key_signature_changes):
            self.key_signature_changes[i] = KeySignature(quantize_fn(m.start_time, self.qticks_notes), m.key)
        for i, m in enumerate(self.other):
            self.other[i] = OtherMidi(quantize_fn(m.start_time, self.qticks_notes), m.msg)

    def quantize_from_note_name(self, min_note_duration_string, dotted_allowed=False, triplets_allowed=False):
        """
        Quantize song with more user-friendly input than ticks.  Allowed quantizations are the keys for the
        ctsConstants.DURATION_STR dictionary.  If an input contains a '.' or a '-3' the corresponding
        values for dotted_allowed and triplets_allowed will be overridden.

            :param min_note_duration_string:  Quantization note value
            :param dotted_allowed:  If true, dotted notes are allowed
            :param triplets_allowed:  If true, triplets (of the specified quantization) are allowed
        """

        if '.' in min_note_duration_string:
            dotted_allowed = True
            min_note_duration_string = min_note_duration_string.replace('.', '')
        if '-3' in min_note_duration_string:
            triplets_allowed = True
            min_note_duration_string = min_note_duration_string.replace('-3', '')
        qticks = int(self.metadata.ppq * DURATION_STR[min_note_duration_string])
        if dotted_allowed:
            qticks //= 2
        if triplets_allowed:
            qticks //= 3
        self.quantize(qticks, qticks)

    def remove_polyphony(self):
        """
        Eliminate polyphony from all tracks.
        """
        self.stats['Truncated'] = 0
        self.stats['Deleted'] = 0
        for t in self.tracks:
            deleted, truncated = t.remove_polyphony()
            self.stats['Truncated'] += truncated
            self.stats['Deleted'] += deleted

    def is_polyphonic(self):
        """
        Is the song polyphonic?  Returns true if ANY of the tracks contains polyphony of any kind.

            :return: Boolean True if any track in the song is polyphonic
        """
        return any(t.is_polyphonic() for t in self.tracks)

    def is_quantized(self):
        """
        Has the song been quantized?  This requires that all the tracks have been quantized with their
        current qticks_notes and qticks_durations values.

            :return:  Boolean True if all tracks in the song are quantized
        """
        return all(t.is_quantized() for t in self.tracks)

    def remove_control_notes(self, control_max=8):
        """
        Some MIDI programs use extremely low notes as a signaling mechanism.
        This method removes notes with pitch <= control_max from all tracks.

            :param control_max:  Maximum note number for the control notes
        """
        for t in self.tracks:
            t.remove_control_notes(control_max)

    def transpose(self, semitones):
        """
        Transposes the song by semitones
            :param semitones:  number of semitones to transpose by.  Positive transposes to higher pitch.
        """
        # First, transpose key signatures
        for ik, ks in enumerate(self.key_signature_changes):
            for key_type in ['major', 'minor']:
                if ks.key in KEYS[key_type]:
                    idx = KEYS[key_type].index(ks.key)
                    idx = (idx + semitones) % 12
                    self.key_signature_changes[ik] = KeySignature(ks.start_time, KEYS[key_type][idx])

        # Now transpose the tracks
        for it, t in self.tracks:
            self.tracks[it].transpose(semitones)

    def modulate(self, num, denom):
        """
        This method performs metric modulation.  It does so by multiplying the length of all notes by num/denom,
        and also automatically adjusts the time signatures and tempos such that the resulting music will sound
        identical to the original.

            :param num:    Numerator of metric modulation
            :param denom:  Denominator of metric modulation
        """
        # First adjust the time signatures
        for i, ts in enumerate(self.time_signature_changes):
            # The time signature always has to be whole numbers so if the new numerator is not an integer fix that
            #  by multiplying by 3/2
            t, n, d = ts
            self.time_signature_changes[i] = TimeSignature((t * num) // denom, n * num, d * denom)
        # Now the key signatures
        for i, ks in enumerate(self.key_signature_changes):
            # The time signature always has to be whole numbers so if the new numerator is not an integer fix that
            #  by multiplying by 3/2
            t, k = ks
            self.key_signature_changes[i] = KeySignature((t * num) // denom, k)
        # Next the tempos
        for i, tm in enumerate(self.tempo_changes):
            t, bpm = tm
            self.tempo_changes[i] = Tempo((t * num) // denom, (bpm * num) // denom)
        # Now all the rest of the meta messages
        for i, ms in enumerate(self.other):
            t, m = ms
            self.other[i] = OtherMidi((t * num) // denom, m)
        # Finally, modulate each track
        for i, _ in enumerate(self.tracks):
            self.tracks[i].modulate(num, denom)
        # Now adjust the quantizations in case quantization has been applied to reflect the new lengths
        self.qticks_notes = (self.qticks_notes * n) // d
        self.qticks_durations = (self.qticks_durations * n) // d

    def scale_ticks(self, scale_factor):
        """
        Scales the ticks for all events in the song.  Multiplies the time for each event by scale_factor.
        This method also changes the ppq by the scale factor.
            :param scale_factor: Floating-point scale factor to multiply all events.
        """
        self.metadata.ppq = int(round(self.metadata.ppq * scale_factor, 0))
        # First adjust the time signatures
        for i, ts in enumerate(self.time_signature_changes):
            # The time signature always has to be whole numbers so if the new numerator is not an integer fix that
            #  by multiplying by 3/2
            t = int(round(ts.start_time * scale_factor, 0))
            self.time_signature_changes[i] = TimeSignature(t, ts.num, ts.denom)
        # Now the key signature changes
        for i, ks in enumerate(self.key_signature_changes):
            t = int(round(ks.start_time * scale_factor, 0))
            self.key_signature_changes[i] = KeySignature(t, ks.key)
        # Next the tempos
        for i, tm in enumerate(self.tempo_changes):
            t = int(round(tm.start_time * scale_factor, 0))
            self.tempo_changes[i] = Tempo(t, tm.bpm)
        # Now all the rest of the meta messages
        for i, ms in enumerate(self.other):
            t = int(round(ms.start_time * scale_factor, 0))
            self.other[i] = OtherMidi(t, ms.msg)
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
        """
        # First adjust the time signatures
        for i, ts in enumerate(self.time_signature_changes):
            # The time signature always has to be whole numbers so if the new numerator is not an integer fix that
            #  by multiplying by 3/2
            t = max(ts.start_time + offset_ticks, 0)
            self.time_signature_changes[i] = TimeSignature(t, ts.num, ts.denom)
        # Now the key signature changes
        for i, ks in enumerate(self.key_signature_changes):
            t = max(ks.start_time + offset_ticks, 0)
            self.key_signature_changes[i] = KeySignature(t, ks.key)
        # Next the tempos
        for i, tm in enumerate(self.tempo_changes):
            t = max(tm.start_time + offset_ticks, 0)
            self.tempo_changes[i] = Tempo(t, tm.bpm)
        # Now all the rest of the meta messages
        for i, ms in enumerate(self.other):
            t = max(ms.start_time + offset_ticks, 0)
            self.other[i] = OtherMidi(t, ms.msg)
        # Finally, offset each track
        for i, _ in enumerate(self.tracks):
            self.tracks[i].move_ticks(offset_ticks)

    def set_bpm(self, bpm):
        """
        Sets the tempo in BPM for the entire song.  Any existing tempo events will be removed.
            :param bpm:
        """
        self.metadata.bpm = bpm
        self.tempo_changes = [Tempo(0, bpm)]

    def set_time_signature(self, num, denom):
        """
        Sets the time signature for the entire song.  Any existing time signature changes will be removed.
            :param num:
            :param denom:
        """
        self.time_signature_changes = [TimeSignature(0, num, denom)]

    def set_key_signature(self, key):
        """
        Sets the key signature for the entire song.  Any existing key signatures and changes will be removed.
            :param key:
        """
        self.key_signature_changes = [KeySignature(0, key)]

    def end_time(self):
        """
        Finds the end time of the last note in the song.

            :return: Time (in ticks) of the end of the last note in the song.
        """
        return max(n.start_time + n.duration for t in self.tracks for n in t.notes)

    def measure_starts(self):
        """
        Returns the starting time for measures in the song.  Calculated using time_signature_changes.

            :return: List of measure starting time in MIDI ticks
        """
        return [m.start_time for m in self.measures_and_beats() if m.beat == 1]

    def measures_and_beats(self):
        """
        Returns the positions of all measures and beats in the song.  Calculated using time_signature_changes.

            :return: List of MeasureBeat objects for each beat of the song.
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
        self.stats['Measures'] = m
        return measures

    def get_measure_beat(self, time_in_ticks):
        """
        This method returns a (measure, beat) tuple for a given time; the time is greater than or
        equal to the returned measure and beat but less than the next.  The result should be
        interpreted as the time being during the measure and beat returned.

        :param time_in_ticks:  Time during the song, in MIDI ticks
        :return:  MeasureBeat object with the current measure and beat
        """
        measure_beats = self.measures_and_beats()
        # Make a list of start times from the list of measure-beat times.
        tmp = [m.start_time for m in measure_beats]
        # Find the index of the desired time in the list.
        pos = bisect.bisect_right(tmp, time_in_ticks)
        # Return the corresponding measure/beat
        return measure_beats[pos - 1]

    def get_time_signature(self, time_in_ticks):
        """
        Get the active time signature at a given time (in ticks) during the song.
        :param time_in_ticks:  Time during the song, in MIDI ticks
        :return:               Active key signature at the time
        """
        itime = 0
        if len(self.time_signature_changes) == 0 or self.time_signature_changes[0].start_time != 0:
            raise ChiptuneSAKValueError("No starting time signature")
        n_time_signature_changes = len(self.time_signature_changes)
        while itime < n_time_signature_changes and self.time_signature_changes[itime].start_time < time_in_ticks:
            itime += 1
        return self.time_signature_changes[itime-1]

    def get_key_signature(self, time_in_ticks):
        """
        Get the active key signature at a given time (in ticks) during the song.
            :param time_in_ticks: Time during the song, in MIDI ticks
            :return:    Key signature active at the time
        """
        ikey = 0
        if len(self.key_signature_changes) == 0 or self.key_signature_changes[0].start_time != 0:
            raise ChiptuneSAKValueError("No starting time signature")
        n_key_signature_changes = len(self.key_signature_changes)
        while ikey < n_key_signature_changes and self.key_signature_changes[ikey].start_time < time_in_ticks:
            ikey += 1
        return self.key_signature_changes[ikey-1]
