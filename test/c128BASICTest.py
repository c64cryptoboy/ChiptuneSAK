import testingPath  # noqa
import unittest
import ctsTestingTools
import ctsMChirp
import ctsMidi
import ctsC128Basic
import ctsConstants

TEST_FILE = ctsConstants.project_to_absolute_path('test/data/BWV_799.mid')
KNOWN_GOOD = ctsConstants.project_to_absolute_path('test/data/BWV_799_known_good.bas')


class TestC128BASIC(unittest.TestCase):
    def setUp(self):
        self.BASIC = ctsC128Basic.C128Basic()
        chirp_song = ctsMidi.MIDI().to_chirp(TEST_FILE)
        chirp_song.quantize_from_note_name('16')
        chirp_song.remove_keyswitches()
        chirp_song.remove_polyphony()
        self.mchirp_song = ctsMChirp.MChirpSong(chirp_song)

    def test_c128_basic_output_bas(self):
        known_good_basic_program_hash = ctsTestingTools.md5_hash_no_spaces_file(KNOWN_GOOD)

        basic_program = self.BASIC.to_bin(self.mchirp_song, format='bas')
        test_hash = ctsTestingTools.md5_hash_no_spaces(basic_program)

        self.assertEqual(known_good_basic_program_hash, test_hash)


if __name__ == '__main__':
    unittest.main(failfast=False)
