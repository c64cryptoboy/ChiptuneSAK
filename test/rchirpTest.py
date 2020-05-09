import testingPath
import copy
import unittest
import ctsMidi
import ctsRChirp
import ctsGoatTracker
from ctsConstants import project_to_absolute_path


SONG_TEST_SONG = project_to_absolute_path('test/data/twinkle.mid')
GT_TEST_SONG = project_to_absolute_path('test/data/twinkle.sng')


class RChirpSongTestCase(unittest.TestCase):
    def setUp(self):
        self.test_song = ctsMidi.MIDI().to_chirp(SONG_TEST_SONG)
        self.test_song.quantize(*self.test_song.estimate_quantization())
        self.rchirp_song = ctsRChirp.RChirpSong(self.test_song)

    def test_notes(self):
        for i, (t, v) in enumerate(zip(self.test_song.tracks, self.rchirp_song.voices)):
            with self.subTest(i=i):
                chirp_notes = set(n.note_num for n in t.notes)
                rchirp_notes = set(v.rows[r].note_num for r in v.rows)
                diff = chirp_notes - rchirp_notes
                self.assertTrue(len(diff) == 0)
