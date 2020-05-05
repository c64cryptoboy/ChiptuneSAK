import testingPath
import unittest
import ctsTestingTools
import ctsChirp
import ctsMChirp
import ctsMidi
import ctsML64
from ctsConstants import project_to_absolute_path


class TestExportML64(unittest.TestCase):
    def test_ML64_output_measures(self):
        """
        Test ML64 export using "measures" mode against known good files made with our previous tools.
        """

        exporter = ctsML64.ML64Exporter()
        exporter.options['Format'] = 'Measures'

        midi_file = project_to_absolute_path('test/data/jingleBellsSDG.mid')
        known_good_ml64_file = project_to_absolute_path('test/data/jingleBellsSDG_good.ml64')
        known_good_ml64_hash = ctsTestingTools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = ctsMidi.import_midi_to_chirp(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        m_song = ctsMChirp.MChirpSong(song)
        test_ml64 = exporter.export_str(m_song)
        test_ml64_hash = ctsTestingTools.md5_hash_no_spaces(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)

        midi_file = project_to_absolute_path('test/data/bach_invention_4.mid')
        known_good_ml64_file = project_to_absolute_path('test/data/bach_invention_4_good.ml64')
        known_good_ml64_hash = ctsTestingTools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = ctsMidi.import_midi_to_chirp(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        m_song = ctsMChirp.MChirpSong(song)
        test_ml64 = exporter.export_str(m_song)
        test_ml64_hash = ctsTestingTools.md5_hash_no_spaces(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)

    def test_ML64_compact_modulation(self):
        """
        Test ML64 export using "compact" mode against a known good file.
        """
        exporter = ctsML64.ML64Exporter()
        exporter.options['Format'] = 'Compact'

        midi_file = project_to_absolute_path('test/data/tripletTest.mid')
        known_good_ml64_file = project_to_absolute_path('test/data/tripletTest_good.ml64')
        known_good_ml64_hash = ctsTestingTools.md5_hash_no_spaces_file(known_good_ml64_file)

        song = ctsMidi.import_midi_to_chirp(midi_file)
        song.modulate(3, 2)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()
        test_ml64 = exporter.export_str(song)
        test_ml64_hash = ctsTestingTools.md5_hash_no_spaces(test_ml64)

        # with open(known_good_ml64_file, 'w') as f:
        #    f.write(test_ml64)

        self.assertEqual(known_good_ml64_hash, test_ml64_hash)


if __name__ == '__main__':
    unittest.main()
