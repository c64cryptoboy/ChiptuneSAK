import os
import csv
from chiptunesak import constants
from chiptunesak.base import *
from chiptunesak.chirp import ChirpSong, ChirpTrack, Note
from chiptunesak.midi import MIDI
from chiptunesak.byte_util import little_endian_int


class Ultima4Song:
    """
    This class represents an Ultima 4 song.
    Ultima note values range from 0x00-0x7f.
    0x00 represents an 'A0', the lowest key on a piano (MIDI: 21)
    Ultima: middle C is 39, concert pitch A (A4) is 48
    MIDI: middle C (C4) is 60, concert pitch A (A4) is 69
    MIDI pitch = Ultima pitch + 21

    """

    MIDI_NOTE_OFFSET = 21
    TICKS_PER_QUARTER = 24

    def __init__(self, song_no, u4music):
        self.sequences = []     # Sequence offsets within music data
        self.voices = []        # This song's voices
        self.tempo = 0x429a     # Current tempo
        self.chirp_song = ChirpSong()   # Chirp song associated with this song
        # TODO: check for valid song number
        self.u4music = u4music
        self.song_no = song_no
        self.music_data = u4music.music_data
        music_data = self.music_data

        self.chirp_song.reset_all()
        self.chirp_song.metadata.ppq = self.TICKS_PER_QUARTER
        self.chirp_song.qticks_notes = self.TICKS_PER_QUARTER
        self.chirp_song.qticks_durations = self.TICKS_PER_QUARTER

        idx = song_no * 2 + 1
        self.song_offset = little_endian_int(music_data[idx:idx + 2])
        print("song_offset: ", self.song_offset)

        idx = self.song_offset
        self.num_voices = music_data[idx]
        print("number of voices: ", self.num_voices)

        idx += 1
        for v in range(self.num_voices):
            # create voices
            start_position = little_endian_int(music_data[idx:idx + 2]) + self.song_offset
            print("voice offset: ", start_position)
            voice = Ultima4Voice(self, start_position)
            self.voices.append(voice)
            self.chirp_song.tracks.append(voice.chirp_track)
            idx += 2

        # idx += 2 * self.num_voices
        print("offset i: ", idx)
        num_sequences = music_data[idx]
        print("number of sequences: ", num_sequences)

        idx += 1
        for seq in range(num_sequences):
            start_pos = little_endian_int(music_data[idx:idx + 2]) + self.song_offset
            self.sequences.append(start_pos)
            idx += 2
        print(self.sequences)

        # init voices
        for v in self.voices:
            v.initialize()

        # extraction loop
        any_voice_played = True
        while any_voice_played:
            any_voice_played = False
            for index, voice in enumerate(self.voices):
                # print("voice", index, " offset: ", voice.song_pos)
                if voice.playback():
                    any_voice_played = True

    def set_tempo(self, ticks, tempo):
        """
        Set a new tempo.

        :param int tempo: New tempo
        """
        self.tempo = tempo
        # calculate qpm (quarter notes per minute)
        qpm = int(60 * 1023000 / (tempo * self.TICKS_PER_QUARTER) + 0.5)
        print("tempo event:", 60 * 1023000 / (tempo * self.TICKS_PER_QUARTER))
        tempo_event = TempoEvent(ticks, qpm)
        self.chirp_song.tempo_changes.append(tempo_event)


class Ultima4Voice:
    """
    This class represents a voice in an Ultima IV song.
    The typical use case is to first construct the voice.
    Next, the initialize function should be called with the
    song's sequences as a parameter. Now, playback()
    can be called repeatedly until the function returns False.
    """

    def __init__(self, song, start_position):
        self.voice_on = True    # Voice is still playing back: True
        self.start_position = start_position  # Voice start position in music data
        self.transpose = 0      # Transpose voice, range -128 - +127
        self.freq_shift = 0
        self.tie_note = False
        self.note_value = 0x3c  # The current note's value
        self.std_note_len = 3   # Current note standard length
        self.note_len = 1       # Current note's length
        self.song = song        # Song owning this voice
        self.song_pos = self.start_position
        self.music_data = song.music_data
        self.return_pos = []    # Return positions for sequences
        self.ticks = 0          # Current playback time in ticks
        # self.chirp_track = None # Chirp track associated with voice
        self.chirp_track = ChirpTrack(self.song.chirp_song)
        self.voice_finished = False

    def initialize(self):
        """
        Initialize voice playback
        """
        self.return_pos = [0 for s in self.song.sequences]
        print(self.return_pos)
        self.ticks = 0

    def fetch_data_byte(self, signed=False):
        # data = self.music_data[self.song_pos]
        idx = self.song_pos
        data = little_endian_int(self.music_data[idx:idx + 1], signed=signed)
        self.song_pos += 1
        return data

    def fetch_data_word(self):
        idx = self.song_pos
        data = little_endian_int(self.music_data[idx:idx + 2])
        self.song_pos += 2
        return data

    def playback(self):
        # print("voice playback")
        voice_played = False

        if not self.voice_on:
            return False     # voice_played: False
        if self.note_len <= 0:
            print("Ultima4Voice error: noteLen <= 0")
            quit()
        voice_played = True
        self.note_len -= 1
        if self.note_len == 0:
            self.voice_finished = False
            while not self.voice_finished:
                music_data = self.music_data
                song_byte = self.fetch_data_byte()
                if song_byte == 0:
                    # command mode
                    self.command_mode = True
                    while self.command_mode:
                        song_byte = music_data[self.song_pos]
                        self.song_pos += 1
                        cmd_switch = {
                            0x10: self.set_adsr_release_time,
                            0x11: self.set_transpose,
                            0x12: self.set_pitchbend,
                            0x18: self.set_adsr_attack_rate,
                            0x20: self.set_adsr_decay_rate,
                            0x28: self.set_adsr_sustain_level,
                            0x30: self.set_adsr_release_rate,
                            0x38: self.set_adsr_attack_level,
                            0x80: self.start_sequence,
                            0x81: self.return_from_sequence,
                            0x82: self.end_voice,
                            0x83: self.set_tempo
                        }
                        if song_byte not in cmd_switch.keys():
                            print("unknown command:", song_byte)
                            self.command_mode = False
                        else:
                            cmd_switch[song_byte]()
                elif song_byte < 0x80:
                    self.adsr_phase = 1
                    self.note_len = self.std_note_len
                    value = song_byte + self.transpose
                    print("start note {} len {}".format(value, self.note_len))
                    if value > 120:
                        print("value: ", value)
                        # quit()
                    note = Note(self.ticks, value + Ultima4Song.MIDI_NOTE_OFFSET, self.note_len)
                    self.chirp_track.notes.append(note)
                    self.voice_finished = True
                elif song_byte == 0x80:
                    self.adsr_phase = 4
                    self.note_len = self.std_note_len
                    print("play rest:", self.note_len)
                    self.voice_finished = True
                else:   # song byte > 0x80
                    self.std_note_len = song_byte & 0x7f
                    print("set new standard length:", self.std_note_len)
        self.ticks += 1
        return voice_played

    def set_adsr_release_time(self):
        print("set release time")
        self.adsr_release_time = self.fetch_data_byte()

    def set_transpose(self):
        self.transpose = self.fetch_data_byte(signed=True)
        print("set transpose:", self.transpose)

    def set_pitchbend(self):
        print("set pitchbend")
        self.pitchbend = self.fetch_data_word()

    def set_adsr_attack_rate(self):
        print("set adsr_attack")
        self.adsr_attack_rate = self.fetch_data_word()

    def set_adsr_decay_rate(self):
        print("set adsr_decay")
        self.adsr_decay_rate = self.fetch_data_word()

    def set_adsr_sustain_level(self):
        print("set adsr_sustain")
        self.adsr_sustain_level = self.fetch_data_word()

    def set_adsr_release_rate(self):
        print("set adsr_release")
        self.adsr_release_rate = self.fetch_data_word()

    def set_adsr_attack_level(self):
        print("set adsr attack")
        self.adsr_attack_level = self.fetch_data_word()

    def start_sequence(self):
        seq = self.fetch_data_byte()
        print("start sequence:", seq)
        if seq < len(self.song.sequences):
            self.return_pos[seq] = self.song_pos
            self.song_pos = self.song.sequences[seq]
            self.song_pos += 2 * len(self.song.voices)
        self.command_mode = False

    def return_from_sequence(self):
        seq = self.fetch_data_byte()
        print("return from sequence:", seq)
        self.song_pos = self.return_pos[seq]
        self.command_mode = False

    def end_voice(self):
        self.voice_on = False
        print("end voice")
        self.command_mode = False
        self.voice_finished = True

    def set_tempo(self):
        tempo = self.fetch_data_word()
        print("set tempo: ", tempo)
        self.song.set_tempo(self.ticks, tempo)
        self.command_mode = False

    def play_note(self, song_byte, new_tie, is_extra_note):
        if (song_byte > 0):
            print("play note")
        else:
            print("play rest")


class Ultima4Music:
    """
    Ultima IV file representation.
    """

    def __init__(self, filename):
        self.filename = filename
        with open(filename, 'rb') as f:
            self.music_data = f.read()
        self.num_songs = self.music_data[0]
        self.name = os.path.basename(filename)

    def __str__(self):
        return "Ultima IV Music file {}, number of songs: {}".format(self.name, self.num_songs)

    def import_song_to_chirp(self, song_no):
        """
        Open and import a MIDI file into the ChirpSong representation.

        :param input_filename: Ultima IV filename.
        """
        song = Ultima4Song(song_no, self)
        return song.chirp_song


# Open the Ultima IV music file
musicPath = constants.project_to_absolute_path('examples/data/appleii_u4/')
f_songinfo = os.path.join(musicPath, 'u4songs.csv')
with open(f_songinfo, 'r') as csvfile:
    csvreader = csv.reader(csvfile, delimiter=",")
    rows = []
    for row in csvreader:
        rows.append(row)
    info = [dict(zip(rows[0], row)) for row in rows[1:]]

for song in info:
    print("Extracting song:", song['title'])
    music = Ultima4Music(os.path.join(musicPath, song['fname']))
    print("Number of songs in file: ", music.num_songs)
    chirp_song = music.import_song_to_chirp(int(song['songno']) - 1)
    midi_song = MIDI()
    output_filename = \
        constants.project_to_absolute_path('examples/data/appleii_u4/%s.mid'
                                           % song['title'])
    midi_song.export_chirp_to_midi(chirp_song, output_filename)
