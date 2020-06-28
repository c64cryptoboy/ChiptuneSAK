import unittest

from chiptunesak import constants
from chiptunesak.base import note_name_to_pitch, pitch_to_note_name


class BaseTestCase(unittest.TestCase):
    def test_note_name_to_midi_note(self):
        last_note = 11
        for octave in range(8):
            for p in constants.PITCHES:
                note_name = "%s%d" % (p, octave)
                note_num = note_name_to_pitch(note_name)
                self.assertEqual(note_num, last_note + 1)
                last_note = note_num
        self.assertEqual(note_name_to_pitch('C4'), 60)
        self.assertEqual(note_name_to_pitch('C-1'), 0)

        self.assertEqual(note_name_to_pitch('C#4'), note_name_to_pitch('C4') + 1)
        self.assertEqual(note_name_to_pitch('C##4'), note_name_to_pitch('D4'))
        self.assertEqual(note_name_to_pitch('Eb4'), note_name_to_pitch('E4') - 1)
        self.assertEqual(note_name_to_pitch('C##4'), note_name_to_pitch('Ebb4'))

    def test_architecture(self):
        self.assertEqual(round(constants.ARCH['PAL-C64'].frame_rate, 2), 50.12)
        self.assertEqual(round(constants.ARCH['NTSC-C64'].ms_per_frame, 2), 16.72)
        self.assertEqual(constants.ARCH['NTSC-R56A'].cycles_per_frame, 16768)

    def test_duration_names(self):
        self.assertEqual(constants.DURATIONS['US'][constants.DURATION_STR['4.']], 'dotted quarter')
        self.assertEqual(constants.DURATIONS['UK'][constants.DURATION_STR['32']], 'demisemiquaver')

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

    def test_freq_conversion(self):
        self.assertEqual(constants.freq_to_midi_num(440.), (constants.A4_MIDI_NUM, 0))
        # Make a tone exactly 12 cents higher than C4
        f = 261.63 * 2**(1 / 100)
        self.assertEqual(constants.freq_to_midi_num(f), (constants.C4_MIDI_NUM, 12))

        midi_note = note_name_to_pitch('C0')
        self.assertAlmostEqual(constants.midi_num_to_freq(midi_note), 16.352, 3)
        self.assertEqual(constants.midi_num_to_freq_arch(midi_note, arch='NTSC-C64'), 268)
        self.assertEqual(constants.midi_num_to_freq_arch(midi_note, arch='PAL-C64'), 278)
        self.assertEqual(constants.freq_arch_to_midi_num(268, arch='NTSC-C64')[0], midi_note)
        self.assertEqual(constants.freq_arch_to_midi_num(278, arch='PAL-C64')[0], midi_note)
        self.assertAlmostEqual(constants.freq_arch_to_freq(268, arch='NTSC-C64'), 16.337, 3)
        self.assertAlmostEqual(constants.freq_arch_to_freq(268, arch='PAL-C64'), 15.738, 3)

        # Every NTSC freq that resolves to C-1 under 440 tuning
        for ntsc_arch_freq in range(131, 139):
            midi_num, _ = constants.freq_arch_to_midi_num(
                ntsc_arch_freq,
                arch='NTSC-C64',
                tuning=constants.CONCERT_A)
            self.assertEqual(pitch_to_note_name(midi_num), 'C-1')  # the lowest note

        # Every PAL freq that resolves to C-1 under 440 tuning
        for pal_arch_freq in range(136, 144):
            midi_num, _ = constants.freq_arch_to_midi_num(
                pal_arch_freq,
                arch='PAL-C64',
                tuning=constants.CONCERT_A)
            self.assertEqual(pitch_to_note_name(midi_num), 'C-1')  # the lowest note


if __name__ == '__main__':
    unittest.main(failfast=False)
