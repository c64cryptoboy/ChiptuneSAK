# test goat tracker functionality (including parsing and conversion to chirp)
#
# TODOs:
# - Add an additional subtune to gtTestData.sng and create tests here for it


import testingPath
import unittest
import ctsGoatTracker
import ctsTestingTools
import ctsBase


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

        """
        # Generate ground truth data for this test (comment out later, but keep it around)
        print("channels = []")
        for i, channel in enumerate(channels_time_events):
            channel_note_on_events = []
            for frame, event in channel.items():
                if event.note_on:
                    midi_note_name = ctsBase.pitch_to_note_name(event.note, ctsGoatTracker.GT_OCTAVE_BASE)
                    channel_note_on_events.append('(%d, "%s")' % (frame, midi_note_name))
            line = "channels.append((%s))" % (', '.join(channel_note_on_events))
            print(line)
        """

    channels = []
    channels.append(((0, "G4"), (72, "C5"), (144, "E5"), (216, "G#4"), (288, "C#5"), (360, "F5"), (432, "G#4"), \
        (504, "C#5"), (576, "F5"), (648, "G4"), (720, "C5"), (792, "E5")))
    channels.append(((0, "E4"), (72, "G4"), (144, "C5"), (216, "F4"), (288, "G#4"), (360, "C#5"), (432, "F4"), \
        (504, "G#4"), (576, "C#5"), (648, "E4"), (720, "G4"), (792, "C5")))
    channels.append(((0, "C4"), (72, "E4"), (144, "G4"), (216, "C#4"), (288, "F4"), (360, "G#4"), (432, "C#4"), \
        (504, "F4"), (576, "G#4"), (648, "C4"), (720, "E4"), (792, "G4")))        


if __name__ == '__main__':
    ctsTestingTools.env_to_stdout()
    unittest.main()
