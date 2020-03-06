import copy
from ctsBase import *


@dataclass
class RChirpRow:
    """
    The basic RChirp row
    """
    note_num: int = 0       # MIDI note number
    instrument: int = None  # Instrument number; none means no change
    gate: bool = None       # Gate on/off tri-value True/False/None
    jiffies: int = 1        # Jiffies to process this row (until next row)


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
        self.rows = collections.defaultdict(RChirpRow)
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

    def _find_closest_row_after(self, row):
        for r in sorted(self.rows):
            if r >= row:
                return r
        return r

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

        # Insert the notes into the voice
        for n in chirp_track.notes:
            n_row = n.start_time // ticks_per_row
            self.rows[n_row].note_num = n.note_num
            self.rows[n_row].gate = True
            self.rows[n_row].jiffies = jiffies_per_row
            e_row = (n.start_time + n.duration) / ticks_per_row
            self.rows[e_row].gate = False

        program_changes = [ProgramEvent(e.start_time, e.program) for e in chirp_track.other
                           if e.msg.type == 'program_change']

        for p in sorted(program_changes):
            n_row = self._find_closest_row_after(p.start_time / ticks_per_row)
            self.rows[n_row].instrument = int(p.program)


class RChirpSong:
    """
    The representation of an RChirp song.  Contains voices, voice groups, and metadata.
    """

    def __init__(self, chirp_song=None):
        self.update_freq = ARCH['NTSC'].frame_rate
        self.voices = []
        self.voice_groups = []
        self.stats = {}
        self.metadata = copy.deepcopy(chirp_song.metadata)
        if chirp_song is not None:
            tmp = str(type(chirp_song))
            if tmp != "<class 'ctsChirp.ChirpSong'>":
                raise ChiptuneSAKTypeError("MChirpSong init can only import ChirpSong objects")
            else:
                self.import_chirp_song(chirp_song)

    def import_chirp_song(self, chirp_song):
        """
        Imports a ChirpSong

            :param song: A ctsChirp.ChirpSong song
        """
        if not chirp_song.is_quantized():
            raise ChiptuneSAKQuantizationError("ChirpSong must be quantized to create RChirp.")
        if chirp_song.is_polyphonic():
            raise ChiptuneSAKPolyphonyError("ChirpSong must not be polyphonic to create RChirp.")
        for t in chirp_song.tracks:
            self.voices.append(RChirpVoice(self, t))
        self.metadata = copy.deepcopy(chirp_song.metadata)
        self.other = copy.deepcopy(chirp_song.other)
