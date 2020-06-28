import copy
import unittest
from chiptunesak import ctsMidi
from chiptunesak.constants import project_to_absolute_path

SONG_TEST_SONG = project_to_absolute_path('tests/data/twinkle.mid')


class ChirpConversionTestCase(unittest.TestCase):
    def setUp(self):
        midi = ctsMidi.MIDI()
        self.test_song = midi.to_chirp(SONG_TEST_SONG)
        self.test_song.quantize_from_note_name('16')
        self.test_song.remove_polyphony()

    def test_chirp_to_mchirp_to_chirp(self):
        """
        Test round_trip from chirp->mchirp->chirp
        """
        before_notes = self.test_song.tracks[0].notes
        mchirp_song = self.test_song.to_mchirp()
        test_chirp = mchirp_song.to_chirp()
        after_notes = test_chirp.tracks[0].notes

        n_notes = len(before_notes)
        matched_notes = sum(1 for n1, n2 in zip(before_notes, after_notes) if n1 == n2)

        # Check that all notes have the same pitch and duration
        self.assertEqual(n_notes, matched_notes)

    def test_chirp_to_rchirp_to_chirp(self):
        """
        Test round_trip from chirp->rchirp->chirp
        """
        before_notes = self.test_song.tracks[0].notes
        rchirp_song = self.test_song.to_rchirp()
        test_chirp = rchirp_song.to_chirp()
        after_notes = copy.deepcopy(test_chirp.tracks[0].notes)

        # RChirp has no concept of a quarter note, so it gives its best guess about note lengths
        ratio = before_notes[0].duration / after_notes[0].duration
        for n in after_notes:
            n.duration = int(round(n.duration * ratio))

        n_notes = len(before_notes)
        matched_notes = sum(1 for n1, n2 in zip(before_notes, after_notes) if n1 == n2)

        # Check that all notes have the same pitch and duration
        self.assertEqual(n_notes, matched_notes)
