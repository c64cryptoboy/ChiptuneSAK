# cstRChirp.py
#
# RChirp is a row-based verison of chirp, useful for export from and to trackers,
# and other jiffy-based music players.
# Rows can be constructed and accessed in both sparse (dictionary-like) and contiguous (list-like) forms. 
#
# TODO:
# - create proper docstrings on class defs (methods already done)

import copy
from functools import reduce
import math
import ctsChirp
from ctsBase import *
from ctsConstants import DEFAULT_MIDI_PPQN
from dataclasses import dataclass


@dataclass(order=True)
class RChirpRow:
    """
    The basic RChirp row
    """
    row_num: int = None           #: rchirp row number
    jiffy_num: int = None         #: jiffy num since time 0
    note_num: int = None          #: MIDI note number; None means no note asserted
    instr_num: int = None         #: Instrument number
    new_instrument: int = None    #: Instrument number; None means no change
    gate: bool = None             #: Gate on/off tri-value True/False/None; None means no gate change
    jiffy_len: int = None         #: Jiffies to process this row (until next row)
    new_jiffy_tempo: int = None   #: New tempo for channel (not global); None means no change

    def match(self, other):
        if self.row_num != other.row_num \
                or self.jiffy_num != other.jiffy_num \
                or self.jiffy_len != other.jiffy_len:
            return False
        if self.note_num is not None or other.note_num is not None:
            if self.note_num != other.note_num:
                return False
        if self.gate is not None or other.gate is not None:
            if self.gate != other.gate:
                return False
        if self.instr_num is not None or other.instr_num is not None:
            if self.instr_num != other.instr_num:
                return False
        if self.new_instrument is not None and other.new_instrument is not None:
            if self.new_instrument != other.new_instrument:
                return False
        if self.new_jiffy_tempo is not None and other.new_jiffy_tempo is not None:  # only check if both
            if self.new_jiffy_tempo != other.new_jiffy_tempo:
                return False
        return True


@dataclass
class RChirpOrderEntry:
    pattern_num: int = None
    transposition: int = 0
    repeats: int = 1


class RChirpOrderList(list):
    """
    An order list made up of a set of patterns
    """
    pass


class RChirpPattern:
    """
    A pattern made up of a set of rows
    """
    def __init__(self, rows=None):
        self.rows = []                  #: List of RChirpRow instances (NOT a dictionary!m No gaps allowed!)

        if rows is not None:
            base_row = min(r.row_num for r in rows)      # Starting row frame number
            base_jiffy = min(r.jiffy_num for r in rows)  # Starting jiffy number
            for r in rows:
                r.row_num -= base_row
                r.jiffy_num -= base_jiffy
                assert r.jiffy_num >= 0, "Illegal jiffy number"
                self.rows.append(r)
        self.rows.sort()  # Sort the rows by the row number member.

    def __str__(self):
        return '\n  '.join(str(r) for r in self.rows)


class RChirpVoice:
    """
    The representation of a single voice; contains rows
    """
    def __init__(self, rchirp_song, chirp_track=None):
        self.rchirp_song = rchirp_song                  #: The song this voice belongs to
        self.rows = collections.defaultdict(RChirpRow)  #: dictionary: K:row num, V: RChirpRow instance
        self.orderlist = RChirpOrderList()
        self.name = ''
        if chirp_track is not None:
            tmp = str(type(chirp_track))
            if tmp != "<class 'ctsChirp.ChirpTrack'>":
                raise ChiptuneSAKTypeError("MChirpTrack init can only import ChirpTrack objects.")
            else:
                self.import_chirp_track(chirp_track)     

    @property
    def jiffy_indexed_rows(self):
        """
        Returns dictionary of rows indexed by jiffy number

        A voice holds onto a dictionary of rows keyed by row number.  This method returns
        a dictionary of rows keyed by jiffy number. 

        :return: A dictionary of rows keyed by jiffy number
        :rtype: defaultdict
        """
        return_val = {v.jiffy_num: v for k, v in self.rows.items()}
        return_val = collections.defaultdict(RChirpRow, return_val)
        return return_val

    @property
    def sorted_rows(self):
        """
        Returns a list of row-number sorted rows for the voice

        :return: A sorted list of RChirpRow instances
        :rtype: list
        """
        return [self.rows[k] for k in sorted(self.rows.keys())]

    def append_row(self, rchirp_row):
        """
        Appends a row to the voice's collection of rows

        This is a helper method for treating rchirp like a list of contiguous rows,
        instead of a sparse dictionary of rows
        
        :param rchirp_row: A row to "append"
        :type rchirp_row: RChirpRow
        """
        insert_row = copy.deepcopy(rchirp_row)
        insert_row.row_num = self.next_row_num
        self.rows[insert_row.row_num] = insert_row

    @property
    def last_row(self):
        """
        Returns the row with the largest jiffy number (latest in time)

        :return: row with latest jiffy number
        :rtype: RChirpRow
        """
        return None if len(self.rows) == 0 else self.rows[max(self.rows, key=self.rows.get)]

    @property
    def next_row_num(self):
        """
        Returns one greater than the largest row number held onto by the voice

        :return: largest row number + 1
        :rtype: int
        """
        return 0 if len(self.rows) == 0 else max(self.rows) + 1

    def is_contiguous(self):
        """
        Determines if the voice's rows are contiguous.  This function requires that row numbers
        are consecutive and that the corresponding jiffy numbers have no gaps.
        
        :return: True if rows are contiguous, False if not
        :rtype: boolean
        """
        start_row = 0 if len(self.rows) == 0 else min(self.rows)
        curr_jiffy, curr_row = self.rows[start_row].jiffy_num, self.rows[start_row].row_num
        for row_num in sorted(self.rows):
            if self.rows[row_num].row_num != curr_row:
                return False
            if self.rows[row_num].jiffy_num != curr_jiffy:
                return False
            curr_row += 1
            curr_jiffy += self.rows[row_num].jiffy_len
        return True

    def integrity_check(self):
        """
        Finds problems with a voice's row data

        :return: True if all integrity checks pass
        :raises AssertionError: Various integrity failure assertions possible
        """
        row_nums = []
        jiffy_nums = []
        for k, row in self.rows.items():
            assert k == row.row_num, "Error: RChirpVoice has a row number that doesn't match its row number index"
            assert row.row_num is not None, "Error: RChirpRow row cannot have row_num = None"
            assert row.row_num >= 0, "Error: RChirpRow row cannot have a negative row_num"
            assert row.jiffy_num is not None, "Error: RChirpRow row cannot have jiffy_num = None"
            assert row.jiffy_num >= 0, "Error: RChirpRow row cannot have a negative jiffy_num"
            if row.note_num is not None:
                assert row.note_num >= 0, "Error: RChirpRow row cannot have a negative note_num"
            if row.new_instrument is not None:    
                assert row.new_instrument >= 0, "Error: RChirpRow row cannot have a negative instrument"
            assert row.jiffy_len is not None, "Error: RChirpRow row cannot have jiffy_len = None"
            assert row.jiffy_len >= 0, "Error: RChirpRow row cannot have a negative jiffy_len"
            row_nums.append(row.row_num)
            jiffy_nums.append(row.jiffy_num)
        assert len(row_nums) == len(set(row_nums)), "Error: RChirpVoice row numbers must be unique"
        assert len(jiffy_nums) == len(set(jiffy_nums)), "Error: RChirpVoice rows' jiffy_nums must be unique"
        return True

    def _find_closest_row_after(self, row):
        for r in sorted(self.rows):
            if r >= row:
                return r
        if len(self.rows) == 0:
            return 0
        else:
            return self.get_last_row().row_num

    def get_filled_rows(self):
        ret_rows = []
        max_row = max(self.rows[rn].row_num for rn in self.rows)
        assert 0 in self.rows, "No row 0 in rows"  # Row 0 should exist!
        last_row = self.rows[0]
        current_instrument = 1
        for rn in range(max_row + 1):  # Because max_row needs to be included!
            if rn in self.rows:
                last_row = copy.copy(self.rows[rn])
                if last_row.new_instrument is not None:
                    current_instrument = last_row.new_instrument
                if last_row.note_num is not None:
                    last_row.instr_num = current_instrument
                ret_rows.append(last_row)
            else:
                tmp_row = RChirpRow()
                tmp_row.row_num = rn
                tmp_row.jiffy_num = last_row.jiffy_num + last_row.jiffy_len
                tmp_row.jiffy_len = last_row.jiffy_len
                last_row = copy.copy(tmp_row)
                ret_rows.append(last_row)
        return ret_rows

    def _fixup_rows(self):
        """
        Goes through the rows and adds missing elements
        """
        last = copy.deepcopy(self.rows[0])
        for r in sorted(self.rows):
            if last.row_num is None:
                print("Row number is None!")
            row = self.rows[r]
            # Make sure the row has a row_num
            if row.row_num is None:
                row.row_num = r
            # Jiffy number is derived from the last row
            if row.jiffy_num is None:
                row.jiffy_num = last.jiffy_num + (row.row_num - last.row_num) * last.jiffy_len
            # If no jiffy length, use the one from the last row
            if row.jiffy_len is None:
                row.jiffy_len = last.jiffy_len
            # If the row is a note off, set the note number
            if row.gate is False:
                row.note_num = last.note_num
            last = copy.deepcopy(row)
            self.rows[r] = row

    def orderlist_to_rows(self):
        ret_rows = []
        current_row = 0
        current_jiffy = 0
        irow = 0
        for entry in self.orderlist:
            patt = entry.pattern_num
            trans = entry.transposition
            if patt >= len(self.rchirp_song.patterns):
                raise ChiptuneSAKContentError(f"Illegal pattern number: {patt}")
            for _ in range(entry.repeats):
                for r in self.rchirp_song.patterns[patt].rows:
                    tmp_row = copy.copy(r)
                    tmp_row.row_num = current_row
                    tmp_row.jiffy_num = current_jiffy
                    if tmp_row.note_num is not None:
                        tmp_row.note_num += trans
                    current_row += 1
                    current_jiffy += tmp_row.jiffy_len
                    ret_rows.append(tmp_row)
                    irow += 1
        return ret_rows

    def validate_orderlist(self):
        filled_rows = self.get_filled_rows()
        compressed_rows = self.orderlist_to_rows()
        if len(filled_rows) != len(compressed_rows):
            return False
        for irow, c_row in enumerate(compressed_rows):
            if not c_row.match(filled_rows[irow]):
                print(f"row mismatch in voice {self.name} at row {irow}:")
                print(f"  compressed: {c_row}")
                print(f"  original:   {filled_rows[irow]}")
                return False
        return True

    def import_chirp_track(self, chirp_track):
        """
        Imports a Chirp track into a raw RChirpVoice object.  No compression or conversion to patterns
           and orderlists performed.  Track must be non-polyphonic and quantized.
        
        :param chirp_track: A chirp track
        :type chirp_track: ctsChirp.ChirpTrack
        :raises ChiptuneSAKQuantizationError: Thrown if chirp track is not quantized
        :raises ChiptuneSAKPolyphonyError: Thrown if a single voice contains polyphony
        """
        if not chirp_track.is_quantized():
            raise ChiptuneSAKQuantizationError("Track must be quantized to generate RChirp.")
        if chirp_track.is_polyphonic():
            raise ChiptuneSAKPolyphonyError("Track must be non-polyphonic to generate RChirp.")

        self.name = chirp_track.name
        # Right now don't allow tempo variations; just use the initial tempo
        ticks_per_jiffy = int((self.rchirp_song.metadata.qpm * self.rchirp_song.metadata.ppq / 60)
                            / self.rchirp_song.update_freq)
        jiffies_per_row = chirp_track.qticks_notes // ticks_per_jiffy
        ticks_per_row = ticks_per_jiffy * jiffies_per_row
        rows_per_quarter = int(self.rchirp_song.metadata.ppq / ticks_per_row + 0.5)
        jiffies_per_quarter = rows_per_quarter * jiffies_per_row
        jiffies_per_row = jiffies_per_quarter * chirp_track.qticks_notes // self.rchirp_song.metadata.ppq
        ticks_per_row = chirp_track.qticks_notes
        tmp_rows = collections.defaultdict(RChirpRow)

        # Always insert a row number 0
        tmp_rows[0] = RChirpRow(row_num=0,
                                jiffy_num=0,
                                jiffy_len=jiffies_per_row,
                                new_jiffy_tempo=jiffies_per_row)
        # Insert the notes into the voice
        for n in chirp_track.notes:
            n_row = int(n.start_time // ticks_per_row)  # Note: if tempo varies this gets complicated.
            tmp_rows[n_row].row_num = n_row
            tmp_rows[n_row].jiffy_num = n_row * jiffies_per_row
            tmp_rows[n_row].note_num = n.note_num
            tmp_rows[n_row].gate = True
            tmp_rows[n_row].jiffy_len = jiffies_per_row
            e_row = int((n.start_time + n.duration) // ticks_per_row)
            tmp_rows[e_row].gate = False

        # Program changes will only occur on rows tat already have note content.  SO no new rows will be created.
        for p in sorted(chirp_track.program_changes):
            n_row = self._find_closest_row_after(p.start_time / ticks_per_row)
            new_instrument = (p.program % 13)
            tmp_rows[n_row].new_instrument = int(new_instrument)  # TODO: Map midi instruments into tracker instruments

        self.rows = tmp_rows
        self._fixup_rows()


class RChirpSong:
    """
    The representation of an RChirp song.  Contains voices, voice groups, and metadata.
    """
    def __init__(self, chirp_song=None):
        self.update_freq = ARCH['NTSC-C64'].frame_rate  #: Update frequency expressed as frame rate
        self.voices = []                                #: List of RChirpVoice instances
        self.voice_groups = []                          #: Voice groupings for lowering to multiple chips
        self.patterns = []                              #: Patterns to be shared among the voices
        self.stats = {}                                 #: TODO: ???
        self.metadata = None                            #: Song metadata (author, copyright, etc.)
        self.other = None                               #: Other meta-events in song
        self.compressed = False                         #: Has song been through compression algorithm?

        if chirp_song is None:
            self.metadata = SongMetadata()
        else:
            self.metadata = copy.deepcopy(chirp_song.metadata)
            tmp = str(type(chirp_song))
            if tmp != "<class 'ctsChirp.ChirpSong'>":
                raise ChiptuneSAKTypeError("MChirpSong init can only import ChirpSong objects")
            else:
                self.import_chirp_song(chirp_song)

    @property
    def voice_count(self):
        """
        Returns the number of voices (channels)

        :return:
        :rtype:
        """
        return len(self.voices)

    def import_chirp_song(self, chirp_song):
        """
        Imports a ChirpSong
        
        :param chirp_song: A chirp song
        :type chirp_song: ctsChirp.ChirpSong
        :raises ChiptuneSAKQuantizationError: Thrown if chirp track is not quantized
        :raises ChiptuneSAKPolyphonyError: Thrown if a single voice contains polyphony
        """
        if not chirp_song.is_quantized():
            raise ChiptuneSAKQuantizationError("ChirpSong must be quantized to create RChirp.")
        if chirp_song.is_polyphonic():
            raise ChiptuneSAKPolyphonyError("ChirpSong must not be polyphonic to create RChirp.")
        for t in chirp_song.tracks:
            self.voices.append(RChirpVoice(self, t))
        self.metadata = copy.deepcopy(chirp_song.metadata)
        self.other = copy.deepcopy(chirp_song.other)
        self.compressed = False

    def is_contiguous(self):
        """
        Determines if the voices' rows are contiguous, without gaps in time
        
        :return: True if rows are contiguous, False if not
        :rtype: boolean
        """
        return all(voice.is_contiguous() for voice in self.voices)

    def integrity_check(self):
        """
        Finds problems with voices' row data

        :return: True if integrity checks pass for all voices
        :raises AssertionError: Various integrity failure assertions possible
        """    
        return all(voice.integrity_check() for voice in self.voices)

    @property
    def jiffy_indexed_voices(self):
        """
        Returns a list of lists, where many voices hold onto many rows.  Rows indexed by jiffy number.
        
        :return: a list of lists (voices->rows)
        :rtype: list
        """
        return [voice.jiffy_indexed_rows for voice in self.voices]

    def validate_compression(self):
        if not self.compressed:
            return False
        return all(v.validate_orderlist() for v in self.voices)

    # Create CVS debug output
    def note_time_data_str(self):
        """
        Returns a comma-separated value list representation of the rchirp data
        
        :return: CSV string
        :rtype: str
        """
        def _str_with_null_handling(a_value):
            return str(a_value) if a_value is not None else ''

        max_tick = max(self.voices[i].get_last_row().jiffy_num for i in range(self.voice_count))

        channels_time_events = self.jiffy_indexed_voices

        csv_header = ["jiffy"]
        for i in range(self.voice_count):
            csv_header.append("v%d row #" % (i+1))
            csv_header.append("v%d note" % (i+1))
            csv_header.append("v%d on/off/none" % (i+1))
            csv_header.append("v%d tempo update" % (i+1))
 
        csv_rows = []
        prev_tempo = [-1] * self.voice_count
        for tick in range(max_tick+1):
            # if any channel has a entry at this tick, create a row for all channels
            if any(tick in channels_time_events[i] for i in range(self.voice_count)):
                a_csv_row = ["%d" % tick]
                for i in range(self.voice_count):
                    if tick in channels_time_events[i]:
                        event = channels_time_events[i][tick]
                        a_csv_row.append("%s" % event.row_num)
                        a_csv_row.append("%s" % _str_with_null_handling(event.note_num))
                        a_csv_row.append("%s" % _str_with_null_handling(event.gate))
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

    def convert_to_chirp(self, song_name='TODO: GET FROM METADATA INSTEAD'):
        """
        Convert rchirp song to chirp
        
        :param song_name: Name of song.  TODO: Get this from metadata instead below?
        :type song_name: str, optional
        :return: chirp conversion
        :rtype: ChirpSong
        """
        song = ctsChirp.ChirpSong()
        song.metadata.ppq = DEFAULT_MIDI_PPQN
        song.name = song_name

        channels_time_events = self.jiffy_indexed_voices
        all_ticks = sorted(set(int(t) for i in range(self.voice_count) for t in channels_time_events[i].keys()))
        note_ticks = sorted([t for t in all_ticks if any(channels_time_events[i].get(t, None) 
                        and (channels_time_events[i][t].gate is not None) for i in range(self.voice_count))])
        notes_offset = note_ticks[0]
        # TODO: Should the two "100"s be parameterized?
        ticks_per_note = reduce(math.gcd, (note_ticks[i] - notes_offset for i in range(100)))
        if ticks_per_note < 3:  # no decent gcd for this data
            ticks_per_note = 6
        notes_per_minute = 60 * 60 / ticks_per_note
        tmp = notes_per_minute // 100
        tempo = int(notes_per_minute // tmp)
        tick_factor = int(song.metadata.ppq // tempo * tmp)

        midi_tick = 0
        for it, channel_data in enumerate(channels_time_events):
            track = ctsChirp.ChirpTrack(song)
            track.name = 'Track %d' % (it + 1)
            track.channel = it
            current_note = None
            for tick in sorted(channel_data):
                midi_tick = (tick - notes_offset) * tick_factor
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
