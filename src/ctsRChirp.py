# cstRChirp.py
#
# RChirp is a row-based verison of chirp, useful for export from and to trackers,
# and other jiffy-based music players.
# Rows can be constructed and accessed in both sparse (dictionary-like) and contiguous (list-like) forms. 
#
# TODO:
# - test Knapp's chirp->rchirp functionality
# - write rchirp->chirp converter

import copy
from functools import reduce, partial
import math
import ctsChirp
from ctsBase import *
from ctsConstants import DEFAULT_MIDI_PPQN

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

    def get_jiffy_indexed_rows(self):
        """ 
        Returns rows indexed by jiffy number

        A voice holds onto a dictionary of rows keyed by row number.  This method returns
        a dictionary of rows keyed by jiffy number. 

        Returns:
            defaultdict: A dictionary of rows keyed by jiffy number
        """        
        return_val = {v.jiffy_num:v for k,v in self.rows.items()}
        return_val = collections.defaultdict(RChirpRow, return_val)
        return return_val

    def append_row(self, rchirp_row):
        """
        Appends a row to the voice's collection of rows

        This is a helper method for treating rchirp like a list of contiguous rows,
        instead of a sparse dictonary of rows

        Parameters:
           rchirp_row (RChirpRow): A row to "append"
        """
        insert_row = copy.deepcopy(rchirp_row)
        insert_row.row_num = self.get_next_row_num()
        self.rows[insert_row.row_num] = insert_row

    def get_last_row(self):
        """
        Returns the row with the largest jiffy number (latest in time)

        Returns:
            RChirpRow: row with latest jiffy number
        """
        if len(self.rows) == 0:
            return None
        return self.rows[max(self.rows, key=self.rows.get)]

    def get_next_row_num(self):
        """
        Returns one greater than the largest row number held onto by the voice

        Returns:
            int: largest row number + 1
        """
        if len(self.rows) == 0:
            return 0
        return max(self.rows) + 1

    def is_contiguous(self):
        """
            Determines if the voices rows are contiguous, without gaps in time

            Returns:
                boolean: True if rows are contiguous, False if not
        """
        curr_jiffy=0
        for row_num in sorted(self.rows):
            if self.rows[row_num].jiffy_num != curr_jiffy:
                return False
            curr_jiffy += self.rows[row_num].jiffy_len
        return True

    def integrity_check(self):
        """
            Finds problems with a voice's row data

            Raises:
                AssertionError
        """
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
    
    def voice_count(self):
        return len(self.voices)

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
        """
            Determines if the voices' rows are contiguous, without gaps in time

            Returns:
                boolean: True if rows are contiguous, False if not
        """
        for voice in self.voices:
            if not voice.is_contiguous():
                return False
        return True

    def integrity_check(self):
        """
            Finds problems with voices' row data

            Raises:
                AssertionError
        """        
        for voice in self.voices:
            voice.integrity_check()

    def get_jiffy_indexed_voices(self):
        """ 
        Returns a list of rows for each voice in a list.  Rows indexed by jiffy number.

        Returns:
            list: A list of lists
        """  

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
        """ 
        Returns a comma-separated value list representation of the rchirp data

        Returns:
            str: CSV string
        """         
        max_tick = max(self.voices[i].get_last_row().jiffy_num for i in range(self.voice_count()))

        channels_time_events = self.get_jiffy_indexed_voices()

        csv_header = []
        csv_header.append("jiffy")
        for i in range(self.voice_count()):
            csv_header.append("v%d row #" % (i+1))
            csv_header.append("v%d note" % (i+1))
            csv_header.append("v%d on/off/none" % (i+1))
            csv_header.append("v%d tempo update" % (i+1))
 
        csv_rows = []
        prev_tempo = [-1] * self.voice_count()
        for tick in range(max_tick+1):
            # if any channel has a entry at this tick, create a row for all channels
            if any(tick in channels_time_events[i] for i in range(self.voice_count())):
                a_csv_row = []
                a_csv_row.append("%d" % tick)
                for i in range(self.voice_count()):
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

    def convert_to_chirp(self, song_name = 'TODO: GET FROM METADATA INSTEAD'):
        """ 
        Convert rchirp song to chirp

        This conversion is lossy TODO: details here

        Returns:
            ChirpSong: chirp conversion
        """  
        def tick_to_midi(tick, offset=0, factor=1):
            return (tick - offset) * factor

        song = ctsChirp.ChirpSong()
        song.metadata.ppq = DEFAULT_MIDI_PPQN
        song.name = song_name

        channels_time_events = self.get_jiffy_indexed_voices()
        all_ticks = sorted(set(int(t) for i in range(self.voice_count()) for t in channels_time_events[i].keys()))
        note_ticks = sorted([t for t in all_ticks if any(channels_time_events[i].get(t, None) 
                        and (channels_time_events[i][t].gate is not None) for i in range(self.voice_count()))])
        notes_offset = note_ticks[0]
        # TODO: Should the two "100"s be parameterized?
        ticks_per_note = reduce(math.gcd, (note_ticks[i] - notes_offset for i in range(100)))
        if ticks_per_note < 3:  # no decent gcd for this data
            ticks_per_note = 6
        notes_per_minute = 60 * 60 / ticks_per_note
        tmp = notes_per_minute // 100
        tempo = int(notes_per_minute // tmp)
        tick_factor = int(song.metadata.ppq // tempo * tmp)

        tick_to_miditick = partial(tick_to_midi, offset=notes_offset, factor=tick_factor)

        midi_tick = 0
        for it, channel_data in enumerate(channels_time_events):
            track = ctsChirp.ChirpTrack(song)
            track.name = 'Track %d' % (it + 1)
            track.channel = it
            current_note = None
            for tick in sorted(channel_data):
                midi_tick = tick_to_miditick(tick)
                event = channel_data[tick]
                if event.gate:
                    if current_note:
                        new_note = ctsChirp.Note(
                            current_note.start_time, current_note.note_num, midi_tick - current_note.start_time
                        )
                        if new_note.duration > 0:
                            track.notes.append(new_note)
                    current_note = ctsChirp.Note(midi_tick, event.note_num, 1)
                elif event.gate is False:
                    if current_note:
                        new_note = ctsChirp.Note(
                            current_note.start_time, current_note.note_num, midi_tick - current_note.start_time
                        )
                        if new_note.duration > 0:
                            track.notes.append(new_note)
                    current_note = None
            if current_note:
                new_note = ctsChirp.Note(
                    current_note.start_time, current_note.note_num, midi_tick - current_note.start_time
                )
                if new_note.duration > 0:
                    track.notes.append(new_note)
            song.tracks.append(track)

        return song

