import unittest
import chiptunesak
from chiptunesak.sid import SID, SidImport
from chiptunesak.constants import project_to_absolute_path, CONCERT_A, freq_arch_to_midi_num


class sidTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Test data: Defender of the Crown, Cinemaware, 1986, later released as freeware
        # CSDB: https://csdb.dk/sid/?id=15918
        cls.sid_filename = project_to_absolute_path('tests/data/Defender_of_the_Crown.sid')

        cls.sid = SID()
        cls.sid.set_options(
            sid_in_filename=cls.sid_filename,
            subtune=0,  # Main theme
            vibrato_cents_margin=10,
            seconds=4,  # just a 4 sec clip for testing, but ~80 if you want the whole tune
            gcf_row_reduce=True,
            verbose=False
        )

        cls.sid_dump = cls.sid.capture()

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

    def v1_vibrato_bounded(self, sid_rows, start_frame):
        unique_notes = set()
        sid_chip_index = 0
        channel_index = 0
        for row_num in range(start_frame, start_frame + 70):
            note = sid_rows[row_num].chips[sid_chip_index].channels[channel_index].note
            if note is not None:
                unique_notes.add(note)
        return len(unique_notes) == 1

    # @unittest.skip("Skipping this test for now")
    def test_vibrato_handling(self):
        # test vibrato handling on notes with increasingly higher amplitudes

        # Test data created with SID-Wizard 1.8, Extra engine
        # Desc:
        # - Used a simple triangle waveform (just ADSR 80F9, ADHR 0F00, WFARP 11)
        # - 08 in col 3 overrides vibrato.
        # - First nibble of column 4 is vibrato amplitude (0 is none, F is largest)
        # - Second nibble of column 4 is vibrato frequency (0 is fastest, F is slowest)
        # - SID-Wizard has an octave offset of +1
        # - Not multi-speed, so play call = frame #
        # Data:
        # - 00: col 1: A-4 col 3-4: 08 27
        # - 06: note off
        # - 0C: col 1: A-4 col 3-4: 08 67
        # - 12: note off
        # - 18: col 1: A-4 col 3-4: 08 87
        # - 1E: note off
        # - 24: col 1: A-4 col 3-4: 08 A7
        # - 2A: note off
        # Vibrato ranges:
        # - 1st note, frames   3- 72:  A3 -20 cents to  A3 +17 cents
        # - 2nd note, frames  75-144: G#3 +44 cents to  A3 +42 cents
        # - 3rd note, frames 147-216: G#3 + 8 cents to A#3 -33 cents
        # - 4th note, frames 219-288: G#3 -49 cents to A#3 + 6 cents

        vibrato_test_filename = project_to_absolute_path('tests/data/vibratotest.sid')

        # First test has 0 cents margin, so only first vibrato note will stay
        # a single note
        vibrato_test_sid = SID()
        vibrato_test_sid.set_options(
            sid_in_filename=vibrato_test_filename,
            vibrato_cents_margin=0,
            seconds=6,
            gcf_row_reduce=False,
            always_include_freq=True,
            verbose=False,
        )
        vibrato_test_dump = vibrato_test_sid.capture()
        sid_rows = vibrato_test_dump.rows

        # out_filename_no_ext = project_to_absolute_path('tests/temp/vibratoTest0cents')
        # vibrato_test_sid.to_csv_file(project_to_absolute_path('%s.csv' % out_filename_no_ext))

        self.assertTrue(self.v1_vibrato_bounded(sid_rows, 3))
        self.assertFalse(self.v1_vibrato_bounded(sid_rows, 75))
        self.assertFalse(self.v1_vibrato_bounded(sid_rows, 147))
        self.assertFalse(self.v1_vibrato_bounded(sid_rows, 219))

        vibrato_test_sid = SID()
        vibrato_test_sid.set_options(
            sid_in_filename=vibrato_test_filename,
            vibrato_cents_margin=42,
            seconds=6,
            gcf_row_reduce=False,
            always_include_freq=True,
            verbose=False,
        )
        vibrato_test_dump = vibrato_test_sid.capture()
        sid_rows = vibrato_test_dump.rows

        # out_filename_no_ext = project_to_absolute_path('tests/temp/vibratoTest42cents')
        # vibrato_test_sid.to_csv_file(project_to_absolute_path('%s.csv' % out_filename_no_ext))

        # Second test has a 42 cents margin, so all but the last vibrato note will
        # collapse into a single note
        self.assertTrue(self.v1_vibrato_bounded(sid_rows, 3))
        self.assertTrue(self.v1_vibrato_bounded(sid_rows, 75))
        self.assertTrue(self.v1_vibrato_bounded(sid_rows, 147))
        self.assertFalse(self.v1_vibrato_bounded(sid_rows, 219))

    # @unittest.skip("Skipping this test for now")
    def test_SID_extraction(self):
        # Test SID import for expected values in RChirp, and ability to transform extraction

        headers = self.sid_dump.sid_file

        # Check for expected header values

        self.assertTrue(headers.version == 2)
        self.assertFalse(headers.is_rsid)

        self.assertTrue(headers.start_song == 1)
        self.assertTrue(headers.num_subtunes == 10)
        self.assertTrue(headers.load_address == 0x804c)
        self.assertTrue(headers.init_address == 0xa9b7)
        self.assertTrue(headers.play_address == 0xa900)
        self.assertTrue(headers.author == b'Richard Joseph')
        self.assertTrue(headers.name == b'Defender of the Crown')
        self.assertTrue(headers.released == b'1987 Cinemaware')

        self.assertTrue(headers.data_offset == 124)
        self.assertTrue(headers.load_addr_preamble)
        self.assertTrue(headers.page_length == 124)
        self.assertTrue(headers.start_page == 4)
        self.assertTrue(headers.sid_model == 1)
        self.assertTrue(headers.sid_count == 1)
        self.assertTrue(headers.speed == 0b00000000000000000000001111111111)
        self.assertTrue(headers.flags == 0b0000000000010100)

        # Check for no runtime errors when converting to CSV output:
        out_filename_no_ext = project_to_absolute_path('tests/temp/dotcExcerptTest')
        self.sid.to_csv_file(project_to_absolute_path('%s.csv' % out_filename_no_ext))

        # Check for no runtime errors when converting to rchirp, then to a midi file
        rchirp_song = self.sid.to_rchirp(self.sid_filename)

        # CSV output shows 192 rows per quarter note (Note: output will be reduced to be more
        # concise, but the delta in row numbers for a quarter note is 192).  This is a lot of
        # rows for a quarter note, and it's due to the "multispeed" play routine being called
        # ~6.6 times per frame.
        play_calls_per_quarter = 192
        # A quarter note only takes 29184 milliframes, but we'll be passing in a value
        # ~6.6 times larger than that.  The larger number will act as a divisor in rchirp
        # which will get the song back up to a more its proper play speed.
        chirp_song = rchirp_song.to_chirp(
            milliframes_per_quarter=play_calls_per_quarter * 1000)
        chirp_song.set_key_signature('F')  # optional
        chirp_song.set_time_signature(4, 4)  # optional
        chiptunesak.MIDI().to_file(
            chirp_song, project_to_absolute_path('%s.mid' % out_filename_no_ext))

        # Check the opening chords for expected notes at expected times
        # (voice, expected_milliframe, expected_note) tuples:
        expected = ((0, 1064, 65), (1, 1064, 57), (2, 1064, 41),
                    (0, 30248, 65), (1, 30248, 57), (2, 30248, 48),
                    (0, 52136, 65), (1, 52136, 58), (2, 52136, 50),
                    (0, 59432, 65), (1, 59432, 57), (2, 59432, 48),
                    (2, 88616, 36))
        milliframe_indexed_rows = rchirp_song.milliframe_indexed_voices()
        for exp_note in expected:
            self.assertTrue(
                milliframe_indexed_rows[exp_note[0]][exp_note[1]].note_num == exp_note[2])

    # @unittest.skip("Skipping this test for now")
    def test_tuning(self):
        # Measure tunings from a set of notes, then using that tuning, measure that the
        # deviations get closer to CONCERT_A

        # (~448.973, 34, 35)
        (orig_tuning, orig_min_cents, orig_max_cents) \
            = self.sid_dump.get_tuning()  # CONCERT_A

        # (~439.987574, -1, 0)
        (new_tuning, new_min_cents, new_max_cents) \
            = self.sid_dump.get_tuning(orig_tuning)

        self.assertTrue(abs(CONCERT_A - new_tuning) < abs(CONCERT_A - orig_tuning))
        self.assertTrue(abs(new_max_cents) <= abs(orig_max_cents))


if __name__ == '__main__':
    unittest.main(failfast=False)
