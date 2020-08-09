import unittest

from chiptunesak import testing_tools
from chiptunesak import mchirp
from chiptunesak import midi
from chiptunesak import c128_basic
from chiptunesak import constants

TEST_FILE = constants.project_to_absolute_path('tests/data/BWV_799.mid')
KNOWN_GOOD = constants.project_to_absolute_path('tests/data/BWV_799_known_good.bas')


class TestC128BASIC(unittest.TestCase):
    def setUp(self):
        self.BASIC = c128_basic.C128Basic()
        chirp_song = midi.MIDI().to_chirp(TEST_FILE)
        chirp_song.quantize_from_note_name('16')
        chirp_song.remove_keyswitches()
        chirp_song.remove_polyphony()
        self.mchirp_song = mchirp.MChirpSong(chirp_song)

    def test_c128_basic_output_bas(self):
        known_good_basic_program_hash = testing_tools.md5_hash_no_spaces_file(KNOWN_GOOD)

        basic_program = self.BASIC.to_bin(self.mchirp_song, format='bas')

        test_hash = testing_tools.md5_hash_no_spaces(basic_program)

        '''
        # Code needed when creating new known-good test hashes
        self.BASIC.to_file(
            self.mchirp_song,
            constants.project_to_absolute_path('tests/data/BWV_799.bas'),
            format='bas')
        self.BASIC.to_file(
            self.mchirp_song,
            constants.project_to_absolute_path('tests/data/BWV_799.prg'),
            format='prg')
        '''
        self.assertEqual(known_good_basic_program_hash, test_hash)


if __name__ == '__main__':
    unittest.main(failfast=False)
