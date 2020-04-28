import os
import ctsMidi
from ctsChirp import ChirpSong
from ctsBytesUtil import big_endian_int, little_endian_int

class Ultima4Song:
    def __init__(self, song_no, u4music):
        self.sequences = []
        self.voices = []
        voices = self.voices
        # TODO: check for valid song number
        self.u4music = u4music
        self.song_no = song_no
        self.music_data = u4music.music_data
        music_data = self.music_data
        idx = song_no * 2 + 1
        self.song_offset = little_endian_int(music_data[idx:idx+2])
        print("song_offset: ", self.song_offset)

        idx = self.song_offset
        self.num_voices = music_data[idx]
        print("number of voices: ", self.num_voices)

        idx += 1
        for v in range(self.num_voices):
            # create voices
            start_position = little_endian_int(music_data[idx:idx+2]) + self.song_offset
            print("voice offset: ", start_position)
            voices.append(Ultima4Voice(self, start_position))
            idx += 2

        #idx += 2 * self.num_voices
        print("offset i: ", idx)
        num_sequences = music_data[idx]
        print("number of sequences: ", num_sequences)

        idx += 1
        for seq in range(num_sequences):
            start_pos = little_endian_int(music_data[idx:idx+2])
            self.sequences.append(start_pos)
            idx += 2
        print(self.sequences)

        # extraction loop
        any_voice_played = True
        while any_voice_played:
            any_voice_played = False
            for index, voice in enumerate(voices):
                print("voice", index)
                if voice.playback():
                    any_voice_played = True
                

class Ultima4Voice:
    def __init__(self, song, start_position):
        self.voice_on = False
        self.start_position = start_position
        self.transpose = 0
        self.freq_shift = 0
        self.voice_on = True
        self.tie_note = False
        self.seq_depth = 0
        self.note_value = 0x3c
        self.std_note_len = 3
        self.note_len = 1
        self.note_on = 0
        self.song_pos = self.start_position
        self.music_data = song.music_data

    def fetch_data_byte(self):
        data = self.music_data[self.song_pos]
        self.song_pos += 1
        return data

    def fetch_data_word(self):
        idx = self.song_pos
        data = little_endian_int(self.music_data[idx:idx+2])
        idx += 2
        return data

    def playback(self):
        print("voice playback")
        voice_played = False

        if not self.voice_on:
            return False     # voice_played: False
        if self.note_len <= 0:
            print("Ultima4Voice error: noteLen <= 0")
            quit()
        voice_played = True
        self.note_len -= 1
        if self.note_len == 0:
            print("note finished")
            voice_finished = False
            while not voice_finished:
                music_data = self.music_data
                song_byte = self.fetch_data_byte()
                if song_byte == 0:
                    # command mode
                    command_mode = True
                    while command_mode:
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
                            print("Ultima4Voice error: unknown command:", song_byte)
                            command_mode = False
                        else:
                            cmd_switch[song_byte]()
                elif song_byte < 0x80:
                    self.adsr_phase = 1
                    self.note_len = self.std_note_len
                    value = song_byte + self.transpose
                    print("start note {} len {}".format(value, self.note_len))
                    voice_finished = True
                elif song_byte == 0x80:
                    self.adsr_phase = 4
                    self.note_len = self.std_note_len
                    print("play rest:", self.note_len)
                    voice_finished = True
                else:   # song byte > 0x80
                    self.std_note_len = song_byte & 0x7f
                    print("set new standard length:", self.std_note_len)
        return voice_played


    def set_adsr_release_time(self):
        print("set release time")
        self.adsr_release_time = self.fetch_data_byte()

    def set_transpose(self):
        print("set transpose")
        self.transpose = self.fetch_data_byte()

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
        sequence = self.fetch_data_byte()
        print("start sequence:", sequence)

    def return_from_sequence(self):
        sequence = self.fetch_data_byte()
        print("return from sequence:", sequence)

    def end_voice(self):
        self.voice_on = False
        print("end voice")

    def set_tempo(self):
        tempo = self.fetch_data_word()
        print("set tempo: ", tempo)


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
       return "Ultima IV Music file {}, number of songs: {}".format(self.name,
              self.num_songs)

    def import_song_to_chirp(self, song_no):
        """
        Open and import a MIDI file into the ChirpSong representation.

        :param input_filename: Ultima IV filename.
        """
        chirp_song = ChirpSong()
        # Clear everything
        chirp_song.reset_all()
        song = Ultima4Song(song_no, self)
        #idx = songno * 2 + 1
        #song_offset = little_endian_int(self.music_data[idx:idx+2])
        #print("song_offset: ", song_offset)
        #idx = song_offset
        #num_voices = self.music_data[idx]
        #print("number of voices: ", num_voices)
        #for v in range(num_voices):
        #    print("extracting voice ", v)

        return chirp_song

# Open the Ultima IV music file
music = Ultima4Music("../res/muso")
print("Number of songs in file: ", music.num_songs)
print(music.name)
print(music)
#chirp_song = music.import_song_to_chirp(0)
chirp_song = music.import_song_to_chirp(1)
#chirp_song = music.import_song_to_chirp(2)
#chirp_song = music.import_song_to_chirp(3)
print(chirp_song)



