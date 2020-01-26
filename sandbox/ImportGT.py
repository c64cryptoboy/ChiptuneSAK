import sandboxPath
import ctsSong
import parseGT


def tick_to_miditick(t):
    return t * 48  # Scale so that midi will pay back at the same speed as the tracker would play.


def import_goattracker(in_filename):
    data = parseGT.import_sng(in_filename)
    channels_time_events = parseGT.convert_to_note_events(data, 0)
    song = ctsSong.Song()
    song.ppq = 960
    song.name = in_filename
    song.bpm = 120

    for it, channel_data in enumerate(channels_time_events):
        track = ctsSong.SongTrack(song)
        track.name = 'Track %d' % (it + 1)
        track.channel = it
        current_note = None
        for tick, event in channel_data.items():
            midi_tick = tick_to_miditick(tick)
            if event.note_on:
                if current_note:
                    new_note = ctsSong.Note(
                        current_note.note_num, current_note.start_time, midi_tick - current_note.start_time
                    )
                    if new_note.duration > 0:
                        track.notes.append(new_note)
                current_note = ctsSong.Note(event.note, midi_tick, 0)
            elif event.note_on is False:
                if event.note_on:
                    if current_note:
                        new_note = ctsSong.Note(
                            current_note.start_time, current_note.note_num, midi_tick - current_note.start_time
                        )
                        if new_note.duration > 0:
                            track.notes.append(new_note)
                current_note = None
        if current_note:
            new_note = ctsSong.Note(
                current_note.note_num, current_note.start_time, midi_tick - current_note.start_time
            )
            if new_note.duration > 0:
                track.notes.append(new_note)
        song.tracks.append(track)

    return song


if __name__ == '__main__':
    song = import_goattracker('consultant.sng')
    print(song.estimate_quantization())
    song.quantize()
    song.export_midi('consultant.mid')
