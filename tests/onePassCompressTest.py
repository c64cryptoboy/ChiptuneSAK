import unittest

from chiptunesak import ctsGoatTracker
from chiptunesak import ctsOnePassCompress
from chiptunesak import constants
from chiptunesak import ctsRChirp
from chiptunesak import ctsMidi

COMPRESS_TEST_SONG = constants.project_to_absolute_path('tests/data/BWV_799.mid')
GT_TEST_DATA_SNG = constants.project_to_absolute_path('tests/data/gtTestData.sng')
GT_TEST_OUT_SNG = constants.project_to_absolute_path('tests/data/gt_test_out.sng')

class TestCompression(unittest.TestCase):
    def setUp(self):
        pass

    def test_one_pass_compression(self):
        self.compress_test_song = ctsMidi.MIDI().to_chirp(COMPRESS_TEST_SONG)
        self.compress_test_song.quantize_from_note_name('16')
        for i, program in enumerate([11, 10, 6]):
            self.compress_test_song.tracks[i].set_program(program)

        self.compress_test_song.remove_polyphony()
        self.compress_test_song.remove_keyswitches(12)
        rchirp_song = ctsRChirp.RChirpSong(self.compress_test_song)

        compressor = ctsOnePassCompress.OnePassLeftToRight()
        rchirp_song = compressor.compress(rchirp_song, min_length=32)

        # TODO: add test for pattern lengths to see that it obeyed limit
        self.assertTrue(ctsOnePassCompress.validate_gt_limits(rchirp_song))
        self.assertTrue(rchirp_song.validate_compression())

        compressor = ctsOnePassCompress.OnePassGlobal()
        compressor.disable_transposition()
        rchirp_song = compressor.compress(rchirp_song, min_length=8)

        exporter = ctsGoatTracker.GoatTracker()
        exporter.to_file(rchirp_song, GT_TEST_OUT_SNG)

        self.assertTrue(ctsOnePassCompress.validate_gt_limits(rchirp_song))
        self.assertTrue(rchirp_song.validate_compression())

        # Now delete a row from a pattern which should cause compressed song not to work.
        rchirp_song.patterns[0].rows.pop()
        self.assertFalse(rchirp_song.validate_compression())

    # This in no way tests data validity, so it's just a placeholder for real testing
    def test_runtime_exceptions_only_superlame(self):

        gt_io = ctsGoatTracker.GoatTracker()

        # Convert goattracker sng to an rchirp
        rchirp_song = gt_io.to_rchirp(str(GT_TEST_DATA_SNG))

        # create patterns and orderlists
        compressor = ctsOnePassCompress.OnePassLeftToRight()
        rchirp_song = compressor.compress(rchirp_song)

        # convert rchirp back to goattracker sng
        # sng = gt_io.to_bin(rchirp_song)  # flake8 this this is unused
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
