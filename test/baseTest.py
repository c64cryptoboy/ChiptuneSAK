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
        self.assertEqual(round(ARCH['PAL-C64'].frame_rate, 2), 50.12)
        self.assertEqual(round(ARCH['NTSC-C64'].ms_per_frame, 2), 16.72)
        self.assertEqual(ARCH['NTSC-R56A'].cycles_per_frame, 16768)

    def test_duration_names(self):
        self.assertEqual(DURATIONS['US'][DURATION_STR['4.']], 'dotted quarter')
        self.assertEqual(DURATIONS['UK'][DURATION_STR['32']], 'demisemiquaver')

    def test_octave_offsets(self):
        octave_offset = 0
        self.assertEqual('G4', pitch_to_note_name(67, octave_offset))
        self.assertEqual(67, note_name_to_pitch('G4', octave_offset))

        octave_offset = -1  # down one octave
        self.assertEqual('G3', pitch_to_note_name(67, octave_offset))
        self.assertEqual(67, note_name_to_pitch('G3', octave_offset))

        octave_offset = 1  # up one octave
        self.assertEqual('G5', pitch_to_note_name(67, octave_offset))
        self.assertEqual(67, note_name_to_pitch('G5', octave_offset))
