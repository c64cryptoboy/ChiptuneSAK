import unittest

from chiptunesak import testing_tools
from chiptunesak import mchirp
from chiptunesak import midi
from chiptunesak.ml64 import ML64
from chiptunesak.constants import project_to_absolute_path


class TestExportML64(unittest.TestCase):
    def test_ML64_output_measures(self):
        """
        Test ML64 export using "measures" mode against known good files made with our previous tools.
        """

        ml64 = ML64()

        midi_file = project_to_absolute_path('tests/data/jingleBellsSDG.mid')
        known_good_ml64_file = project_to_absolute_path('tests/data/jingleBellsSDG_good.ml64')
        known_good_ml64_hash = testing_tools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = midi.MIDI().to_chirp(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        m_song = mchirp.MChirpSong(song)
        test_ml64 = ml64.to_bin(m_song, format='measures')
        test_ml64_hash = testing_tools.md5_hash_no_spaces(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)

        midi_file = project_to_absolute_path('tests/data/BWV_775.mid')
        known_good_ml64_file = project_to_absolute_path('tests/data/BWV_775_good.ml64')
        known_good_ml64_hash = testing_tools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = midi.MIDI().to_chirp(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        m_song = mchirp.MChirpSong(song)
        test_ml64 = ml64.to_bin(m_song, format='measures')
        test_ml64_hash = testing_tools.md5_hash_no_spaces(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)

    def test_ML64_standard(self):
        """
        Test ML64 export using "standard" mode against a known good file.
        """
        ml64 = ML64()

        midi_file = project_to_absolute_path('tests/data/BWV_775.mid')
        known_good_ml64_file = project_to_absolute_path('tests/data/BWV_775_good_std.ml64')
        known_good_ml64_hash = testing_tools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = midi.MIDI().to_chirp(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        test_ml64 = ml64.to_bin(song, format='standard')
        test_ml64_hash = testing_tools.md5_hash_no_spaces(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)

    def test_ML64_compact_modulation(self):
        """
        Test ML64 export using "compact" mode against a known good file.
        """
        ml64 = ML64()

        midi_file = project_to_absolute_path('tests/data/tripletTest.mid')
        known_good_ml64_file = project_to_absolute_path('tests/data/tripletTest_good.ml64')
        known_good_ml64_hash = testing_tools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = midi.MIDI().to_chirp(midi_file)
        song.modulate(3, 2)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        test_ml64 = ml64.to_bin(song, format='compact')
        test_ml64_hash = testing_tools.md5_hash_no_spaces(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)


if __name__ == '__main__':
    unittest.main()
