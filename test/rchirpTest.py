import testingPath
import unittest
import ctsBase
import ctsMidi
import ctsRChirp
import ctsGoatTracker

SONG_TEST_SONG = 'data/twinkle.mid'
GT_TEST_SONG = 'data/twinkle.sng'


class RChirpSongTestCase(unittest.TestCase):
    def setUp(self):
        self.test_song = ctsMidi.midi_to_chirp(SONG_TEST_SONG)
        self.test_song.quantize(*self.test_song.estimate_quantization())
        self.rchirp_song = ctsRChirp.RChirpSong(self.test_song)

    def test_notes(self):
        for i, (t, v) in enumerate(zip(self.test_song.tracks, self.rchirp_song.voices)):
            with self.subTest(i=i):
                chirp_notes = set(n.note_num for n in t.notes)
                rchirp_notes = set(v.rows[r].note_num for r in v.rows)
                diff = chirp_notes - rchirp_notes
                self.assertTrue(len(diff) == 0)

    def test_gt(self):

        # This is a temporary test that writes out a gt .sng file to listen to.
        for v in self.rchirp_song.voices:
            v.rows[0].new_instrument = 1
        ctsGoatTracker.convert_rchirp_to_gt_file(self.rchirp_song, GT_TEST_SONG)

