import testingPath
import os
import unittest
import subprocess
import ctsChirp
import ctsMChirp
import ctsMidi
import ctsTestingTools
import ctsLilypond

class TestExportLilypond(unittest.TestCase):
    def test_lilypond_(self):
        midi_file = 'data/bach_invention_4.mid'
        known_good_ly_file = 'data/bach_invention_4_clip_good.ly'
        known_good_ly_hash = ctsTestingTools.md5_hash_no_spaces_file(known_good_ly_file)


        song = ctsMidi.import_midi_to_chirp(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()

        m_song = ctsMChirp.MChirpSong(song)

        test_ly = ctsLilypond.export_clip_to_lilypond(m_song, m_song.tracks[0].measures[3:8])
        test_ly_hash = ctsTestingTools.md5_hash_no_spaces(test_ly)

        with open('data/test.ly', 'w') as f:
            f.write(test_ly)

        self.assertEqual(known_good_ly_hash, test_ly_hash)


