import testingPath
import os
import unittest
import subprocess
import ctsChirp
import ctsMeasures
import ctsTestingTools
import ctsLilypond

class TestExportLilypond(unittest.TestCase):
    def test_lilypond_(self):
        midi_file = 'bach_invention_4.mid'
        known_good_ly_file = 'bach_invention_4_clip_good.ly'
        known_good_ly_hash = ctsTestingTools.md5_hash_no_spaces_file(known_good_ly_file)


        song = ctsChirp.ChirpSong(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()

        measures = ctsMeasures.get_measures(song)

        test_ly = ctsLilypond.clip_to_lilypond(song, measures[0][3:5])
        test_ly_hash = ctsTestingTools.md5_hash_no_spaces(test_ly)

        self.assertEqual(known_good_ly_hash, test_ly_hash)


