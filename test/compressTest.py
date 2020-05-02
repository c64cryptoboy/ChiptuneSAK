import testingPath
import unittest
import ctsGoatTracker
import ctsGtCompress
from ctsConstants import project_to_absolute_path

class TestCompression(unittest.TestCase):

    # TODO: For refactoring, I need to test for runtime exceptions.
    # This in no way tests data validity, so it's just a placeholder for real testing
    def test_runtime_exceptions_only_superlame(self):

        # Convert goattracker sng to an rchirp
        rchirp_song = ctsGoatTracker.import_sng_file_to_rchirp(
            project_to_absolute_path('test/data/gtTestData.sng'))

        # create patterns and orderlists
        rchirp_song = ctsGtCompress.compress_gt_lr(rchirp_song)

        # convert rchirp back to goattracker sng
        parsed_gt = ctsGoatTracker.GTSong()
        parsed_gt.export_rchirp_to_parsed_gt(rchirp_song, False, 126)
        parsed_gt.export_parsed_gt_to_sng_file(project_to_absolute_path('test/data/test_out.sng'))

        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
