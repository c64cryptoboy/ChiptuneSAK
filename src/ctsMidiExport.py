import sys
import mido
from ctsErrors import *
from ctsConstants import *
from ctsBase import *
from ctsChirp import Note, ChirpTrack, ChirpSong

def chirp_track_to_midi_track(chirp_track):
    """
    Convert  ChirpTrack to a midi track.
    """
    midiTrack = mido.MidiTrack()
    events = [mido.MetaMessage('track_name', name=chirp_track.name)]
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
    for t, msg in chirp_track.other:
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


def meta_to_midi_track(chirp_song):
    """
    Exports metadata to a MIDI track.
    """
    midi_track = mido.MidiTrack()
    events = []
    #  Put all the time signature changes into the track.
    for t, key in chirp_song.key_signature_changes:
        events.append(mido.MetaMessage('key_signature', key=key, time=t))
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
    events.sort(key=lambda m: (m.time, m.type))

    # Generate the midi from the events.
    last_time = 0
    for msg in events:
        tmp_time = msg.time
        msg.time -= last_time
        midi_track.append(msg)
        last_time = tmp_time

    return midi_track

def chirp_to_midi(chirp_song, outfile):
    """
    Exports the song to a MIDI Type 1 file.  Exporting to the midi format is privileged because this class
    is tied to many midi concepts and uses midid messages explicitly for some content.
    """
    out_midi_file = mido.MidiFile(ticks_per_beat=chirp_song.metadata.ppq)
    out_midi_file.tracks.append(meta_to_midi_track(chirp_song))
    for t in chirp_song.tracks:
        out_midi_file.tracks.append(chirp_track_to_midi_track(t))
    out_midi_file.save(outfile)
