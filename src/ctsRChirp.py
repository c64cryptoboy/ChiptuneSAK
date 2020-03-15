# cstRChirp.py
#
# RChirp is a row-based verison of chirp, useful for export from and to trackers,
# and other jiffy-based music players.
# Rows can be constructed and accessed in both sparse (dictionary-like) and contiguous (list-like) forms. 

import copy
from ctsBase import *

@dataclass
class RChirpRow:
    """
    The basic RChirp row
    """
    row_num: int = None     # rchirp row number
    jiffy_num: int = None   # jiffy num since time 0
    note_num: int = None    # MIDI note number; None means no note asserted
    instrument: int = None  # Instrument number; None means no change
    gate: bool = None       # Gate on/off tri-value True/False/None; None means no gate change
    jiffy_len: int = None   # Jiffies to process this row (until next row)

    def __gt__(self, rchirp_row):
        return self.row_num > rchirp_row.row_num

class RChirpOrderList:
    """
    An order list made up of a set of patterns
    """

    def __init__(self, patterns=None):
        self.patterns = []
        if patterns is not None:
            self.patterns = copy.copy(patterns)


class RChirpPattern:
    """
    A pattern made up of a set of rows
    """

    def __init__(self, rows):
        self.rows = []
        row_times = sorted(rows)
        base_time = min(sorted(rows))
        for update in row_times:
            self.rows[update - base_time] = copy.copy(rows[update])


class RChirpVoice:
    """
    The representation of a single voice; contains rows
    """
    
    def __init__(self, rchirp_song, chirp_track=None):
        self.rchirp_song = rchirp_song
        self.rows = collections.defaultdict(RChirpRow)
        if chirp_track is not None:
            tmp = str(type(chirp_track))
            if tmp != "<class 'ctsChirp.ChirpTrack'>":
                raise ChiptuneSAKTypeError("MChirpTrack init can only import ChirpTrack objects.")
            else:
                self.import_chirp_track(chirp_track)

    # Rows are indexed by row num.  Returns rows indexed by jiffy number instead.
    def get_jiffy_indexed_rows(self):
        return_val = {v.jiffy_num:v for k,v in self.rows.items()}
        return_val = collections.defaultdict(RChirpRow, return_val)
        return return_val

    # Helper method for when treating rchirp like a list of contiguous rows,
    # instead of a sparse dictonary of rows
    def append_row(self, rchirp_row):
        insert_row = copy.deepcopy(rchirp_row)
        insert_row.row_num = self.get_next_row_num()
        self.rows[insert_row.row_num] = insert_row

    def get_last_row(self):
        if len(self.rows) == 0:
            return None
        return self.rows[max(self.rows, key=self.rows.get)]

    def get_next_row_num(self):
        if len(self.rows) == 0:
            return 0
        return max(self.rows) + 1

    # Returns False if voice contains a sparse row representation
    def is_contiguous(self):
        curr_jiffy=0
        for row_num in sorted(self.rows):
            if self.rows[row_num].jiffy_num != curr_jiffy:
                return False
            curr_jiffy += self.rows[row_num].jiffy_len
        return True

    def integrity_check(self):
        row_nums = []
        jiffy_nums = []
        for k, row in self.rows.items():
            assert k == row.row_num, "Error: RChirpVoice has a row number that doesn't match its row number index"
            assert row.row_num is not None, "Error: RChirpRow row cannot have row_num = None"
            assert row.row_num >=0, "Error: RChirpRow row cannot have a negative row_num"            
            assert row.jiffy_num is not None, "Error: RChirpRow row cannot have jiffy_num = None"
            assert row.jiffy_num >=0, "Error: RChirpRow row cannot have a negative jiffy_num"
            if row.note_num is not None:
                assert row.note_num >=0, "Error: RChirpRow row cannot have a negative note_num"
            if row.instrument is not None:    
                assert row.instrument >=0, "Error: RChirpRow row cannot have a negative instrument"
            assert row.jiffy_len is not None, "Error: RChirpRow row cannot have jiffy_len = None"
            assert row.jiffy_len >=0, "Error: RChirpRow row cannot have a negative jiffy_len"
            row_nums.append(row.row_num)
            jiffy_nums.append(row.jiffy_num)
        assert len(row_nums) == len(set(row_nums)), "Error: RChirpVoice row numbers must be unique"
        assert len(jiffy_nums) == len(set(jiffy_nums)), "Error: RChirpVoice rows' jiffy_nums must be unique"

    def _find_closest_row_after(self, row):
        for r in sorted(self.rows):
            if r >= row:
                return r
        return max(self.rows)

    def import_chirp_track(self, chirp_track):
        """
        Imports a Chirp track into a raw RChirpVoice object.  No compression or conversion to patterns
           and orderlists performed

            :param chirp_track: A ctsChirpTrack object; the track must be non-polyphonic and quantized.
        """
        if not chirp_track.is_quantized():
            raise ChiptuneSAKQuantizationError("Track must be quantized to generate RChirp.")
        if chirp_track.is_polyphonic():
            raise ChiptuneSAKPolyphonyError("Track must be non-polyphonic to generate RChirp.")
        # Right now don't allow tempo variations; just use the initial tempo
        ticks_per_jiffy = (self.rchirp_song.metadata.qpm * self.rchirp_song.metadata.ppq * 60) \
                            / self.rchirp_song.update_freq
        jiffies_per_row = chirp_track.qticks_notes / ticks_per_jiffy
        ticks_per_row = ticks_per_jiffy * jiffies_per_row
        tmp_rows = collections.defaultdict(RChirpRow)

        # Insert the notes into the voice
        for n in chirp_track.notes:
            n_row = n.start_time // ticks_per_row
            tmp_rows[n_row].note_num = n.note_num
            tmp_rows[n_row].gate = True
            tmp_rows[n_row].jiffy_len = jiffies_per_row
            e_row = (n.start_time + n.duration) / ticks_per_row
            tmp_rows[e_row].gate = False

        program_changes = [ProgramEvent(e.start_time, e.program) for e in chirp_track.other
                           if e.msg.type == 'program_change']

        for p in sorted(program_changes):
            n_row = self._find_closest_row_after(p.start_time / ticks_per_row)
            tmp_rows[n_row].instrument = int(p.program)


class RChirpSong:
    """
    The representation of an RChirp song.  Contains voices, voice groups, and metadata.
    """

    def __init__(self, chirp_song=None):
        self.update_freq = ARCH['NTSC'].frame_rate
        self.voices = []
        self.voice_groups = []
        self.stats = {}
        self.metadata = None

        if chirp_song is not None:
            self.metadata = copy.deepcopy(chirp_song.metadata)
            tmp = str(type(chirp_song))
            if tmp != "<class 'ctsChirp.ChirpSong'>":
                raise ChiptuneSAKTypeError("MChirpSong init can only import ChirpSong objects")
            else:
                self.import_chirp_song(chirp_song)

    def import_chirp_song(self, chirp_song):
        """
        Imports a ChirpSong

            :param chirp_song: A ctsChirp.ChirpSong song
        """
        if not chirp_song.is_quantized():
            raise ChiptuneSAKQuantizationError("ChirpSong must be quantized to create RChirp.")
        if chirp_song.is_polyphonic():
            raise ChiptuneSAKPolyphonyError("ChirpSong must not be polyphonic to create RChirp.")
        for t in chirp_song.tracks:
            self.voices.append(RChirpVoice(self, t))
        self.metadata = copy.deepcopy(chirp_song.metadata)
        self.other = copy.deepcopy(chirp_song.other)

    def is_contiguous(self):
        for voice in self.voices:
            if not voice.is_contiguous():
                return False
        return True

    def integrity_check(self):
        for voice in self.voices:
            voice.integrity_check()

    def get_jiffy_indexed_voices(self):
        return_val = []
        for voice in self.voices:
            return_val.append(voice.get_jiffy_indexed_rows())
        return return_val

    @staticmethod    
    def __str_with_null_handling(a_value):
        if a_value is None:
            return ''
        return str(a_value)

    # Create CVS debug output
    def note_time_data_str(self):
        num_channels = len(self.voices)
        max_tick = max(self.voices[i].get_last_row().jiffy_num for i in range(num_channels))

        channels_time_events = self.get_jiffy_indexed_voices()

        csv_header = []
        csv_header.append("jiffy")
        for i in range(num_channels):
            csv_header.append("v%d row #" % (i+1))
            csv_header.append("v%d note" % (i+1))
            csv_header.append("v%d on/off/none" % (i+1))
            csv_header.append("v%d tempo update" % (i+1))
 
        csv_rows = []
        prev_tempo = [-1] * num_channels
        for tick in range(max_tick+1):
            # if any channel has a entry at this tick, create a row for all channels
            if any(tick in channels_time_events[i] for i in range(num_channels)):
                a_csv_row = []
                a_csv_row.append("%d" % tick)
                for i in range(num_channels):
                    if tick in channels_time_events[i]:
                        event = channels_time_events[i][tick]
                        a_csv_row.append("%s" % event.row_num)
                        a_csv_row.append("%s" % RChirpSong.__str_with_null_handling(event.note_num))
                        a_csv_row.append("%s" % RChirpSong.__str_with_null_handling(event.gate))
                        if event.jiffy_len != prev_tempo[i]:
                            tempo_update = event.jiffy_len
                        else:
                            tempo_update = ''
                        a_csv_row.append("%s" % str(tempo_update))
                    else:
                        a_csv_row.append("")
                        a_csv_row.append("")
                        a_csv_row.append("")
                        a_csv_row.append("")
                csv_rows.append(','.join(a_csv_row))
        spreadsheet = '\n'.join(csv_rows)
        spreadsheet = ','.join(csv_header) + '\n' + spreadsheet
   
        return spreadsheet

 
