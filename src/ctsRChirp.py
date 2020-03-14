import copy
from ctsBase import *

@dataclass
class RChirpRow:
    """
    The basic RChirp row
    """
    row_num: int = 0        # rchirp row number
    jiffy_num: int = 0      # jiffy num since time 0
    note_num: int = None    # MIDI note number;None means no note asserted
    instrument: int = None  # Instrument number; none means no change
    gate: bool = None       # Gate on/off tri-value True/False/None; None means no gate change
    jiffy_len: int = 1      # Jiffies to process this row (until next row)

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

    