import sys
sys.path.append('../src/')
import hashlib
import re
import unittest
import ctsSong
import ctsML64

class TestExportML64(unittest.TestCase):
    def test_ML64_output_measures(self):
        midi_file = 'jingleBellsSDG.mid'
        known_good_ml64_file = 'jingleBellsSDG.ml64'
        with open(known_good_ml64_file, 'r', encoding='ascii') as f:
            lines = [l.strip() for l in f.readlines() if not l.startswith('//')]
        known_good_ml64 = re.sub('\s', '', ''.join(lines))
        known_good_ml64 = re.sub('AcousticGrandPiano', '0', known_good_ml64)

        md5 = hashlib.md5(known_good_ml64.encode('ascii', 'ignore'))
        known_good_md5 = md5.hexdigest()

        song = ctsSong.Song(midi_file)
        song.quantize(song.ppq // 4, song.ppq // 4) # Quantize to sixteenth notes
        song.eliminate_polyphony()
        test_ml64 = ctsML64.export_ML64(song, mode='m')
        test_ml64 = re.sub('\s', '', test_ml64)

        md5 = hashlib.md5(test_ml64.encode('ascii'))
        test_md5 = md5.hexdigest()

        self.assertEqual(known_good_md5, test_md5)

    def test_ML64_compact_modulation(self):
        midi_file = 'tripletTest.mid'
        known_good_ml64_file = 'tripletTest.ml64'
        with open(known_good_ml64_file, 'r', encoding='ascii') as f:
            lines = [l.strip() for l in f.readlines() if not l.startswith('//')]
        known_good_ml64 = re.sub('\s', '', ''.join(lines))

        md5 = hashlib.md5(known_good_ml64.encode('ascii', 'ignore'))
        known_good_md5 = md5.hexdigest()

        song = ctsSong.Song(midi_file)
        song.modulate(3, 2)
        song.quantize(song.ppq // 4, song.ppq // 4) # Quantize to sixteenth notes
        song.eliminate_polyphony()
        test_ml64 = ctsML64.export_ML64(song, mode='c')
        test_ml64 = re.sub('\s', '', test_ml64)

        md5 = hashlib.md5(test_ml64.encode('ascii'))
        test_md5 = md5.hexdigest()

        self.assertEqual(known_good_md5, test_md5)

if __name__ == '__main__':
    unittest.main()
