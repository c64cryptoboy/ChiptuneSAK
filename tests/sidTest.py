# TODO:
# - this hardly covers all the ctsSID functionality, need to add many more tests

#import testingPath  # noqa
import unittest
from chiptunesak import ctsConstants
from chiptunesak import ctsSID


class sidTests(unittest.TestCase):

    def test_SID_freqs_to_midi_notes(self):
        si_ntsc = ctsSID.SidImport(arch='NTSC-C64', tuning=ctsConstants.CONCERT_A)
        si_pal = ctsSID.SidImport(arch='PAL-C64', tuning=ctsConstants.CONCERT_A)

        cminus1_midi_num = 0  # our lowest note
        # Very low SID frequencies tests
        self.assertEqual(  # C#-1
            si_ntsc.get_note(142, vibrato_cents_margin=0, prev_note=None), cminus1_midi_num + 1)
        self.assertEqual(
            si_ntsc.get_note(134, vibrato_cents_margin=0, prev_note=None), cminus1_midi_num)
        # instead of returning midi_note -1, it returns midi_note 0 (the lowest allowed):
        self.assertEqual(
            si_ntsc.get_note(127, vibrato_cents_margin=0, prev_note=None), cminus1_midi_num)
        # frequency 0 legit in C64, but undefined in sound frequency space, so return lowest again
        self.assertEqual(
            si_ntsc.get_note(0, vibrato_cents_margin=0, prev_note=None), cminus1_midi_num)

        # Very high SID frequencies tests
        b7_midi_num = 107
        # Max NTSC freq = B7 + 19 cents
        self.assertEqual(
            si_ntsc.get_note(65535, vibrato_cents_margin=0, prev_note=None), b7_midi_num)
        # Max PAL freq = B7 - 46 cents
        self.assertEqual(
            si_pal.get_note(65535, vibrato_cents_margin=0, prev_note=None), b7_midi_num)

        # vibrator_cents_margin tests -- first, create some g2 test notes
        g2_midi_num = 43

        very_flat_g2_freq = 1571
        (midi_note, very_flat_g2_cents) = ctsConstants.freq_arch_to_midi_num(
            very_flat_g2_freq, arch='NTSC-C64', tuning=ctsConstants.CONCERT_A)
        self.assertEquals((midi_note, very_flat_g2_cents), (g2_midi_num, -40))

        flat_g2_freq = 1604
        (midi_note, flat_g2_cents) = ctsConstants.freq_arch_to_midi_num(
            flat_g2_freq, arch='NTSC-C64', tuning=ctsConstants.CONCERT_A)
        self.assertEquals((midi_note, flat_g2_cents), (g2_midi_num, -4))

        # g2_freq = 1608
        # (midi_note, g2_cents) = ctsConstants.freq_arch_to_midi_num(
        #     g2_freq, arch='NTSC-C64', tuning=ctsConstants.CONCERT_A)
        # self.assertEquals((midi_note, g2_cents), (g2_midi_num, 0))

        sharp_g2_freq = 1611
        (midi_note, sharp_g2_cents) = ctsConstants.freq_arch_to_midi_num(
            sharp_g2_freq, arch='NTSC-C64', tuning=ctsConstants.CONCERT_A)
        self.assertEquals((midi_note, sharp_g2_cents), (g2_midi_num, 4))

        very_sharp_g2_freq = 1645
        (midi_note, very_sharp_g2_cents) = ctsConstants.freq_arch_to_midi_num(
            very_sharp_g2_freq, arch='NTSC-C64', tuning=ctsConstants.CONCERT_A)
        self.assertEquals((midi_note, very_sharp_g2_cents), (g2_midi_num, 40))

        # Scenario A: We imagine a wide vibrato on an f#2 strayed a little into
        # g2 teritory, so a f#2 is selected instead, because f#2 was the note on the previous
        # play call.
        self.assertEquals(si_ntsc.get_note(very_flat_g2_freq,
            vibrato_cents_margin=15, prev_note=g2_midi_num - 1), g2_midi_num - 1)

        # Scenario B: The g2 is very flat (nearly an f#2), but the previous note (vibrato or not)
        # was too far away to be the culprit, so it stays a g2
        self.assertEquals(si_ntsc.get_note(very_flat_g2_freq,
            vibrato_cents_margin=15, prev_note=g2_midi_num - 2), g2_midi_num)

        # Scenario C: Like scenario A, except the flattness is not great enough to fall into
        # the vibrato_cents_margin setting, so the note remains unchanged
        self.assertEquals(si_ntsc.get_note(flat_g2_freq,
            vibrato_cents_margin=15, prev_note=g2_midi_num - 1), g2_midi_num)

        # Scenario D: Like Scenario A, but from the other direction (big vibrato on a g#2)
        self.assertEquals(si_ntsc.get_note(very_sharp_g2_freq,
            vibrato_cents_margin=15, prev_note=g2_midi_num + 1), g2_midi_num + 1)

        # Scenario E: Like Scenario B, but from the other direction again
        self.assertEquals(si_ntsc.get_note(very_sharp_g2_freq,
            vibrato_cents_margin=15, prev_note=g2_midi_num + 2), g2_midi_num)

        # Scenario F: Like Scenario C, but from the other direction again
        self.assertEquals(si_ntsc.get_note(sharp_g2_freq,
            vibrato_cents_margin=15, prev_note=g2_midi_num + 1), g2_midi_num)


if __name__ == '__main__':
    unittest.main(failfast=False)
