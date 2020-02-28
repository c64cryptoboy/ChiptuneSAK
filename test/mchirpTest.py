import sys
import copy
import testingPath
import unittest
import ctsMidi
from ctsBase import *
from ctsMChirp import MChirpSong, MChirpTrack
from ctsChirp import ChirpSong, ChirpTrack


class SongTestCase(unittest.TestCase):
    def setUp(self):
        self.test_song = ctsMidi.midi_to_chirp('data/bach_invention_4.mid')
        self.test_song.quantize_from_note_name('16')
        self.test_song.remove_polyphony()
        self.test_mchirp_song = MChirpSong(self.test_song)

    def test_tracks(self):
        """
        Tests both the number and the names of extracted tracks
        """
        self.assertTupleEqual(tuple(t.name for t in self.test_mchirp_song.tracks), ('I', 'II'))

    def test_measures(self):
        """
        Tests the measures handling
        """
        # There should be 36 measures:  12 per track x 3 tracks
        self.assertEqual(sum(len(t.measures) for t in self.test_mchirp_song.tracks), 104)

        #  Test that the sum of note and rest durations in every measure is equal to the measure duration.
        for t in self.test_mchirp_song.tracks:
            for m in t.measures:
                s = sum(n.duration for n in m.get_notes())
                r = sum(r.duration for r in m.get_rests())
                self.assertEqual(s+r, m.duration)

    def test_conversion(self):
        """
        Tests midi-chirp-mchirp-chirp-midi pipeline.
        """
        chirp_song = ChirpSong(self.test_mchirp_song)

        # Used to generate output midi file to check that they sound the same.
        # ctsMidi.chirp_to_midi(chirp_song, 'MChirp_test.mid')

        self.assertEqual(len(chirp_song.tracks), len(self.test_song.tracks))
        self.assertEqual([t.name for t in chirp_song.tracks], [t.name for t in self.test_song.tracks])
        self.assertEqual(chirp_song.metadata, self.test_song.metadata)

        test_total_notes = sum(1 for t in self.test_song.tracks for n in t.notes)
        chirp_total_notes = sum(1 for t in chirp_song.tracks for n in t.notes)
        self.assertEqual(test_total_notes, chirp_total_notes)

    def test_triplets(self):
        test_song = ctsMidi.midi_to_chirp('data/tripletTest.mid')
        estimated_q = test_song.estimate_quantization()
        test_song.quantize(*estimated_q)
        test_song.remove_polyphony()

        test_mchirp = MChirpSong(test_song)
        total_triplets = sum(1 for t in test_mchirp.tracks for m in t.measures
                             for e in m.events if isinstance(e, Triplet))
        self.assertEqual(total_triplets, 21)

        #tmp_song = ChirpSong(test_mchirp)
        #ctsMidi.chirp_to_midi(tmp_song, 'data/tripletTestConversion.mid')
