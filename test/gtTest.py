# test goat tracker functionality (including parsing and conversion to chirp)
#
# TODOs:
# - Add an additional subtune to gtTestData.sng and create tests here for it


import testingPath
import unittest
import ctsGoatTracker
import ctsTestingTools


class TestGoatTrackerFunctions(unittest.TestCase):
    def test_sng_parsing(self):
        # TODO: I'm fighting environment again...
        sng_in_file = './test/gtTestData.sng'
        #sng_in_file = 'gtTestData.sng'

        # parse all subtunes
        sng_data = ctsGoatTracker.import_sng(sng_in_file)
        # get channel time events for subtune 0
        channels_time_events = ctsGoatTracker.convert_to_note_events(sng_data, 0)

        """
        Description of gtTestData.sng subtune 0 playback

        Patterns 0, 1, and 2 play simultaneously, giving a C major chord, then its 1st and 2nd inversions.
        This is for simple testing.

        Then patterns 0, 1, 2 are transposed up a half step, and this transposed playback is done twice
        (R2 command).  The transpose is then removed.
        This supports testing of repeats and transpositions.

        Finally, patterns 7, 8, and 9 play simultaneously, giving a C major chord, then its 1st and 2nd
        inversions.  However, channel one is running at tempo 24 (3 rows per note), channel two at tempo
        12 (6 rows per note), and channel three at tempo 6 (12 rows per note).  Tempo * rows-per-note is
        constant across all three channels, so the channels play back with (chord) simultaneity.
        This supports testing of related tempos across channels.
        """

        # TODO: Write parsing tests on channels_time_events

        pass

if __name__ == '__main__':
    ctsTestingTools.env_to_stdout()
    unittest.main()