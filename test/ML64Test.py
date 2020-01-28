import testingPath
import unittest
import ctsTestingTools
import ctsSong
import ctsML64


class TestExportML64(unittest.TestCase):
    def test_ML64_output_measures(self):
        """
        Test ML64 export using "measures" mode against known good files made with our previous tools.
        """
        midi_file = 'jingleBellsSDG.mid'
        known_good_ml64_file = 'jingleBellsSDG_good.ml64'
        known_good_ml64_hash = ctsTestingTools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = ctsSong.Song(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        test_ml64 = ctsML64.export_ml64(song, format='m')
        test_ml64_hash = ctsTestingTools.md5_hash_no_spaces(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)

        midi_file = 'bach_invention_4.mid'
        known_good_ml64_file = 'bach_invention_4_good.ml64'
        known_good_ml64_hash = ctsTestingTools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = ctsSong.Song(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        test_ml64 = ctsML64.export_ml64(song, format='m')
        test_ml64_hash = ctsTestingTools.md5_hash_no_spaces(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)



    def test_ML64_compact_modulation(self):
        """
        Test ML64 export using "compact" mode against a known good file.
        """
        midi_file = 'tripletTest.mid'
        known_good_ml64_file = 'tripletTest_good.ml64'
        known_good_ml64_hash = ctsTestingTools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = ctsSong.Song(midi_file)
        song.modulate(3, 2)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        test_ml64 = ctsML64.export_ml64(song, format='c')
        test_ml64_hash = ctsTestingTools.md5_hash_no_spaces(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)


if __name__ == '__main__':
    unittest.main()
