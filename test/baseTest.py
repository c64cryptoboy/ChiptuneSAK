import testingPath
import unittest
from ctsConstants import *
from ctsBase import *

class BaseTestCase(unittest.TestCase):
    def test_note_name_to_midi_note(self):
        last_note = 11
        for octave in range(8):
            for p in PITCHES:
                note_name = "%s%d" % (p, octave)
                note_num = note_name_to_pitch(note_name)
                self.assertEqual(note_num, last_note + 1)
                last_note = note_num
        self.assertEqual(note_name_to_pitch('C4'), 60)

        self.assertEqual(note_name_to_pitch('C#4'), note_name_to_pitch('C4') + 1)
        self.assertEqual(note_name_to_pitch('C##4'), note_name_to_pitch('D4'))
        self.assertEqual(note_name_to_pitch('Eb4'), note_name_to_pitch('E4') - 1)
        self.assertEqual(note_name_to_pitch('C##4'), note_name_to_pitch('Ebb4'))

    def test_architecture(self):
        self.assertEqual(round(ARCH['PAL'].frame_rate, 2), 50.12)
        self.assertEqual(round(ARCH['NTSC'].ms_per_frame, 2), 16.72)
        self.assertEqual(ARCH['NTSC-R56A'].cycles_per_frame, 16768)

    def test_duration_names(self):
        self.assertEqual(DURATIONS['US'][DURATION_STR['4.']], 'dotted quarter')
        self.assertEqual(DURATIONS['UK'][DURATION_STR['32']], 'demisemiquaver')
