# Test goat tracker functionality (including parsing and conversion to chirp)
#
# TODOs:
# - Add an additional subtune to gtTestData.sng and create tests here for it

import testingPath
import unittest
import ctsGoatTracker
import ctsTestingTools
import ctsBase

class TestGoatTrackerFunctions(unittest.TestCase):
    
    #@unittest.skip("GT import testing not working now...")
    
    def test_sng_to_rchirp_to_sng(self):

        # First, test sng -> rchirp

        # TODO: I'm fighting environment again...
        # sng_in_file = 'test/data/gtTestData.sng'
        sng_in_file = 'data/gtTestData.sng'

        # parse all subtunes
        parsed_gt = ctsGoatTracker.import_sng(sng_in_file)
        # get rchirp for subtune 0
        rchirp_song = ctsGoatTracker.convert_parsed_gt_to_rchirp(parsed_gt, 0)

        """
        # Generate expected output data for this test (comment out later, but keep it around)
        print("expected_channels = []")
        for channel in rchirp_song.voices:
            channel = channel.rows
            channel_note_on_events = []
            for rchirp_row in channel.values():
                if rchirp_row.gate:
                    midi_note_name = ctsBase.pitch_to_note_name(rchirp_row.note_num)
                    channel_note_on_events.append('(%d, "%s")' % (rchirp_row.jiffy_num, midi_note_name))
            line = "expected_channels.append((%s))" % (', '.join(channel_note_on_events))
            print(line)
        """
        
        expected_channels = []
        expected_channels.append(((0, "G4"), (72, "C5"), (144, "E5"), (216, "G#4"), (288, "C#5"), (360, "F5"), \
            (432, "G#4"), (504, "C#5"), (576, "F5"), (648, "G4"), (720, "C5"), (792, "E5")))
        expected_channels.append(((0, "E4"), (72, "G4"), (144, "C5"), (216, "F4"), (288, "G#4"), (360, "C#5"), \
            (432, "F4"), (504, "G#4"), (576, "C#5"), (648, "E4"), (720, "G4"), (792, "C5")))
        expected_channels.append(((0, "C4"), (72, "E4"), (144, "G4"), (216, "C#4"), (288, "F4"), (360, "G#4"), \
            (432, "C#4"), (504, "F4"), (576, "G#4"), (648, "C4"), (720, "E4"), (792, "G4")))        

        # Description of gtTestData.sng subtune 0 playback
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

        for i, expected_channel in enumerate(expected_channels):
            actual_channel = rchirp_song.voices[i].get_jiffy_indexed_rows()
            for expected_jiffy, expected_note in expected_channel:
                rchirp_row = actual_channel[expected_jiffy]
                self.assertIsNotNone(rchirp_row) # Make sure there's an actual entry at that expected jiffy
                actual_note = ctsBase.pitch_to_note_name(rchirp_row.note_num) # do enharmonic comparison              
                self.assertEqual(actual_note, expected_note)

        # Second, test rchirp -> sng        
#        gt_binary = ctsGoatTracker.convert_rchirp_to_gt_binary(rchirp_song, arch='NTSC', \
#            end_with_repeat = False, compress = False, pattern_len = 126)

        gt_binary = ctsGoatTracker.convert_rchirp_to_gt_file('test/data/deleteme.sng', \
            rchirp_song, arch='NTSC', end_with_repeat = False, compress = False, pattern_len = 126)

if __name__ == '__main__':
    #ctsTestingTools.env_to_stdout()
    unittest.main(failfast=True) # Lots of asserts (in a loop), so stop after first fail
