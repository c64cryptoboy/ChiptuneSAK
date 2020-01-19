import sys
import copy
sys.path.append('../src/')
import hashlib
import re
import unittest
import ctsSong

class SongTestCase(unittest.TestCase):
    def setUp(self):
        self.test_song = ctsSong.Song('twinkle.mid')

    def test_total_notes(self):
        """
        Tests that the total number of notes imported is correct.
        """
        self.assertEqual(self.test_song.stats['Notes'], 143)

    def test_tracks(self):
        """
        Tests both the number and the names of extracted tracks
        """
        self.assertTupleEqual(tuple(t.name for t in  self.test_song.tracks), ('Lead', 'Counter', 'Bass'))

    def test_quantization_and_polyphony(self):
        """
        Tests the quantization and polyphony functions of the Song class.
        """
        ts = copy.deepcopy(self.test_song)
        q_n, q_d = ts.estimate_quantization()
        ts.quantize(q_n, q_d)
        ts.remove_polyphony()

        result = (not self.test_song.is_quantized() and self.test_song.is_polyphonic()
                  and ts.is_quantized() and not ts.is_polyphonic()
                  and ts.qticks_notes == 480 and ts.qticks_durations == 480)
        self.assertTrue(result)

    def test_duration_to_note_name(self):
        """
        Test conversion of durations (in ticks) to note names
        """
        ppq = self.test_song.ppq
        known_good = 'quarter eighth eighth triplet sixteenth thirty-second thirty-second triplet sixty-fourth'
        test_durations = [1, 2, 3, 4, 8, 12, 16]
        test_output = ' '.join(ctsSong.duration_to_note_name(ppq//n, ppq) for n in test_durations)

        self.assertEqual(test_output, known_good)
