import testingPath
import unittest
import ctsGoatTracker

"""
gtTestData.sng

Description of playback:

Patterns 0, 1, and 2 play simultaneously, giving a C major chord, then its 1st and 2nd inversions.
This is for simple testing.

Then patterns 0, 1, 2 are transposed up a half step, and this transposed playback is done twice
(R2 command).  The transpose is then removed.
This supports testing of repeats and transpositions.

Finally, patterns 7, 8, and 9 play simultaneously, giving a C major chord, then its 1st and 2nd
inversions.  However, channel one is running at tempo 24 (3 rows per note), channel two at tempo
12 (6 rows per note), and channel three at tempo 6 (12 rows per note).  Tempo * rows-per-note is
constant across all three channels, so chords play back with simultaneity.
This supports testing of related tempos across channels.
"""

class TestGtImport(unittest.TestCase):
    def test_gt_import(self):
        pass

if __name__ == '__main__':
    unittest.main()
