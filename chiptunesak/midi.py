import sys
import mido
from chiptunesak.base import *
from chiptunesak.chirp import Note, ChirpTrack, ChirpSong


def sort_midi_events(msg):
    if msg.type == 'note_off':
        return (msg.time, 9)
    elif msg.type == 'note_on':
        return (msg.time, 10)
    elif msg.type == 'program_change':
        return (msg.time, 5)
    elif msg.type == 'track_name':
        return (msg.time, 0)
    else:
        return (msg.time, 7)


class MIDI(ChiptuneSAKIO):
    """
    Import/Export MIDI files to and from Chirp songs.

    The Chirp format is most closely tied to the MIDI standard.  As a result, conversion between MIDI
    files and ChirpSong objects is one of the most common ways to import and export music using the
    ChiptuneSAK framework.

    The MIDI class does not implement the standard to_bin() method because it uses the `mido`_ library to
    process low-level midi messages, and mido only deals with MIDI files.

    The Chirp framework can import both MIDI type 0 and type 1 files.  It will only write MIDI type 1 files.

    .. _mido: https://mido.readthedocs.io/en/latest/
    """
    @classmethod
    def cts_type(cls):
        return "MIDI"

    def __init__(self):
        ChiptuneSAKIO.__init__(self)
        self.midi_song = mido.MidiFile()

    def to_chirp(self, filename, **kwargs):
        """
        Import a midi file to Chirp format

        :param filename: filename to import
        :type filename: str
        :return: chirp song
        :rtype: ChirpSong
        :keyword options:
            * **keyswitch** (bool) Remove keyswitch notes with midi number <=8 (default True)
            * **polyphony** (bool) Allow polyphony (removal occurs after any quantization) (default True)
            * **quantize** (str)

                - 'auto': automatically determines required quantization
                - '8', '16', '32', etc. : quantize to the named duration
        """
        self.set_options(**kwargs)
        return self.import_midi_to_chirp(filename)

    def to_file(self, song, filename, **kwargs):
        """
        Exports a ChirpSong to a midi file.

        :param song: chirp song
        :type song: chirpSong
        :param filename: filename for export
        :type filename: str
        :return: True on success
        :rtype: bool
        """
        self.set_options(**kwargs)
        return self.export_chirp_to_midi(song, filename)

    def midi_track_to_chirp_track(self, chirp_song, midi_track):
        """
        Parse a MIDI track into notes, track name, and program changes.  This method uses the `mido`
        library for MIDI messges within the track.

        :param midi_track: midi track
        :type midi_track: MIDO midi track
        """
        chirp_track = ChirpTrack(chirp_song)
        # Find the first note_on event and use its channel to set the channel for this track.
        ch_msg = next((msg for msg in midi_track if msg.type == 'note_on'), None)
        if ch_msg:
            chirp_track.channel = ch_msg.channel
            chirp_track.name = 'Channel %d' % chirp_track.channel
        # Find the name meta message to get the track's name. Default is the channel.
        name_msg = next((msg for msg in midi_track if msg.type == 'track_name'), None)
        if name_msg:
            if len(name_msg.name.strip()) > 0:
                chirp_track.name = name_msg.name.strip()
        # Convert Midi events in the track into notes and durations
        current_time = 0
        current_notes_on = {}
        chirp_track.notes = []  # list of notes
        chirp_track.other = []  # list of other things int the track, such as patch changes or pitchwheel
        channels = set()
        for msg in midi_track:
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
                        chirp_track.notes.append(current_note)
                    elif delta < 0:
                        raise ChiptuneSAKValueError("Error in MIDI import: Illegal note length %d" % delta)
                    # Remove the note from the dictionary of notes that are on.
                    del current_notes_on[msg.note]
            elif msg.type == 'note_on':
                # Keep a dictionary of all notes that are currently on
                if msg.note not in current_notes_on:
                    current_notes_on[msg.note] = Note(current_time, msg.note, 0, msg.velocity)
            # Program changes get their own list
            elif msg.type == 'program_change':
                chirp_track.program_changes.append(ProgramEvent(current_time, int(msg.program)))
            elif msg.is_meta and msg.type == 'track_name':
                chirp_track.name = msg.name.strip()
            # Other messages of interest in the track are stored in a separate list as native MIDI messages
            elif msg.is_meta or (msg.type in ChirpTrack.other_message_types):
                chirp_track.other.append(OtherMidiEvent(current_time, msg))
        #  Turn off any notes left on
        for n in current_notes_on:
            start = current_notes_on[n].start_time
            delta = current_time - start
            if delta > 0:
                current_notes_on[n].duration = delta
                chirp_track.notes.append(current_notes_on[n])

        # Check that there was only one channel used in the track
        if len(channels) > 1:
            raise ChiptuneSAKException('Non-unique channel for track: %d channels in track %s'
                                       % (len(channels), chirp_track.name))

        # Now sort the notes by the time they turn on. They were inserted into the list in
        # the order they were turned off.  To do the sort, take advatage of automatic sorting of tuples.
        chirp_track.notes.sort(key=lambda n: (n.start_time, -n.note_num))
        chirp_track.program_changes.sort(key=lambda n: n.start_time)
        return chirp_track

    def import_midi_to_chirp(self, input_filename):
        """
        Open and import a MIDI file into the ChirpSong representation. THis method can handle MIDI type 0 and 1 files.

            :param input_filename: MIDI filename.
        """
        chirp_song = ChirpSong()
        # Clear everything
        chirp_song.reset_all()

        # Open the midi file using the Python mido library
        in_midi = mido.MidiFile(input_filename)
        chirp_song.metadata.ppq = in_midi.ticks_per_beat  # Pulses Per Quarter Note (usually 480, but Sibelius uses 960)
        # If MIDI file is not a Type 0 or 1 file, barf
        if int(in_midi.type) > 1:
            print("Error: Midi type %d detected. Only midi type 0 and 1 files supported." % (in_midi.type),
                  file=sys.stderr)
            sys.exit(1)

        # Parse and process the MIDI file into tracks
        # if this is a MIDI type 0 file, then there will only be one track with all the data in it.
        if in_midi.type == 0:
            # Splits into tracks: track 0 (metadata), and tracks 1-16 are note data.
            in_midi = self.split_midi_zero_into_tracks(in_midi)

        # Process meta commands in ALL tracks
        chirp_song.time_signature_changes = []
        chirp_song.key_signature_changes = []
        midi_meta_tracks = []
        for i, track in enumerate(in_midi.tracks):
            if i == 0:
                midi_meta_tracks.append(track)
                chirp_song = self.get_meta(chirp_song, track, True if i == 0 else False, True)
            else:
                chirp_song = self.get_meta(chirp_song, track, False, False)

        # Sort all time changes from meta tracks into a single time signature change list
        chirp_song.time_signature_changes = sorted(chirp_song.time_signature_changes)
        chirp_song.key_signature_changes = sorted(chirp_song.key_signature_changes)
        chirp_song.tempo_changes = sorted(chirp_song.tempo_changes)

        # Find all tracks that contain notes
        midi_note_tracks = [t for t in in_midi.tracks if sum(1 for m in t if m.type == 'note_on') > 0]

        # Now generate the note tracks
        for track in midi_note_tracks:
            chirp_track = self.midi_track_to_chirp_track(chirp_song, track)
            chirp_song.tracks.append(chirp_track)

        if self.get_option('keyswitch', True):
            chirp_song.remove_keyswitches(ks_max=8)
        q_type = self.get_option('quantization', None)
        if q_type is not None:
            if q_type == 'auto':
                chirp_song.quantize(*chirp_song.estimate_quantization())
            elif isinstance(q_type, int) or all(c.isdigit() for c in q_type):
                chirp_song.quantize_from_note_name(str(q_type))
        if not self.get_option('polyphony', 'True'):
            chirp_song.remove_polyphony()

        return chirp_song

    def get_meta(self, chirp_song, meta_track, is_zerotrack=False, is_metatrack=False):
        """
        Process MIDI meta messages in a track.

            :param chirp_song:
            :param meta_track:
            :param is_zerotrack:
            :param is_metatrack:
        """
        is_composer_set = False
        is_name_set = False
        current_time = 0
        for msg in meta_track:
            current_time += msg.time
            if msg.type == 'time_signature':
                chirp_song.time_signature_changes.append(
                    TimeSignatureEvent(current_time, msg.numerator, msg.denominator))
            elif msg.type == 'set_tempo':
                chirp_song.tempo_changes.append(TempoEvent(current_time, int(round(mido.tempo2bpm(msg.tempo)))))
            elif msg.type == 'key_signature':
                chirp_song.key_signature_changes.append(KeySignatureEvent(current_time, key.ChirpKey(msg.key)))
            elif msg.type == 'track_name' and is_zerotrack and not is_name_set:
                chirp_song.metadata.name = msg.name.strip()
                is_name_set = True
            # Composer seems to be the first text message in track zero.  Not required but maybe a semi-standard
            elif msg.type == 'text' and is_zerotrack and not is_composer_set:
                chirp_song.metadata.composer = msg.text.strip()
                is_composer_set = True
            elif msg.type == 'copyright' and is_zerotrack:
                chirp_song.metadata.copyright = msg.text.strip()
            # Keep meta events from tracks without notes
            # Note that these events are stored as midi messages with the global time attached.
            elif msg.is_meta and is_metatrack:
                chirp_song.other.append(OtherMidiEvent(current_time, msg))

        # Require initial time signature, key signature, and tempo values.
        if len(chirp_song.key_signature_changes) == 0 or chirp_song.key_signature_changes[0].start_time != 0:
            chirp_song.key_signature_changes.insert(0, KeySignatureEvent(0, key.ChirpKey("C")))  # Default top key of C
        chirp_song.metadata.key_signature = chirp_song.key_signature_changes[0]
        if len(chirp_song.time_signature_changes) == 0 or chirp_song.time_signature_changes[0].start_time != 0:
            chirp_song.time_signature_changes.insert(0, TimeSignatureEvent(0, 4, 4))  # Default to 4/4
        chirp_song.metadata.time_signature = chirp_song.time_signature_changes[0]
        if len(chirp_song.tempo_changes) == 0 or chirp_song.tempo_changes[0].start_time != 0:
            chirp_song.tempo_changes.insert(0, TempoEvent(0, int(mido.tempo2bpm(500000))))
        chirp_song.metadata.qpm = chirp_song.tempo_changes[0].qpm
        chirp_song.set_metadata()
        return chirp_song

    def split_midi_zero_into_tracks(self, midi_song):
        """
        For MIDI Type 0 files, split the notes into tracks.  To accomplish this, we
        move the metadata into Track 0 and then assign tracks 1-16 to the note data.
        """
        last_times = [0 for i in range(17)]
        tracks = [mido.MidiTrack() for i in range(17)]
        current_time = 0
        for msg in midi_song.tracks[0]:
            current_time += msg.time
            # Move all the meta messages into a single track.  Midi type 0 files should not
            # contain any track-specific meta-messages, so this is safe.
            if msg.is_meta:
                msg.time = current_time - last_times[0]
                last_times[0] = current_time
                tracks[0].append(msg)
            # All other messages get assigned to tracks based on their channel.
            elif msg.type != 'sysex':
                ch = msg.channel + 1
                msg.time = current_time - last_times[ch]
                last_times[ch] = current_time
                tracks[ch].append(msg)
        midi_song.type = 1  # Change the midi type for the mido object to Type 1
        # Eliminate tracks that have no events in them.
        midi_song.tracks = [t for t in tracks if len(t) > 0]

        return midi_song

    def chirp_track_to_midi_track(self, chirp_track):
        """
        Convert  ChirpTrack to a midi track.
        """
        midiTrack = mido.MidiTrack()
        events = [mido.MetaMessage('track_name', name=chirp_track.name, time=0)]
        for n in chirp_track.notes:
            # For the sake of sorting, create the midi event with the absolute time (which will be
            # changed to a delta time before returning).
            if n.note_num < 0 or n.note_num > 127:
                print(n.note_num)
            events.append(mido.Message('note_on',
                                       note=n.note_num, channel=chirp_track.channel,
                                       velocity=n.velocity, time=n.start_time))
            events.append(mido.Message('note_off',
                                       note=n.note_num, channel=chirp_track.channel,
                                       velocity=0, time=n.start_time + n.duration))
        for t, program in chirp_track.program_changes:
            events.append(mido.Message('program_change',
                                       channel=chirp_track.channel, program=program, time=t))
        for t, msg in chirp_track.other:
            msg.time = t
            events.append(msg)
        # Because 'note_off' comes before 'note_on' this sort will keep note_off events before
        # note_on events.
        events.sort(key=sort_midi_events)
        last_time = 0
        # Turn the absolute times into delta times.
        for msg in events:
            current_time = msg.time
            msg.time -= last_time
            midiTrack.append(msg)
            last_time = current_time
        return midiTrack

    def meta_to_midi_track(self, chirp_song):
        """
        Exports metadata to a MIDI track.
        """
        midi_track = mido.MidiTrack()
        events = [mido.MetaMessage('track_name', name=chirp_song.metadata.name, time=0)]
        if len(chirp_song.metadata.composer) > 0:
            events.append(mido.MetaMessage('text', text=chirp_song.metadata.composer, time=0))
        if len(chirp_song.metadata.copyright) > 0:
            events.append(mido.MetaMessage('copyright', text=chirp_song.metadata.copyright, time=0))
        #  Put all the time signature changes into the track.
        for t, key in chirp_song.key_signature_changes:
            events.append(mido.MetaMessage('key_signature', key=key.key_name, time=t))
        #  Put all the time signature changes into the track.
        for t, numerator, denominator in chirp_song.time_signature_changes:
            events.append(mido.MetaMessage('time_signature', numerator=numerator, denominator=denominator, time=t))
        #  Put the tempo changes into the track.
        for t, tempo in chirp_song.tempo_changes:
            events.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(tempo), time=t))
        # Put any other meta-messages that were assign to the song as a whole into the track.
        for t, msg in chirp_song.other:
            msg.time = t
            events.append(msg)
        # Sort the track by time so it's ready for the MIDI delta-time format.
        events.sort(key=sort_midi_events)

        # Generate the midi from the events.
        last_time = 0
        for msg in events:
            tmp_time = msg.time
            msg.time -= last_time
            midi_track.append(msg)
            last_time = tmp_time

        return midi_track

    def export_chirp_to_midi(self, chirp_song, output_filename):
        """
        Exports the song to a MIDI Type 1 file.  Exporting to the midi format is privileged because this class
        is tied to many midi concepts and uses midid messages explicitly for some content.
        """
        if chirp_song.cts_type() != 'Chirp':
            raise ChiptuneSAKNotImplemented("Only ChirpSong objects can be exported to midi")
        out_midi_file = mido.MidiFile(ticks_per_beat=chirp_song.metadata.ppq)
        out_midi_file.tracks.append(self.meta_to_midi_track(chirp_song))
        for t in chirp_song.tracks:
            out_midi_file.tracks.append(self.chirp_track_to_midi_track(t))
        out_midi_file.save(output_filename)
        return True
