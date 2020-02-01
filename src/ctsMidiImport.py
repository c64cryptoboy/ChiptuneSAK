import sys
import mido
import more_itertools as moreit
from fractions import Fraction
from ctsErrors import *
from ctsConstants import *
from ctsBase import *
from ctsChirp import Note, ChirpTrack, ChirpSong


def midi_track_to_chirp_track(chirp_song, midi_track):
    """
    Parse a MIDI track into notes.

        :param track:
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
        # Other messages of interest in the track are stored in a separate list as native MIDI messages
        elif msg.is_meta or (msg.type in ChirpTrack.other_message_types):
            chirp_track.other.append(OtherMidi(current_time, msg))
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
    return chirp_track


def midi_to_chirp(filename):
    """
    Open and import a MIDI file into the ChirpSong representation. THis method can handle MIDI type 0 and 1 files.

        :param filename: MIDI filename.
    """
    chirp_song = ChirpSong()
    # Clear everything
    chirp_song.reset_all()

    # Open the midi file using the Python mido library
    in_midi = mido.MidiFile(filename)
    chirp_song.metadata.ppq = in_midi.ticks_per_beat  # Pulses Per Quarter Note (usually 480, but Sibelius uses 960)
    # If MIDI file is not a Type 0 or 1 file, barf
    if in_midi.type > 1:
        print("Error: Midi type %d detected. Only midi type 0 and 1 files supported." % (self.in_midi.type),
              file=sys.stderr)
        sys.exit(1)

    # Parse and process the MIDI file into tracks
    # if this is a MIDI type 0 file, then there will only be one track with all the data in it.
    if in_midi.type == 0:
        in_midi = split_midi_zero_into_tracks(in_midi)  # Splits into tracks: track 0 (metadata), and tracks 1-16 are note data.

    # Process meta commands in ALL tracks
    chirp_song.time_signature_changes = []
    chirp_song.key_signature_changes = []
    midi_meta_tracks = []
    for i, track in enumerate(in_midi.tracks):
        n_notes = sum(1 for m in track if m.type == 'note_on')
        if n_notes == 0:
            midi_meta_tracks.append(track)
            chirp_song = get_meta(chirp_song, track, True if i == 0 else False, True)
        else:
            chirp_song = get_meta(chirp_song, track, False, False)

    # Sort all time changes from meta tracks into a single time signature change list
    chirp_song.time_signature_changes = sorted(chirp_song.time_signature_changes)
    chirp_song.stats['Time Signature Changes'] = len(chirp_song.time_signature_changes)
    chirp_song.key_signature_changes = sorted(chirp_song.key_signature_changes)
    chirp_song.stats['Key Signature Changes'] = len(chirp_song.key_signature_changes)
    chirp_song.tempo_changes = sorted(chirp_song.tempo_changes)
    chirp_song.stats['Tempo Changes'] = len(chirp_song.tempo_changes)

    # Find all tracks that contain notes
    midi_note_tracks = [t for t in in_midi.tracks if sum(1 for m in t if m.type == 'note_on') > 0]

    chirp_song.stats["MIDI notes"] = sum(1 for t in midi_note_tracks
                                   for m in t if m.type == 'note_on' and m.velocity != 0)

    # Now generate the note tracks
    for track in midi_note_tracks:
        chirp_track = midi_track_to_chirp_track(chirp_song, track)
        chirp_song.tracks.append(chirp_track)

    chirp_song.stats["Notes"] = sum(len(t.notes) for t in chirp_song.tracks)
    chirp_song.stats["Track names"] = [t.name for t in chirp_song.tracks]

    return chirp_song

def get_meta(chirp_song, meta_track, is_zerotrack=False, is_metatrack=False):
    """
    Process MIDI meta messages in a track.

        :param chirp_song:
        :param meta_track:
        :param is_zerotrack:
        :param is_metatrack:
    """
    current_time = 0
    for msg in meta_track:
        current_time += msg.time
        if msg.type == 'time_signature':
            chirp_song.time_signature_changes.append(TimeSignature(current_time, msg.numerator, msg.denominator))
        elif msg.type == 'set_tempo':
            chirp_song.tempo_changes.append(Tempo(current_time, int(mido.tempo2bpm(msg.tempo) + 0.5)))
        elif msg.type == 'key_signature':
            chirp_song.key_signature_changes.append(KeySignature(current_time, msg.key))
        elif msg.type == 'track_name' and is_zerotrack:
            chirp_song.metadata.name = msg.name.strip()
        # Keep meta events from tracks without notes
        # Note that these events are stored as midi messages with the global time attached.
        elif msg.is_meta and is_metatrack:
            chirp_song.other.append(OtherMidi(current_time, msg))

    # Require initial time signature, key signature, and tempo values.
    if len(chirp_song.key_signature_changes) == 0 or chirp_song.key_signature_changes[0].start_time != 0:
        chirp_song.key_signature_changes.insert(0, KeySignature(0, "C"))  # Default top key of C
    chirp_song.metadata.key_signature = chirp_song.key_signature_changes[0]
    if len(chirp_song.time_signature_changes) == 0 or chirp_song.time_signature_changes[0].start_time != 0:
        chirp_song.time_signature_changes.insert(0, TimeSignature(0, 4, 4))  # Default to 4/4
    chirp_song.metadata.time_signature= chirp_song.time_signature_changes[0]
    if len(chirp_song.tempo_changes) == 0 or chirp_song.tempo_changes[0].start_time != 0:
        chirp_song.tempo_changes.insert(0, Tempo(0, int(mido.tempo2bpm(500000))))
    chirp_song.metadata.bpm = chirp_song.tempo_changes[0].bpm

    return chirp_song


def split_midi_zero_into_tracks(midi_song):
    """
    For MIDI Type 0 files, split the notes into tracks.  To accomplish this, we
    move the metadata into Track 0 and then assign tracks 1-16 to the note data.
    """
    last_times = [0 for i in range(17)]
    tracks = [mido.MidiTrack() for i in range(17)]
    current_time = 0
    for msg in midi.tracks[0]:
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
    midi_song.type = 1  # Change the midi type for the mido object to Type 1
    # Eliminate tracks that have no events in them.
    midi_song.tracks = [t for t in tracks if len(t) > 0]

    return midi_song


