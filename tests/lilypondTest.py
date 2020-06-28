import unittest

from chiptunesak import mchirp
from chiptunesak import midi
from chiptunesak import testing_tools
from chiptunesak.lilypond import Lilypond
from chiptunesak.constants import project_to_absolute_path

MIDI_TEST_FILE = project_to_absolute_path('tests/data/bach_invention_4.mid')
KNOWN_GOOD_LY_FILE_CLIP = project_to_absolute_path('tests/data/bach_invention_4_clip_good.ly')
TEST_LY_FILE_CLIP = project_to_absolute_path('tests/data/test_bach_invention_4_clip_good.ly')


class TestExportLilypond(unittest.TestCase):
    def test_lilypond_(self):
        known_good_ly_hash = testing_tools.md5_hash_no_spaces_file(KNOWN_GOOD_LY_FILE_CLIP)

        song = midi.MIDI().to_chirp(MIDI_TEST_FILE)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()

        m_song = mchirp.MChirpSong(song)

        lilypond = Lilypond()

        lilypond.set_options(format='clip', measures=m_song.tracks[0].measures[3:8])
        # lilypond.to_file(m_song, TEST_LY_FILE_CLIP)
        test_ly = lilypond.to_bin(m_song)
        test_ly_hash = testing_tools.md5_hash_no_spaces(test_ly)

        self.assertEqual(known_good_ly_hash, test_ly_hash)
