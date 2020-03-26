import testingPath
import unittest
import ctsTestingTools
import ctsChirp
import ctsMChirp
import ctsMidi
import ctsML64


class TestExportML64(unittest.TestCase):
    def test_ML64_output_measures(self):
        """
        Test ML64 export using "measures" mode against known good files made with our previous tools.
        """
        midi_file = 'data/jingleBellsSDG.mid'
        known_good_ml64_file = 'data/jingleBellsSDG_good.ml64'
        known_good_ml64_hash = ctsTestingTools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = ctsMidi.import_midi_to_chirp(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        m_song = ctsMChirp.MChirpSong(song)
        test_ml64 = ctsML64.export_mchirp_to_ml64(m_song)
        test_ml64_hash = ctsTestingTools.md5_hash_no_spaces(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)

        midi_file = 'data/bach_invention_4.mid'
        known_good_ml64_file = 'data/bach_invention_4_good.ml64'
        known_good_ml64_hash = ctsTestingTools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = ctsMidi.import_midi_to_chirp(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        m_song = ctsMChirp.MChirpSong(song)
        test_ml64 = ctsML64.export_mchirp_to_ml64(m_song)
        test_ml64_hash = ctsTestingTools.md5_hash_no_spaces(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)

    def test_ML64_compact_modulation(self):
        """
        Test ML64 export using "compact" mode against a known good file.
        """
        midi_file = 'data/tripletTest.mid'
        known_good_ml64_file = 'data/tripletTest_good.ml64'
        known_good_ml64_hash = ctsTestingTools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = ctsMidi.import_midi_to_chirp(midi_file)
        song.modulate(3, 2)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        test_ml64 = ctsML64.export_chirp_to_ml64(song, ml64_format='c')
        test_ml64_hash = ctsTestingTools.md5_hash_no_spaces(test_ml64)

        # with open(known_good_ml64_file, 'w') as f:
        #    f.write(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)


if __name__ == '__main__':
    unittest.main()
