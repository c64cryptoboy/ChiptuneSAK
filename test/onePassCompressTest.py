import testingPath
import unittest
import ctsGoatTracker
import ctsOnePassCompress
from ctsConstants import project_to_absolute_path
import ctsRChirp
import ctsMidi

COMPRESS_TEST_SONG = project_to_absolute_path('test/data/BWV_799.mid')


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
        compressor.options['min_length'] = 32
        rchirp_song = compressor.compress(rchirp_song)

        # TODO: add test for pattern lengths to see that it obeyed limit
        self.assertTrue(ctsOnePassCompress.validate_gt_limits(rchirp_song))
        self.assertTrue(rchirp_song.validate_compression())

        compressor = ctsOnePassCompress.OnePassGlobal()
        compressor.options['min_length'] = 8
        compressor.disable_transposition()
        rchirp_song = compressor.compress(rchirp_song)

        ctsGoatTracker.export_rchirp_to_sng_file('../test/data/gt_test_out.sng', rchirp_song)

        self.assertTrue(ctsOnePassCompress.validate_gt_limits(rchirp_song))
        self.assertTrue(rchirp_song.validate_compression())

        # Now delete a row from a pattern which should cause compressed song not to work.
        rchirp_song.patterns[0].rows.pop()
        self.assertFalse(rchirp_song.validate_compression())

    # This in no way tests data validity, so it's just a placeholder for real testing
    def test_runtime_exceptions_only_superlame(self):

        # Convert goattracker sng to an rchirp
        rchirp_song = ctsGoatTracker.import_sng_file_to_rchirp(
            str(project_to_absolute_path('test/data/gtTestData.sng')))

        # create patterns and orderlists
        compressor = ctsOnePassCompress.OnePassLeftToRight()
        rchirp_song = compressor.compress(rchirp_song)

        # convert rchirp back to goattracker sng
        parsed_gt = ctsGoatTracker.GTSong()
        parsed_gt.export_rchirp_to_parsed_gt(rchirp_song, False, 126)
        parsed_gt.export_parsed_gt_to_sng_file(project_to_absolute_path('test/data/test_out.sng'))

        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
