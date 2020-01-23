TOOLVERSION = "0.1"

# Midi Simple Processing Library
#
# 2019, David Knapp / David Youd
#
# Recommended Python version installed >= 3.7.4
# Must first install midi: https://github.com/olemb/mido/blob/master/docs/installing.rst
#    pip install mido
#

import sys
import bisect
import collections
import mido
import more_itertools as moreit
from fractions import Fraction
from ctsErrors import *
import ctsConstants

# Named tuple types for several lists throughout
TimeSignature = collections.namedtuple('TimeSignature', ['start_time', 'num', 'denom'])
KeySignature = collections.namedtuple('KeySignature', ['start_time', 'key'])
Tempo = collections.namedtuple('Tempo', ['start_time', 'bpm'])
OtherMidi = collections.namedtuple('OtherMidi', ['start_time', 'msg'])
Beat = collections.namedtuple('Beat', ['start_time', 'measure', 'beat'])


class Note:
    """
    This class represents a note in human-friendly form:  as a note with a start time, a duration, and
    a velocity. 
    """

    def __init__(self, note, start, duration, velocity=100, rest=False):
        self.note_num = note  # MIDI note number
        self.start_time = start  # In ticks since tick 0
        self.duration = duration  # In ticks
        self.velocity = velocity  # MIDI velocity 0-127
        self.is_rest = rest

    def is_rest(self):
        return self.rest

    def is_note(self):
        return not self.rest

    def __eq__(self, other):
        """ Two notes are equal when their note numbers and durations are the same """
        return (self.note_num == other.note_num) and (self.duration == other.duration)

    def __str__(self):
        return "p=%3d  s=%4d  d=%4d  v=%4d" % (self.note_num, self.start_time, self.duration, self.velocity)


class SongTrack:
    """
    This class represents a track (or a voice) from a song.  It is basically a list of Notes with some
    other context information.

    ASSUMPTION: The track contains notes for only ONE instrument (midi channel).  Tracks with notes
    from more than one instrument will produce undefined results.
    """

    # Define the message types to preserve as a static variable
    other_messages = ['program_change', 'pitchwheel', 'control_change']

    def __init__(self, song, track=None):
        self.song = song  # Parent song
        self.name = 'none'  # Track name
        self.channel = 0  # This track's midi channel.  Each track should have notes from only one channel.
        self.notes = []  # The notes in the track
        self.other = []  # Other events in the track (includes voice changes and pitchwheel)
        self.qticks_notes = song.qticks_notes  # Inherit quantization from song
        self.qticks_durations = song.qticks_durations  # inherit quantization from song
        # If a track is given to the constructor, it must be a midi track from mido.
        if track is not None:
            self.import_midi_track(track)

    def import_midi_track(self, track):
        """
        Parse a MIDI track into notes.  This process loses any meta messages in the track
        except the track name message, which is uses to name itself.
        """

        # Find the first note_on event and use its channel to set the channel for this track.
        ch_msg = next((msg for msg in track if msg.type == 'note_on'), None)
        if ch_msg:
            self.channel = ch_msg.channel
            self.name = 'Channel %d' % self.channel
        # Find the name meta message to get the track's name. Default is the channel.
        name_msg = next((msg for msg in track if msg.type == 'track_name'), None)
        if name_msg:
            self.name = name_msg.name.strip()
        # Convert Midi events in the track into notes and durations
        current_time = 0
        current_notes_on = {}
        self.notes = []  # list of notes
        self.other = []  # list of other things int the track, such as patch changes or pitchwheel
        channels = set()
        for msg in track:
            current_time += msg.time
            if not msg.is_meta:
                # Keep track of unique channels for non-meta messages
                channels.add(msg.channel)
            # Some MIDI devices use a note_on with velocity of 0 to turn notes off.
            if msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                # If this note is not in our dictionary of notes that are on, ignore the note_off
                if msg.note in current_notes_on:
                    current_note = current_notes_on[msg.note]
                    start = current_note.start_time
                    delta = current_time - start
                    if delta > 0:
                        current_note.duration = delta
                        self.notes.append(current_note)
                    elif delta < 0:
                        raise ChiptuneSAKValueError("Error in MIDI import: Illegal note length %d" % delta)
                    # Remove the note from the dictionary of notes that are on.
                    del current_notes_on[msg.note]
            elif msg.type == 'note_on':
                # Keep a dictionary of all notes that are currently on
                if msg.note not in current_notes_on:
                    current_notes_on[msg.note] = Note(msg.note, current_time, 0, msg.velocity)
            # Other messages of interest in the track are stored in a separate list as native MIDI messages        
            elif msg.is_meta or (msg.type in SongTrack.other_messages):
                self.other.append(OtherMidi(current_time, msg))
        #  Turn off any notes left on
        for n in current_notes_on:
            start = current_notes_on[n].start_time
            delta = current_time - start
            if delta > 0:
                current_notes_on[n].duration = delta
                self.notes.append(current_notes_on[n])

        # Check that there was only one channel used in the track
        if len(channels) > 1:
            raise ChiptuneSAKException('Non-unique channel for track: %d channels in track %s'
                                       % (len(channels), self.name))

        # Now sort the notes by the time they turn on. They were inserted into the list in
        # the order they were turned off.  To do the sort, take advatage of automatic sorting of tuples.
        self.notes.sort(key=lambda n: (n.start_time, -n.note_num))

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
        self.qticks_notes = find_quantization(self.song.ppq, tmpNotes)
        tmpNotes = [n.duration for n in self.notes]
        self.qticks_durations = find_quantization(self.song.ppq, tmpNotes)
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
            if abs(n.duration - duration_before) > 100:
                print(self.name, n)

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
            ret_notes.append(last)
            last = n
        ret_notes.append(last)
        self.notes = ret_notes
        self.notes.sort(key=lambda n: (n.start_time, -n.note_num))
        return (deleted, truncated)

    def is_polyphonic(self):
        return any(b.start_time - a.start_time < a.duration for a, b in moreit.pairwise(self.notes))

    def is_quantized(self):
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

    def to_midi(self):
        """
        Convert the SongTrack to a midi track.
        """
        midiTrack = mido.MidiTrack()
        events = []
        for n in self.notes:
            # For the sake of sorting, create the midi event with the absolute time (which will be
            # changed to a delta time before returning).
            events.append(mido.Message('note_on',
                                       note=n.note_num, channel=self.channel,
                                       velocity=n.velocity, time=n.start_time))
            events.append(mido.Message('note_off',
                                       note=n.note_num, channel=self.channel,
                                       velocity=0, time=n.start_time + n.duration))
        for t, msg in self.other:
            msg.time = t
            events.append(msg)
        # Because 'note_off' comes before 'note_on' this sort will keep note_off events before
        # note_on events.
        events.sort(key=lambda m: (m.time, m.type))
        last_time = 0
        # Turn the absolute times into delta times.
        for msg in events:
            current_time = msg.time
            msg.time -= last_time
            midiTrack.append(msg)
            last_time = current_time
        return midiTrack

    def __str__(self):
        ret_val = "Track: %s (channel %d)\n" % (self.name, self.channel)
        return ret_val + '\n'.join(str(n) for n in self.notes)


class Song:
    """
    This class represents a song. It stores notes in an intermediate representation that
    approximates traditional music notationh (as pitch-duration).  It also stores other 
    information, such as time signatures and tempi, in a similar way.
    """

    def __init__(self, filename=None):
        self.reset_all()
        if filename:
            self.import_midi(filename)

    def reset_all(self):
        """ 
        Clear all tracks and reinitialize to default values
        """
        self.ppq = 480  # Pulses (ticks) per quarter note. Default is 480, which is commonly used.
        self.qticks_notes = self.ppq  # Quantization for note starts, in ticks
        self.qticks_durations = self.ppq  # Quantization for note durations, in ticks
        self.bpm = mido.tempo2bpm(500000)  # Default tempo (it's the midi default)
        self.tracks = []  # List of Songtrack tracks
        self.name = ''
        self.meta_track = []  # List of all meta events that apply to the song as a whole
        self.midi_meta_tracks = []  # list of all the midi tracks that only contain metadata
        self.midi_note_tracks = []  # list of all the tracks that contain notes
        self.time_signature_changes = []  # List of time signature changes
        self.key_signature_changes = []  # List of key signature changes
        self.tempo_changes = []  # List of tempo changes
        self.end_time = 0  # last MIDI event in the entire song
        self.stats = {}  # Statistics about the song

    def import_midi(self, filename):
        """ 
        Open and initialize from a MIDI Type 0 or 1 file.
        """
        # Clear everything
        self.reset_all()

        # Open the midi file using the Python mido library
        self.in_midi = mido.MidiFile(filename)
        self.ppq = self.in_midi.ticks_per_beat  # Pulses Per Quarter Note (usually 480, but Sibelius uses 960)
        # If MIDI file is not a Type 0 or 1 file, barf
        if self.in_midi.type > 1:
            print("Error: Midi type %d detected. Only midi type 0 and 1 files supported." % (self.in_midi.type),
                  file=sys.stderr)
            sys.exit(1)

        # Parse and process the MIDI file into tracks 
        # if this is a MIDI type 0 file, then there will only be one track with all the data in it.
        if self.in_midi.type == 0:
            self.split_midi_zero_into_tracks()  # Splits into tracks: track 0 (metadata), and tracks 1-16 are note data.

        # Process meta commands in ALL tracks
        self.time_signature_changes = []
        self.key_signature_changes = []
        for i, track in enumerate(self.in_midi.tracks):
            n_notes = sum(1 for m in track if m.type == 'note_on')
            if n_notes == 0:
                self.midi_meta_tracks.append(track)
                self.get_meta(track, True if i == 0 else False, True)
            else:
                self.get_meta(track, False, False)



        # Sort all time changes from meta tracks into a single time signature change list
        self.time_signature_changes = sorted(self.time_signature_changes)
        self.stats['Time Signature Changes'] = len(self.time_signature_changes)
        self.tempo_changes = sorted(self.tempo_changes)
        self.stats['Tempo Changes'] = len(self.tempo_changes)

        # Set the tempo to that specified by the first tempo event
        if len(self.tempo_changes) > 0:
            self.bpm = self.tempo_changes[0].bpm

        # Find all tracks that contain notes
        self.midi_note_tracks = [t for t in self.in_midi.tracks if sum(1 for m in t if m.type == 'note_on') > 0]

        self.stats["MIDI notes"] = sum(1 for t in self.midi_note_tracks
                                       for m in t if m.type == 'note_on' and m.velocity != 0)

        # Now generate the note tracks
        for track in self.midi_note_tracks:
            self.tracks.append(SongTrack(self, track))

        self.stats["Notes"] = sum(len(t.notes) for t in self.tracks)
        self.stats["Track names"] = [t.name for t in self.tracks]

        # Finally, generate measures and beats
        self.end_time = max(n.start_time + n.duration for t in self.tracks for n in t.notes)
        self.measure_beats = make_measures(self.ppq, self.time_signature_changes, self.end_time)
        self.stats['Measures'] = max(m.measure for m in self.measure_beats)


    def get_meta(self, track, is_zerotrack=False, is_metatrack=False):
        """ 
        Process meta messages in track.
        """
        current_time = 0
        for msg in track:
            current_time += msg.time
            if msg.type == 'time_signature':
                self.time_signature_changes.append(TimeSignature(current_time, msg.numerator, msg.denominator))
            elif msg.type == 'set_tempo':
                self.tempo_changes.append(Tempo(current_time, int(mido.tempo2bpm(msg.tempo) + 0.5)))
            elif msg.type == 'key_signature':
                self.key_signature_changes.append(KeySignature(current_time, msg.key))
            elif msg.type == 'track_name' and is_zerotrack:
                self.name = msg.name.strip()
            # Keep meta events from tracks without notes
            # Note that these events are stored as midi messages with the global time attached.
            elif msg.is_meta and is_metatrack:
                self.meta_track.append(OtherMidi(current_time, msg))
            # Find the very last meta message (which should be an end_track) and use it as the end time.

    def estimate_quantization(self):
        """ 
        This method estimates the optimal quantization for note starts and durations from the note
        data itself. This version all note data in the tracks. Many pieces have no discernable 
        duration quantization, so in that case the default is half the note start quantization.  
        These values are easily overridden.
        """
        tmp_notes = [n.start_time for t in self.tracks for n in t.notes]
        self.qticks_notes = find_quantization(self.ppq, tmp_notes)
        tmp_durations = [n.duration for t in self.tracks for n in t.notes]
        self.qticks_durations = find_duration_quantization(self.ppq, tmp_durations, self.qticks_notes)
        if self.qticks_durations < self.qticks_notes:
            self.qticks_durations = self.qticks_notes // 2
        return (self.qticks_notes, self.qticks_durations)

    def quantize(self, qticks_notes=None, qticks_durations=None):
        """
        This method applies quantization to both note start times and note durations.  If you
        want either to remain unquantized, simply specify a qticks parameter to be 1 (quantization
        of 1 tick).
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
        for i, m in enumerate(self.meta_track):
            self.meta_track[i] = OtherMidi(quantize_fn(m.start_time, self.qticks_notes), m.msg)

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
        """
        return any(t.is_polyphonic() for t in self.tracks)

    def is_quantized(self):
        """
        Has the song been quantized?  This requires that all the tracks have been quantized with their
        current qticks_notes and qticks_durations values.
        """
        return all(t.is_quantized() for t in self.tracks)

    def remove_control_notes(self, control_max=8):
        """ 
        Some MIDI programs use extremely low notes as a signaling mechanism.
        This method removes notes with pitch <= control_max from all tracks.
        """
        for t in self.tracks:
            t.remove_control_notes(control_max)

    def modulate(self, num, denom):
        """
        This method performs metric modulation.  It does so by multiplying the length of all notes by num/denom,
        and also automatically adjusts the time signatures and tempos such that the resulting music will sound
        identical to the original.
        """
        # First adjust the time signatures
        for i, ts in enumerate(self.time_signature_changes):
            # The time signature always has to be whole numbers so if the new numerator is not an integer fix that
            #  by multiplying by 3/2
            t, n, d = ts
            self.time_signature_changes[i] = TimeSignature(t, n * num, d * denom)
        # Next the tempos
        for i, tm in enumerate(self.tempo_changes):
            t, bpm = tm
            self.tempo_changes[i] = Tempo((t * num) // denom, (bpm * num) // denom)
        # Now all the rest of the meta messages
        for i, ms in enumerate(self.meta_track):
            t, m = ms
            self.meta_track[i] = OtherMidi((t * num) // denom, m)
        # Finally, modulate each track
        for i, _ in enumerate(self.tracks):
            self.tracks[i].modulate(num, denom)
        # Now adjust the quantizations in case quantization has been applied to reflect the new lengths
        self.qticks_notes = (self.qticks_notes * n) // d
        self.qticks_durations = (self.qticks_durations * n) // d
        # Finally finally fix the last event time
        self.end_time = max(n.start_time + n.duration for t in self.tracks for n in t.notes)
        # Things have changed to re-do the measures calculation
        self.measure_beats = make_measures(self.ppq, self.time_signature_changes, self.end_time)

    def get_measure_beat(self, start_time):
        """
        This method returns a (measure, beat) tuple for a given time; the time is greater than or
        equal to the returned measure and beat but less than the next.  The result should be
        interpreted as the time being during the measure and beat returned.
        """
        # Make a list of start times from the list of measure-beat times.
        tmp = [m.start_time for m in self.measure_beats]
        # Find the index of the desired time in the list.
        pos = bisect.bisect_right(tmp, start_time)
        # Return the corresponding measure/beat
        return (self.measure_beats[pos - 1].measure, self.measure_beats[pos - 1].beat)

    def split_midi_zero_into_tracks(self):
        """
        For MIDI Type 0 files, split the notes into tracks.  To accomplish this, we
        move the metadata into Track 0 and then assign tracks 1-16 to the note data.
        """
        last_times = [0 for i in range(17)]
        tracks = [[] for i in range(17)]
        current_time = 0
        for msg in self.in_midi.tracks[0]:
            current_time += msg.time
            # Move all the meta messages into a single track.  Midi type 0 files should not
            # contain any track-specific meta-messages, so this is safe.
            if msg.is_meta:
                msg.time = current_time - last_times[0]
                last_times[0] = current_time
                tracks[0].append(msg)
            # All other messages get assigned to tracks based on their channel.
            else:
                ch = msg.channel + 1
                msg.time = current_time - last_times[ch]
                last_times[ch] = current_time
                tracks[ch].append(msg)
        self.in_midi.type = 1  # Change the midi type for the mido object to Type 1
        # Eliminate tracks that have no events in them.
        self.in_midi.tracks = [t for t in tracks if len(t) > 0]

    def meta_to_midi_track(self):
        """
        Exports metadata to a MIDI track.
        """
        midi_track = mido.MidiTrack()
        events = []
        #  Put all the time signature changes into the track.
        for t, numerator, denominator in self.time_signature_changes:
            events.append(mido.MetaMessage('time_signature', numerator=numerator, denominator=denominator, time=t))
        #  Put the tempo changes into the track.
        for t, tempo in self.tempo_changes:
            events.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(tempo), time=t))
        # Put any other meta-messages that were assign to the song as a whole into the track.
        for t, msg in self.meta_track:
            msg.time = t
            events.append(msg)
        # Sort the track by time so it's ready for the MIDI delta-time format.
        events.sort(key=lambda m: (m.time, m.type))

        # Generate the midi from the events.
        last_time = 0
        for msg in events:
            tmp_time = msg.time
            msg.time -= last_time
            midi_track.append(msg)
            last_time = tmp_time
        return midi_track

    def export_midi(self, midi_filename):
        """
        Exports the song to a MIDI Type 1 file.  Exporting to the midi format is privileged because this class
        is tied to many midi concepts and uses midid messages explicitly for some content.
        """
        out_midi_file = mido.MidiFile(ticks_per_beat=self.ppq)
        out_midi_file.tracks.append(self.meta_to_midi_track())
        for t in self.tracks:
            out_midi_file.tracks.append(t.to_midi())
        out_midi_file.save(midi_filename)


# --------------------------------------------------------------------------------------
#
#  Utility functions
#
# --------------------------------------------------------------------------------------

def quantization_error(t_ticks, q_ticks):
    """
    Calculated the error, in ticks, for the given time for a quantization of q ticks.
    """
    j = t_ticks // q_ticks
    return int(min(abs(t_ticks - q_ticks * j), abs(t_ticks - q_ticks * (j + 1))))


def objective_error(notes, test_quantization):
    """
    This is the objective function for getting the error for the entire set of notes for a
    given quantization in ticks.  The function used here could be a sum, RMS, or other
    statistic, but empirical tests indicate that the max used here works well and is robust.
    """
    return max(quantization_error(n, test_quantization) for n in notes)


def find_quantization(ppq, time_series):
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
    """
    last_err = len(time_series) * ppq
    n_notes = len(time_series)
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


def find_duration_quantization(ppq, durations, qticks_note):
    """
    The duration quantization is determined from the shortest note length.
    The algorithm starts from the estimated quantization for note starts.
    """
    min_length = min(durations)
    current_q = qticks_note
    ratio = min_length / current_q
    while ratio < 0.9:
        # Try a triplet
        tmp_q = current_q
        current_q = current_q * 3 // 2
        if ratio > 0.9:
            break
        current_q = tmp_q // 2
    return current_q


def quantize_fn(t, qticks):
    """ 
    This function quantizes a time to a certain number of ticks.
    """
    current = t // qticks
    next = current + 1
    current *= qticks
    next *= qticks
    if abs(t - current) <= abs(next - t):
        return current
    else:
        return next


def make_measures(ppq, time_signature_changes, max_time):
    """
    Given a list of times and time signatures (num / denom), generates alist of the positions of measures and
    beats within that measure.
    """
    measures = []
    time_signature_changes = sorted(time_signature_changes)
    if time_signature_changes[0].start_time == 0:
        last = time_signature_changes[0]
    else:
        last = TimeSignature(0, 4, 4)
    t, m, b = 0, 1, 1
    for s in time_signature_changes:
        while t < s.start_time:
            measures.append(Beat(t, m, b))
            t += (ppq * 4) // last.denom
            b += 1
            if b > last.num:
                m += 1
                b = 1
        last = s
    while t <= max_time:
        measures.append(Beat(t, m, b))
        t += (ppq * 4) // last.denom
        b += 1
        if b > last.num:
            m += 1
            b = 1
    while b <= last.num:
        measures.append(Beat(t, m, b))
        b += 1
    return measures


def duration_to_note_name(duration, ppq):
    """
    Given a ppq (pulses per quaver) convert a duration to a human readable note length, e.g., 'eighth'
    Works for notes, dotted notes, and triplets down to sixty-fourth notes.
    """
    f = Fraction(duration/ppq).limit_denominator(64)
    return ctsConstants.DURATIONS.get(f, '<unknown>')


def pitch_to_note_name(note_num, octave_offset=0):
    """
    Gets note name for a given MIDI pitch
    """
    if not 0 <= note_num <= 127:
        raise ChiptuneSAKValueError("Illegal note number %d" % note_num)
    octave = (note_num // 12) + octave_offset
    pitch = note_num % 12
    return "%s%d" % (ctsConstants.PITCHES[pitch], octave)
