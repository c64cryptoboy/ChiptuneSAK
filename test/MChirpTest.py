import sys
import copy
sys.path.append('../src/')
import unittest
import ctsMidi
import ctsMChirp

class SongTestCase(unittest.TestCase):
    def setUp(self):
        self.test_song = ctsMidi.midi_to_chirp('twinkle.mid')
        self.test_song.quantize()
        self.test_song.remove_polyphony()
        self.test_mchirp_song = ctsMChirp.MChirpSong(self.test_song)

    def test_tracks(self):
        """
        Tests both the number and the names of extracted tracks
        """
        self.assertTupleEqual(tuple(t.name for t in self.test_mchirp_song.tracks), ('Lead', 'Counter', 'Bass'))

    def test_measures(self):
        """
        Tests the measures handling
        """
        # There should be 36 measures:  12 per track x 3 tracks
        self.assertEqual(sum(len(t.measures) for t in self.test_mchirp_song.tracks), 36)

        #  Test that the sum of note and rest durations in every measure is equal to the measure duration.
        for t in self.test_mchirp_song.tracks:
            for m in t.measures:
                s = sum(n.duration for n in m.get_notes())
                r = sum(r.duration for r in m.get_rests())
                self.assertEqual(s+r, m.duration)