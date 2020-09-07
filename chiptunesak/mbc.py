# importer/exporter for files created with MusicBoxComposer
# Goal: integrate with ChiptuneSAK to act as an importer and an exporter
# Features:
# - read .mbc file and convert it into an internal MbcStrip class
# - convert MbcStrip to chirp
# - convert chirp to MbcStrip
# - write MbcStrip to file
# when converting MbcStrip to chirp, polyphony needs to be handled:
# - sort music note events by:
#    time, pitch
# - use explode_polyphony to split up chirp song into tracks?

# File format documentation
# see:
# http://www.jellybiscuits.com/phpBB3/viewtopic.php?f=10&t=21#p52
# The format is very simple, all ascii and the header keys are fairly self explanatory.
#
# NoteCount=
#
# after that entry it simply loops through 6 values per note:
# p=pitch
# t=time
# v=volume
# s=selected (ui)
# a=active (since you can deactivate notes)
# i=if the note is illegal due to mechanical limitations (ie too close together)

# Check the FileVersion as in the not to distant future I'll may add other keys (a pitch-shift is on the cards though it may be global), so you might be better off walking through the values and incrementing when you hit the next 'p=', which would then be your next notes pitch value.


from chiptunesak.base import *
from chiptunesak.chirp import Note, ChirpTrack, ChirpSong
from chiptunesak.midi import MIDI

class MusicBox(ChiptuneSAKIO):
    MIDI_NOTE_OFFSET = 21
    TICKS_PER_QUARTER = 48  # equals to the MIDI default value

    @classmethod
    def cts_type(cls):
        return 'MusicBox'

    def __init__(self):
        ChiptuneSAKIO.__init__(self)

    def to_chirp(self, filename, **kwargs):
        """
        Import a Music Box Composer file to Chirp format
        """
        strip = MbcStrip()
        strip.from_file(filename)

        chirp_song = ChirpSong()
        # Clear everything
        chirp_song.reset_all()
        chirp_song.metadata.ppq = self.TICKS_PER_QUARTER
        chirp_song.qticks_notes = self.TICKS_PER_QUARTER
        chirp_song.qticks_durations = self.TICKS_PER_QUARTER

        # create a ChirpTrack
        chirp_track = ChirpTrack(chirp_song)
        chirp_song.tracks.append(chirp_track)
        self.chirp_song.metadata.name = chirp_song.meta_data['StripName']

        for n in strip.get_notes():
            print(n)
            pitch = n.get_pitch()
            pitch = MbcNote.to_midi_pitch(pitch)
            time = int(n.get_time() * self.TICKS_PER_QUARTER * 2 + 0.5)
            # No duration available, arbitrarily set to a 16th
            duration = int(self.TICKS_PER_QUARTER / 4)
            # print("Pitch: ", pitch)
            # print("Time: ", time)
            note = Note(time, pitch, duration)
            chirp_track.notes.append(note)
        
        chirp_song.explode_polyphony(0)
        chirp_song.set_qpm(strip.get_tempo())
        return chirp_song

    def to_file(self, ir_song, filename, **kwargs):
        strip = MbcStrip(ir_song.metadata.name)
        print("To File: ", filename)

        # set initial timing values pqm and ppq:
        qpm = 60
        ppq = self.TICKS_PER_QUARTER
        if ir_song.metadata.qpm is not None:
            qpm = ir_song.metadata.qpm
            print("QPM: " + str(qpm))
        if ir_song.metadata.ppq is not None:
            ppq = ir_song.metadata.ppq
            print("PPQ: " + str(ppq))

        t = 0
        noteCount = 0
        for track in ir_song.tracks:
            print("Track", t)
            for note in track.notes:
                pitch = MbcNote.to_mbc_pitch(note.note_num)
                #print("PITCH", pitch)
                if pitch is None:
                    #print("skip note")
                    continue
                noteCount += 1
                #time = float(note.start_time) / (self.TICKS_PER_QUARTER * 2)
                time = float(note.start_time) * 60 / (qpm * ppq)
                #print("TIME", time)
                mbc_note = MbcNote(time, pitch)
                strip.add_note(mbc_note)
        strip.meta_data['NoteCount'] = str(noteCount)
        strip.export(filename)

class MbcStrip:
    meta_att_list = [
        "FileVersion", "PlaybackSpeed", "noteTextureIndex", "StripName",
        "StripCredits", "StripContact", "StripInfo", "DoLoopPublish",
        "AllowEditingPublish", "AutoPlayPublish", "stripSize", "stripLength", 
        "NoteCount" ]

    def __init__(self, name="abc"):
        self.notes = list()
        self.meta_data = dict()
        self.meta_data = {
            'FileVersion':"1.0",
            'PlaybackSpeed':"1.0",
            'noteTextureIndex':"0",
            'StripName':"",
            'DoLoopPublish':"1",
            'AllowEditingPublish':"0",
            'AutoPlayPublish':"1",
            'stripSize':"30",
            'stripLength':"10.0",
            'NoteCount':"0"
        }
        self.meta_data['StripName'] = name

    def __repr__(self):
        return str(self.notes)

    def __str__(self):
        return self.meta_data['StripName']

    def add_note(self, note):
        self.notes.append(note)

    def from_file(self, filename):
        with open(filename, 'r') as f:
            for line in f:
                (k,v) = line.strip().split("=")
                self.meta_data[k] = v
                if k == "NoteCount":
                    break;
            note_count = int(self.meta_data["NoteCount"])
            for i in range(note_count):
                n = MbcNote()
                n.read_note(f)
                self.add_note(n)
                #print(repr(n))

    def to_tuples(self):
        self.tuplist = list()
        for n in self.notes:
            self.tuplist.append(n.to_tuple())
        #print(self.tuplist)
        return self.tuplist

    def export(self, filename):
        with open(filename, 'w') as f:
            for att in self.meta_att_list:
                f.write(att + "=" + self.meta_data.get(att, "") + "\n")
            for note in self.notes:
                note.export(f)

    def get_notes(self):
        return self.notes

    def get_tempo(self):
        return int(float(self.meta_data.get("PlaybackSpeed", "1.0")) * 120 + 0.5)

class MbcNote:
    # Midi values: 60 = middle C
    midi_pitch_table = [ 41,43,
                  48,50,52,53,55,57,58,59,
                  60,61,62,63,64,65,66,67,68,69,70,71,
                  72,73,74,75,76,77,79,81 ]

    def __init__(self, time=None, pitch=None):
        if time is not None:
            self.time = time
        if pitch is not None:
            self.pitch = pitch
        self.volume = "1.0"
        self.selected = "0"
        self.active = "1"
        self.illegal = "0"
        return

    def __str__(self):
        return "time: " + str(self.time) + " pitch: " + str(self.pitch)

    def __repr__(self):
        return str(self.to_tuple())

    @classmethod
    def to_midi_pitch(cls, mbc_pitch):
        return MbcNote.midi_pitch_table[mbc_pitch]

    @classmethod
    def to_mbc_pitch(cls, midi_pitch):
        if midi_pitch in MbcNote.midi_pitch_table:
            pitch = MbcNote.midi_pitch_table.index(midi_pitch)
        else:
            pitch = None
        return pitch

    def read_note(self, f):
        note = {}
        for i in range(6):
            (k,v) = f.readline().strip().split("=")
            note[k] = v
        self.pitch = int(note['p'])
        self.time = float(note['t'])
        self.volume = note['v']
        self.selected = note['s']
        self.active = note['a']
        self.illegal = note['i']

    def to_tuple(self):
        return (self.time, self.pitch, self.active, self.volume, self.selected, self.illegal)

    def export(self, f):
        f.write("p=" + str(self.pitch) + "\n")
        f.write("t=" + str(self.time) + "\n")
        f.write("v=" + self.volume + "\n")
        f.write("s=" + self.selected + "\n")
        f.write("a=" + self.active + "\n")
        f.write("i=" + self.illegal + "\n")

    def get_pitch(self):
        return self.pitch

    def set_pitch(self, pitch):
        self.pitch = pitch

    def get_time(self):
        return self.time

    def set_time(self, time):
        self.time = time

#filename = "karaelia.mbc"

#meta_data = dict()
#is_header = True
#note_count = 0

#strip = MbcStrip()
#strip.from_file(filename)
#print(strip)
#print(repr(strip))
#print("tuples:")
#print(sorted(strip.to_tuples()))
#sstrip = sorted(strip.to_tuples())
#strip.export("out.mbc")
#chirp_song = MusicBox().to_chirp(filename)
#print(chirp_song)

#midi_song = MIDI()
#output_filename = "karaelia.mid"
#midi_song.export_chirp_to_midi(chirp_song, output_filename)

#MusicBox().to_file(chirp_song, "out2.mbc")
