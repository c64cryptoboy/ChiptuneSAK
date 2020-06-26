# Test goat tracker functionality
#
# TODOs:
# - Add an additional subtune to gtTestData.sng and create tests here for it

import unittest
from chiptunesak import ctsGoatTracker
from chiptunesak import ctsBase
from chiptunesak.ctsConstants import project_to_absolute_path
from chiptunesak.ctsBytesUtil import read_binary_file


# Description of tests/data/gtTestData.sng test data
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

SNG_TEST_FILE = project_to_absolute_path('tests/data/gtTestData.sng')

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

        self.GoatTrackerIO = ctsGoatTracker.GoatTracker()

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

    # Test that .sng binary to parsed back to sng binary is lossless
    def test_sng_to_parsed_to_sng(self):
        gt_binary2 = self.parsed_gt.export_parsed_gt_to_gt_binary()

        # write_binary_file(project_to_absolute_path('tests/data/gtTestData_deleteMe.sng'), gt_binary2)
        self.assertTrue(self.gt_binary == gt_binary2)

    # Test that .sng binary to rchirp has expected note content after conversion
    def test_sng_to_rchirp(self):
        rchirp_song = self.parsed_gt.import_parsed_gt_to_rchirp(0)

        self.assertTrue(self.found_expected_note_content(rchirp_song))

        # Now do it with the new interface
        rchirp_song = self.GoatTrackerIO.to_rchirp(SNG_TEST_FILE, subtune=0)

        self.assertTrue(self.found_expected_note_content(rchirp_song))

    def test_sng_to_rchirp_to_chirp_to_rchirp(self):
        rchirp_song = self.GoatTrackerIO.to_rchirp(SNG_TEST_FILE, subtune=0)
        self.assertTrue(self.found_expected_note_content(rchirp_song))
        chirp_song = rchirp_song.to_chirp()
        test_rchirp = chirp_song.to_rchirp()
        self.assertTrue(self.found_expected_note_content(test_rchirp))

    # Tests for consistency under transformations
    # This ASCII art chart (below) shows a sequence of 6 transformations, which will allow
    # for a number of consistency tests
    #
    #  . . . . . . . . . . . . rchirp -> . . . . . . . . . . . . . . . . . .  rchirp3
    #  . . . . . . . parsed -> . . . . . parsed2 ->  . . . . . . . parsed3 -> . . . .
    #  sng binary -> . . . . . . . . . . . . . . .  sng binary2 ->  . . . . . . . . .
    #
    #  (Yup, there's nothing named rchirp2)
    #
    def test_sng_to_rchirp_to_sng_to_rchirp(self):
        # convert parsed sng file into rchirp
        rchirp_song = self.parsed_gt.import_parsed_gt_to_rchirp()

        # convert rchirp back to a second parsed sng file
        parsed_gt2 = ctsGoatTracker.GTSong()
        parsed_gt2.export_rchirp_to_parsed_gt(rchirp_song, end_with_repeat=False, max_pattern_len=126)

        # Test that instrument data survived these conversions
        # (this is not a situation where default instruments will be auto-appended)
        self.assertTrue(self.parsed_gt.get_instruments_bytes() == parsed_gt2.get_instruments_bytes())
        self.assertTrue(self.parsed_gt.wave_table.to_bytes() == parsed_gt2.wave_table.to_bytes())
        self.assertTrue(self.parsed_gt.pulse_table.to_bytes() == parsed_gt2.pulse_table.to_bytes())
        self.assertTrue(self.parsed_gt.filter_table.to_bytes() == parsed_gt2.filter_table.to_bytes())
        self.assertTrue(self.parsed_gt.speed_table.to_bytes() == parsed_gt2.speed_table.to_bytes())

        gt_binary2 = parsed_gt2.export_parsed_gt_to_gt_binary()

        parsed_gt3 = ctsGoatTracker.GTSong()
        parsed_gt3.import_sng_binary_to_parsed_gt(gt_binary2)

        # convert second parsed sng file into a second rchirp file
        rchirp_song_2 = parsed_gt3.import_parsed_gt_to_rchirp()

        # test if the note/timing content from original file survived 6 transformations
        # (shown in ascii diagram above)
        self.assertTrue(self.found_expected_note_content(rchirp_song_2))

    # Test adding an instrument.
    # FUTURE:  Judging success only by how much each table gets extended, so more could be
    # added at some point
    def test_add_instrument(self):
        rchirp_song = self.parsed_gt.import_parsed_gt_to_rchirp()
        extensions = rchirp_song.metadata.extensions
        self.assertTrue(
            extensions["gt.wave_table"][0] == 2
            and extensions["gt.pulse_table"][0] == 0
            and extensions["gt.filter_table"][0] == 0
            and extensions["gt.speed_table"][0] == 0)

        ctsGoatTracker.add_gt_instrument_to_rchirp(rchirp_song, "SlepBass", 'tests/data/')

        self.assertTrue(
            extensions["gt.wave_table"][0] == 2 + 4    # adds 4
            and extensions["gt.pulse_table"][0] == 5   # adds 5
            and extensions["gt.filter_table"][0] == 6  # adds 6
            and extensions["gt.speed_table"][0] == 1)  # adds 1

        # Code to check out result in GoatTracker:
        # converter = ctsGoatTracker.GoatTracker()
        # converter.set_instruments(['HarpsiSolo', 'FluteVibro', 'SawtoothLegato'])
        # converter.to_file(rchirp_song, project_to_absolute_path('tests/data/deleteMe.sng'))


if __name__ == '__main__':
    # ctsTestingTools.env_to_stdout()
    unittest.main(failfast=True)  # Lots of asserts (in a loop), so stop after first fail
