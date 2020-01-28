import testingPath
import os
import unittest
import subprocess
import ctsSong
import ctsExportUtil
import ctsLilypond

class TestExportLilypond(unittest.TestCase):
    def test_lilypond_(self):
        midi_file = 'bach_invention_4.mid'
        song = ctsSong.Song(midi_file)
        song.quantize_from_note_name('16')  # Quantize to sixteenth notes
        song.remove_polyphony()

        measures = ctsExportUtil.get_measures(song)

        ly = ctsLilypond.clip_to_lilypond(song, measures[0][3:5])
        out_filename = os.path.splitext(os.path.split(midi_file)[1])[0] + '.ly'
        with open(out_filename, 'w') as f:
            f.write(ly)

        subprocess.call('lilypond -ddelete-intermediate-files -dbackend=eps -dresolution=600 --png %s' % out_filename, shell=True)


