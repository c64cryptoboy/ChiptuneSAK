import sys
import copy
sys.path.append('../src/')
import unittest
import ctsMidi
import ctsChirp
from ctsKey import ChirpKey

SONG_TEST_SONG = 'data/twinkle.mid'
TRACK_TEST_SONG = 'data/BWV_799.mid'

class SongTestCase(unittest.TestCase):
    def setUp(self):
        self.test_song = ctsMidi.midi_to_chirp(SONG_TEST_SONG)

    def test_notes(self):
        """
        Tests that the total number of notes imported is correct.
        """
        self.assertEqual(self.test_song.stats['Notes'], 143)
        self.assertEqual(max(n.note_num for t in self.test_song.tracks for n in t.notes), 69)
        self.assertEqual(max(n.duration for t in self.test_song.tracks for n in t.notes), 3840)

    def test_tracks(self):
        """
        Tests both the number and the names of extracted tracks
        """
        self.assertTupleEqual(tuple(t.name for t in self.test_song.tracks), ('Lead', 'Counter', 'Bass'))

    def test_quantization_and_polyphony(self):
        """
        Tests the quantization and polyphony functions of the ChirpSong class.
        """
        self.assertFalse(self.test_song.is_quantized())
        self.assertTrue(self.test_song.is_polyphonic())

        ts = copy.deepcopy(self.test_song)
        q_n, q_d = ts.estimate_quantization()
        self.assertEqual(q_n, 480)
        self.assertEqual(q_d, 480)

        ts.quantize(q_n, q_d)
        ts.remove_polyphony()
        self.assertTrue(ts.is_quantized())
        self.assertFalse(ts.is_polyphonic())
        self.assertEqual(ts.qticks_notes, q_n)
        self.assertEqual(ts.qticks_durations, q_d)

    def test_duration_to_note_name(self):
        """
        Test conversion of durations (in ticks) to note names
        """
        ppq = self.test_song.metadata.ppq
        known_good = 'quarter, eighth, eighth triplet, sixteenth, thirty-second, thirty-second triplet, sixty-fourth'
        test_durations = [1, 2, 3, 4, 8, 12, 16]
        test_output = ', '.join(ctsChirp.duration_to_note_name(ppq // n, ppq) for n in test_durations)
        self.assertEqual(test_output, known_good)

    def test_measures(self):
        """
        Tests the measures handling
        """
        self.assertEqual(len(self.test_song.measures_and_beats()), 48)

    def test_modulation(self):
        test_song_mod = copy.deepcopy(self.test_song)
        test_song_mod.modulate(3, 2)

        self.assertEqual(test_song_mod.metadata.time_signature, (0, 12, 8))

        test_song_mod.modulate(2, 3)

        self.assertEqual(test_song_mod.metadata.time_signature, (0, 4, 4))

    def test_transposition(self):
        orig_notes = [n for t in self.test_song.tracks for n in t.notes]
        test_transpose = 7
        test_song_transposed = copy.deepcopy(self.test_song)
        test_song_transposed.transpose(test_transpose)
        test_notes = [n for t in test_song_transposed.tracks for n in t.notes]

        self.assertTrue(all(n.note_num - o.note_num == test_transpose for o, n in zip(orig_notes, test_notes)))

        orig_key_offset = self.test_song.metadata.key_signature.key.key_signature.offset
        test_key_offset = test_song_transposed.metadata.key_signature.key.key_signature.offset

        self.assertTrue((test_key_offset - orig_key_offset) % 12 == test_transpose % 12)


class TrackTestCase(unittest.TestCase):
    def setUp(self):
        self.test_song = ctsMidi.midi_to_chirp(TRACK_TEST_SONG)

    def test_quantization(self):
        for i in range(len(self.test_song.tracks)):
            with self.subTest(i=i):
                qticks = self.test_song.tracks[1].estimate_quantization()
                self.assertEqual(qticks, (120, 120))

    def test_remove_short(self):
        tmp_song = copy.deepcopy(self.test_song)

        test_duration = 120

        tmp_song.quantize(test_duration, test_duration)
        total_notes = sum(len(t.notes) for t in tmp_song.tracks)
        short_notes = sum(1 for t in tmp_song.tracks for n in t.notes if n.duration <= test_duration)
        for t in tmp_song.tracks:
            t.remove_short_notes(test_duration)

        total_notes_test = sum(len(t.notes) for t in tmp_song.tracks)
        self.assertEqual(total_notes_test + short_notes, total_notes)

    def test_set_min_note_length(self):
        tmp_song = copy.deepcopy(self.test_song)

        test_duration = 120

        tmp_song.quantize(test_duration, test_duration)
        total_notes = sum(len(t.notes) for t in tmp_song.tracks)
        short_notes = sum(1 for t in tmp_song.tracks for n in t.notes if n.duration <= test_duration)
        for t in tmp_song.tracks:
            t.set_min_note_len(test_duration * 2)

        total_notes_test = sum(len(t.notes) for t in tmp_song.tracks)
        expected_lost = short_notes // 2 #  In this piece, the short notes come in pairs
        self.assertEqual(total_notes_test + expected_lost, total_notes)
