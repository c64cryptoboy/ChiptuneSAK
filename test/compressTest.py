import testingPath
import unittest
import ctsGoatTracker
import ctsGtCompress
from ctsConstants import project_to_absolute_path
import ctsRChirp
import ctsMidi

COMPRESS_TEST_SONG = project_to_absolute_path('test/data/BWV_799.mid')


class TestCompression(unittest.TestCase):
    def setUp(self):
        pass

    def test_gt_compression(self):
        self.compress_test_song = ctsMidi.MIDI().to_chirp(COMPRESS_TEST_SONG)
        self.compress_test_song.quantize_from_note_name('16')
        for i, program in enumerate([11, 10, 6]):
            self.compress_test_song.tracks[i].set_program(program)

        self.compress_test_song.remove_polyphony()
        self.compress_test_song.remove_keyswitches(12)
        rchirp_song = ctsRChirp.RChirpSong(self.compress_test_song)

        rchirp_song = ctsGtCompress.compress_gt_lr(rchirp_song, 16)

        self.assertTrue(ctsGtCompress.validate_gt_limits(rchirp_song))
        self.assertTrue(rchirp_song.validate_compression())

        ctsGtCompress.compress_gt_global(rchirp_song, 16)

        self.assertTrue(ctsGtCompress.validate_gt_limits(rchirp_song))
        self.assertTrue(rchirp_song.validate_compression())
        # ctsGoatTracker.export_rchirp_to_gt(rchirp_song, '../test/data/gt_test_out.sng')

        # Now delete a row from a pattern which should cause compressed song not to work.
        rchirp_song.patterns[0].rows.pop()
        self.assertFalse(rchirp_song.validate_compression())

        # print(f'{len(rchirp_song.patterns)} total patterns with a total of
        #     {sum(len(p.rows) for p in rchirp_song.patterns)} rows')
        #
        # print('%d total orderlist entries' % sum(len(v.orderlist) for v in rchirp_song.voices))
        # print('%d bytes estimated orderlist size' %
        #     sum(ctsGtCompress.get_gt_orderlist_length(v.orderlist) for v in rchirp_song.voices))
        # for i, v in enumerate(rchirp_song.voices):
        #     print(f'Voice {i+1}:')
        #     print(f'{len(v.orderlist)} orderlist entries')
        #     print(f'{ctsGtCompress.get_gt_orderlist_length(v.orderlist)} estimated orderlist rows')
        # print(f'{ctsGtCompress.estimate_song_size(rchirp_song)} bytes estimated song size')
        #

    # TODO: For refactoring, I need to test for runtime exceptions.
    # This in no way tests data validity, so it's just a placeholder for real testing
    def test_runtime_exceptions_only_superlame(self):

        # Convert goattracker sng to an rchirp
        rchirp_song = ctsGoatTracker.import_sng_file_to_rchirp(
            str(project_to_absolute_path('test/data/gtTestData.sng')))

        # create patterns and orderlists
        rchirp_song = ctsGtCompress.compress_gt_lr(rchirp_song)

        # convert rchirp back to goattracker sng
        parsed_gt = ctsGoatTracker.GTSong()
        parsed_gt.export_rchirp_to_parsed_gt(rchirp_song, False, 126)
        parsed_gt.export_parsed_gt_to_sng_file(project_to_absolute_path('test/data/test_out.sng'))

        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
