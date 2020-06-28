import unittest

from chiptunesak import ctsMChirp
from chiptunesak import ctsMidi
from chiptunesak import ctsTestingTools
from chiptunesak import ctsLilypond
from chiptunesak.constants import project_to_absolute_path

MIDI_TEST_FILE = project_to_absolute_path('tests/data/bach_invention_4.mid')
KNOWN_GOOD_LY_FILE_CLIP = project_to_absolute_path('tests/data/bach_invention_4_clip_good.ly')
TEST_LY_FILE_CLIP = project_to_absolute_path('tests/data/test_bach_invention_4_clip_good.ly')


class TestExportLilypond(unittest.TestCase):
    def test_lilypond_(self):
        known_good_ly_hash = ctsTestingTools.md5_hash_no_spaces_file(KNOWN_GOOD_LY_FILE_CLIP)

        song = ctsMidi.MIDI().to_chirp(MIDI_TEST_FILE)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()

        m_song = ctsMChirp.MChirpSong(song)

        lilypond = ctsLilypond.Lilypond()

        lilypond.set_options(format='clip', measures=m_song.tracks[0].measures[3:8])
        # lilypond.to_file(m_song, TEST_LY_FILE_CLIP)
        test_ly = lilypond.to_bin(m_song)
        test_ly_hash = ctsTestingTools.md5_hash_no_spaces(test_ly)

        self.assertEqual(known_good_ly_hash, test_ly_hash)