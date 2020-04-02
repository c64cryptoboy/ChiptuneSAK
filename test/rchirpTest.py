import testingPath
import copy
import unittest
import ctsMidi
import ctsRChirp
import ctsGoatTracker
import ctsRCompress

SONG_TEST_SONG = 'data/twinkle.mid'
GT_TEST_SONG = 'data/twinkle.sng'


class RChirpSongTestCase(unittest.TestCase):
    def setUp(self):
        self.test_song = ctsMidi.import_midi_to_chirp(SONG_TEST_SONG)
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
        ctsGoatTracker.export_rchirp_to_gt(self.rchirp_song, GT_TEST_SONG)

    def test_compression(self):
        rchirp_song = copy.deepcopy(self.rchirp_song)

        #ctsRCompress.compress_gt(rchirp_song)

        test_song = ctsMidi.import_midi_to_chirp('../test/data/betrayal_q.mid')
        test_song.quantize_from_note_name('8')
        test_song.remove_polyphony()
        rchirp_song = ctsRChirp.RChirpSong(test_song)

        ctsRCompress.compress_gt(rchirp_song)

