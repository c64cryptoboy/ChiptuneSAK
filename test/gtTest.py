# Test goat tracker functionality
#
# TODOs:
# - Add an additional subtune to gtTestData.sng and create tests here for it

import testingPath
import unittest
import ctsGoatTracker
import ctsBase
import ctsRChirp
import collections
from ctsConstants import project_to_absolute_path
from ctsBytesUtil import read_binary_file, write_binary_file


# Description of test/data/gtTestData.sng test data
#
# Patterns 0, 1, and 2 play simultaneously, giving a C major chord, then its 1st and 2nd inversions.
# This is for simple testing.
#
# Then patterns 0, 1, 2 are transposed up a half step, and this transposed playback is done twice
# (R2 command).  The transpose is then removed.
# This supports testing of repeats and transpositions.
#
# Finally, patterns 7, 8, and 9 play simultaneously, giving a C major chord, then its 1st and 2nd
# inversions.  However, channel one is running at tempo 24 (3 rows per note), channel two at tempo
# 12 (6 rows per note), and channel three at tempo 6 (12 rows per note).  Tempo * rows-per-note is
# constant across all three channels, so the channels play back with (chord) simultaneity.
# This supports testing of related tempos across channels.

SNG_TEST_FILE = project_to_absolute_path('test/data/gtTestData.sng')

# Keep this generating code around (commented out)
# print("self.expected_channels = (")
# for voice in self.rchirp_song.voices:
#     channel_note_on_events = []
#     for rchirp_row in voice.sorted_rows():
#         if rchirp_row.gate:
#             midi_note_name = ctsBase.pitch_to_note_name(rchirp_row.note_num)
#             channel_note_on_events.append('(%d, "%s")' % (rchirp_row.jiffy_num, midi_note_name))
#     line = '    (' + ', '.join(channel_note_on_events) + '),'
#     print(line)
# print(')')

EXPECTED_CHANNELS = (
    ((0, "G4"), (72, "C5"), (144, "E5"), (216, "G#4"), (288, "C#5"), (360, "F5"),
        (432, "G#4"), (504, "C#5"), (576, "F5"), (648, "G4"), (720, "C5"), (792, "E5")),
    ((0, "E4"), (72, "G4"), (144, "C5"), (216, "F4"), (288, "G#4"), (360, "C#5"),
        (432, "F4"), (504, "G#4"), (576, "C#5"), (648, "E4"), (720, "G4"), (792, "C5")),
    ((0, "C4"), (72, "E4"), (144, "G4"), (216, "C#4"), (288, "F4"), (360, "G#4"),
        (432, "C#4"), (504, "F4"), (576, "G#4"), (648, "C4"), (720, "E4"), (792, "G4"))
)


class TestGoatTrackerFunctions(unittest.TestCase):
    def setUp(self):
        self.gt_binary = read_binary_file(SNG_TEST_FILE)
        self.parsed_gt = ctsGoatTracker.GTSong()
        self.parsed_gt.import_sng_binary_to_parsed_gt(self.gt_binary)


    def found_expected_note_content(self, rchirp_song):
        """
        Compare actual note content to expected note content
        :param rchirp_song: rchirp song
        :type rchirp_song: ctsRChirp.RChirpSong
        :return: True on success
        :rtype: bool
        """
        for i, expected_channel in enumerate(EXPECTED_CHANNELS):
            with self.subTest(i=i):
                actual_channel = {v.jiffy_num: v for k, v in rchirp_song.voices[i].rows.items()}
                for expected_jiffy, expected_note in expected_channel:
                    rchirp_row = actual_channel[expected_jiffy]
                    self.assertIsNotNone(rchirp_row, "Null Row in channel %d" % i)
                    actual_note = ctsBase.pitch_to_note_name(rchirp_row.note_num)  # do enharmonic comparison
                    self.assertEqual(actual_note, expected_note)
        return True


    # Test that .sng file to GTSong back to .sng file binary is lossless
    def test_sng_to_parsed_to_sng(self):
        gt_binary2 = self.parsed_gt.export_parsed_gt_to_gt_binary()

        #write_binary_file(project_to_absolute_path('test/data/gtTestData_deleteMe.sng'), gt_binary2)
        self.assertTrue(self.gt_binary == gt_binary2)


    # @unittest.skip("GT import testing not working now...")
    # Test that .sng file to rchirp has expected note content
    def test_sng_to_rchirp(self):
        rchirp_song = ctsGoatTracker.import_parsed_gt_to_rchirp(self.parsed_gt, 0)

        self.assertTrue(self.found_expected_note_content(rchirp_song))

        # Uncomment out to make the gt sng file for playback:
        # ctsGoatTracker.export_rchirp_to_gt('test/data/deleteme.sng', \
        #    rchirp_song, end_with_repeat = False, compress = False, pattern_len = 126)

    # Test that .sng file to rchirp back to .sng binary to rchirp has expected note content
    def test_sng_to_rchirp_to_sng_to_rchirp(self):
        rchirp_song = ctsGoatTracker.import_parsed_gt_to_rchirp(self.parsed_gt, 0)

        gt_binary2 = ctsGoatTracker.export_rchirp_to_gt_binary(rchirp_song,
            end_with_repeat=False, pattern_len=126)
        parsed_gt_2 = ctsGoatTracker.GTSong()
        parsed_gt_2.import_sng_binary_to_parsed_gt(gt_binary2)
        rchirp_song_2 = ctsGoatTracker.import_parsed_gt_to_rchirp(parsed_gt_2, 0)

        self.assertTrue(self.found_expected_note_content(rchirp_song_2))


if __name__ == '__main__':
    # ctsTestingTools.env_to_stdout()
    unittest.main(failfast=True)  # Lots of asserts (in a loop), so stop after first fail
