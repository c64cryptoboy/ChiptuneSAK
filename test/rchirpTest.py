import testingPath
import copy
import unittest
import ctsMidi
import ctsRChirp
import ctsGoatTracker
import ctsGtCompress
from ctsConstants import project_to_absolute_path

SONG_TEST_SONG = project_to_absolute_path('test/data/twinkle.mid')
GT_TEST_SONG = project_to_absolute_path('test/data/twinkle.sng')
COMPRESS_TEST_SONG = project_to_absolute_path('test/data/BWV_799.mid')


class RChirpSongTestCase(unittest.TestCase):
    def setUp(self):
        self.test_song = ctsMidi.import_midi_to_chirp(SONG_TEST_SONG)
        self.test_song.quantize(*self.test_song.estimate_quantization())
        self.rchirp_song = ctsRChirp.RChirpSong(self.test_song)
        self.compress_test_song = ctsMidi.import_midi_to_chirp(COMPRESS_TEST_SONG)

    def test_notes(self):
        for i, (t, v) in enumerate(zip(self.test_song.tracks, self.rchirp_song.voices)):
            with self.subTest(i=i):
                chirp_notes = set(n.note_num for n in t.notes)
                rchirp_notes = set(v.rows[r].note_num for r in v.rows)
                diff = chirp_notes - rchirp_notes
                self.assertTrue(len(diff) == 0)

    def test_gt_compression(self):
        self.compress_test_song = ctsMidi.import_midi_to_chirp(COMPRESS_TEST_SONG)
        self.compress_test_song.quantize_from_note_name('16')
        for i, program in enumerate([11, 10, 6]):
            self.compress_test_song.tracks[i].set_program(program)

        self.compress_test_song.remove_polyphony()
        self.compress_test_song.remove_keyswitches(12)
        rchirp_song = ctsRChirp.RChirpSong(self.compress_test_song)

        rchirp_song = ctsGtCompress.compress_gt_lr(rchirp_song, 16)

        self.assertTrue(ctsGtCompress.validate_gt_limits(rchirp_song))
        self.assertTrue(rchirp_song.validate_compression())

        ctsGtCompress.compress_gt_global(rchirp_song, 16)

        self.assertTrue(ctsGtCompress.validate_gt_limits(rchirp_song))
        self.assertTrue(rchirp_song.validate_compression())
        #ctsGoatTracker.export_rchirp_to_gt(rchirp_song, '../test/data/gt_test_out.sng')

        # Now delete a row from a pattern which should cause compressed song not to work.
        rchirp_song.patterns[0].rows.pop()
        self.assertFalse(rchirp_song.validate_compression())

        # print(f'{len(rchirp_song.patterns)} total patterns with a total of {sum(len(p.rows) for p in rchirp_song.patterns)} rows')
        #
        # print('%d total orderlist entries' % sum(len(v.orderlist) for v in rchirp_song.voices))
        # print('%d bytes estimated orderlist size' % sum(ctsGtCompress.get_gt_orderlist_length(v.orderlist) for v in rchirp_song.voices))
        # for i, v in enumerate(rchirp_song.voices):
        #     print(f'Voice {i+1}:')
        #     print(f'{len(v.orderlist)} orderlist entries')
        #     print(f'{ctsGtCompress.get_gt_orderlist_length(v.orderlist)} estimated orderlist rows')
        # print(f'{ctsGtCompress.estimate_song_size(rchirp_song)} bytes estimated song size')
        #
