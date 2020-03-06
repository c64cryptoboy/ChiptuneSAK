import copy
from ctsBase import *


@dataclass
class RChirpRow:
    """
    The basic RChirp row
    """
    note_num: int = 0
    instrument: int = 0
    gate_on: bool = False
    gate_off: bool = False


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
        ticks_per_update = (self.rchirp_song.metadata.qpm * self.rchirp_song.metadata.ppq * 60) \
                            / self.rchirp_song.update_freq

        # Insert the notes into the voice
        for n in chirp_track.notes:
            su = n.start_time / ticks_per_update
            self.rows[su].note_num = n.note_num
            self.rows[su].gate_on = True
            self.rows[su].gate_off = False  # If the gate were turned off, delete that since new note starts
            eu = (n.start_time + n.duration) / ticks_per_update
            self.rows[eu].gate_off = True

        # Now find the program changes; make a list with a default at the beginning and another default at the end
        program_changes = [ProgramEvent(0, 0)]
        for p in [m for m in chirp_track.other if m.msg.type == 'program_change']:
            program_changes.append(ProgramEvent(p.start_time, p.msg.program))
            program_changes.sort(key=lambda p: p.start_time)
            program_changes.append(ProgramEvent(BIG_NUMBER, p[-1].program))  # Happens a long time from now

        ip, current_program, next_program_tick = 0, 0, 0
        while program_changes[ip].start_time <= 0:  # Consume all the program changes that occur at tick 0
            current_program = int(program_changes[ip].program)
            next_program_tick = program_changes[ip + 1].start_time
            ip += 1

        for r in sorted(self.rows):
            tick = r * ticks_per_update
            if tick >= next_program_tick:
                while program_changes[ip] <= tick:
                    current_program = int(program_changes[ip].program)
                    next_program_tick = program_changes[ip + 1].start_time
                    ip += 1
            self.rows[r].instrument = current_program


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
