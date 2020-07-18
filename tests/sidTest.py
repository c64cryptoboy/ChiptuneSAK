# TODO:
# - finish partially written tests cases

import unittest
import chiptunesak
from chiptunesak.sid import SID, SidImport
from chiptunesak.constants import project_to_absolute_path, CONCERT_A, freq_arch_to_midi_num


class sidTests(unittest.TestCase):

    # @unittest.skip("Skipping this test for now")
    def test_SID_freqs_to_midi_notes(self):
        si_ntsc = SidImport(arch='NTSC-C64', tuning=CONCERT_A)
        si_pal = SidImport(arch='PAL-C64', tuning=CONCERT_A)

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
        (midi_note, very_flat_g2_cents) = freq_arch_to_midi_num(
            very_flat_g2_freq, arch='NTSC-C64', tuning=CONCERT_A)
        self.assertEqual((midi_note, very_flat_g2_cents), (g2_midi_num, -40))

        flat_g2_freq = 1604
        (midi_note, flat_g2_cents) = freq_arch_to_midi_num(
            flat_g2_freq, arch='NTSC-C64', tuning=CONCERT_A)
        self.assertEqual((midi_note, flat_g2_cents), (g2_midi_num, -4))

        # g2_freq = 1608
        # (midi_note, g2_cents) = constants.freq_arch_to_midi_num(
        #     g2_freq, arch='NTSC-C64', tuning=constants.CONCERT_A)
        # self.assertEqual((midi_note, g2_cents), (g2_midi_num, 0))

        sharp_g2_freq = 1611
        (midi_note, sharp_g2_cents) = freq_arch_to_midi_num(
            sharp_g2_freq, arch='NTSC-C64', tuning=CONCERT_A)
        self.assertEqual((midi_note, sharp_g2_cents), (g2_midi_num, 4))

        very_sharp_g2_freq = 1645
        (midi_note, very_sharp_g2_cents) = freq_arch_to_midi_num(
            very_sharp_g2_freq, arch='NTSC-C64', tuning=CONCERT_A)
        self.assertEqual((midi_note, very_sharp_g2_cents), (g2_midi_num, 40))

        # Scenario A: We imagine a wide vibrato on an f#2 strayed a little into
        # g2 teritory, so a f#2 is selected instead, because f#2 was the note on the previous
        # play call.
        self.assertEqual(
            si_ntsc.get_note(very_flat_g2_freq, vibrato_cents_margin=15, prev_note=g2_midi_num - 1),
            g2_midi_num - 1)

        # Scenario B: The g2 is very flat (nearly an f#2), but the previous note (vibrato or not)
        # was too far away to be the culprit, so it stays a g2
        self.assertEqual(
            si_ntsc.get_note(very_flat_g2_freq, vibrato_cents_margin=15, prev_note=g2_midi_num - 2),
            g2_midi_num)

        # Scenario C: Like scenario A, except the flattness is not great enough to fall into
        # the vibrato_cents_margin setting, so the note remains unchanged
        self.assertEqual(
            si_ntsc.get_note(flat_g2_freq, vibrato_cents_margin=15, prev_note=g2_midi_num - 1),
            g2_midi_num)

        # Scenario D: Like Scenario A, but from the other direction (big vibrato on a g#2)
        self.assertEqual(
            si_ntsc.get_note(very_sharp_g2_freq, vibrato_cents_margin=15, prev_note=g2_midi_num + 1),
            g2_midi_num + 1)

        # Scenario E: Like Scenario B, but from the other direction again
        self.assertEqual(
            si_ntsc.get_note(very_sharp_g2_freq, vibrato_cents_margin=15, prev_note=g2_midi_num + 2),
            g2_midi_num)

        # Scenario F: Like Scenario C, but from the other direction again
        self.assertEqual(
            si_ntsc.get_note(sharp_g2_freq, vibrato_cents_margin=15, prev_note=g2_midi_num + 1),
            g2_midi_num)

    # @unittest.skip("Skipping this test for now")
    def test_SID_extraction(self):
        # TODO
        # Test SID import for expected values in RChirp
        #
        # Test data: Defender of the Crown, Cinemaware, 1986, later released as freeware
        # CSDB: https://csdb.dk/sid/?id=15918

        sid_filename = project_to_absolute_path('res/Defender_of_the_Crown.sid')

        sid = SID()
        sid.set_options(
            sid_in_filename=sid_filename,
            subtune=0,  # Main theme
            vibrato_cents_margin=10,
            seconds=4,  # just a small clip for testing
            gcf_row_reduce=True,
            verbose=False
        )

        sid_dump = sid.capture()  # noqa: F841

        # TODO: check for expected SID parsed values (author name, speed bits, etc.)

        out_filename_no_ext = project_to_absolute_path('tests/temp/dotcExcerptTest')

        sid.to_csv_file(project_to_absolute_path('%s.csv' % out_filename_no_ext))

        rchirp_song = sid.to_rchirp()

        # CSV output shows 192 rows per quarter note (Note: output will be reduced to be more
        # concise, but the delta in row numbers for a quarter note is 192).  This is a lot of
        # rows for a quarter note, and it's due to the "multispeed" play routine being called
        # ~6.6 times per frame.
        play_calls_per_quarter = 192
        # A quarter note only takes 29184 milliframes, but we'll be passing in a value
        # ~6.6 times larger than that.  The larger number will act as a divisor in rchirp
        # which will get the song back up to its proper play speed.
        chirp_song = rchirp_song.to_chirp(
            milliframes_per_quarter=play_calls_per_quarter * 1000)
        chirp_song.set_key_signature('F')  # optional
        chirp_song.set_time_signature(4, 4)  # optional
        chiptunesak.MIDI().to_file(
            chirp_song, project_to_absolute_path('%s.mid' % out_filename_no_ext))

        self.assertTrue(True)

    @unittest.skip("Skipping this test for now")
    def test_tuning(self):
        # TODO:
        # Measure tunings from a set of notes, then using that tuning, measure that the
        # cents deviations get closer to zero
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main(failfast=False)
