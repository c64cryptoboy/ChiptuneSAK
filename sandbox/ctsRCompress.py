import sandboxPath
import collections
from dataclasses import dataclass
import copy
from ctsBase import *
from ctsConstants import *
import ctsGoatTracker

from ctsRChirp import RChirpOrderList, RChirpPattern

Transform = collections.namedtuple('Transform', ['transpose', 'stretch'])


@dataclass(order=True)
class Repeat:
    start_row: int = None       #: Starting row of original pattern
    repeat_start: int = None    #: Starting row of repeats
    length: int = 0             #: Length of repeated pattern
    xform: Transform = Transform(0, 0)  #: Transform between repeats


def get_xform(row1, row2):
    """
    Gets the transform for transposition and time stretching to match two notes.
    :param row1:
    :type row1: RChirpRow
    :param row2:
    :type row2: RChirpRow
    :return:
    :rtype:
    """
    transpose = row2.note_num - row1.note_num
    return Transform(transpose, 1)  # not doing any stretch for now.


def apply_xform(row, xform):
    """
    Applies a transposition and stretching transform to a row, returning a new row
    :param row:
    :type row: RChirpRow
    :param xform:
    :type xform: Transform
    :return:
    :rtype: RChirpRow
    """
    ret_row = copy.copy(row)
    if ret_row.note_num is not None:
        ret_row.note_num += xform.transpose
    if ret_row.jiffy_len is not None:
        ret_row.jiffy_len *= xform.stretch
    return ret_row


def is_valid_start(rows, position):
    return rows[position].note_num is not None


def find_all_repeats(rows, min_length=4):
    """
    Finds all repeating patterns in a list of rows
    :param rows:
    :type rows:
    :param min_length:
    :type min_length:
    :return:
    :rtype:
    """
    n_rows = len(rows)
    patterns = []
    for base_position in range(n_rows - min_length):
        for trial_position in range(base_position + min_length, n_rows - min_length):
            if is_valid_start(rows, base_position) and is_valid_start(rows, trial_position):
                xf = get_xform(rows[base_position], rows[trial_position])
                pattern_length = 1
                ib = base_position + 1
                it = trial_position + 1
                while rows[ib].gt_match(rows[it], xf):
                    ib += 1
                    it += 1
                    pattern_length += 1
                    if ib >= trial_position:
                        break
                if pattern_length >= min_length:
                    patterns.append(Repeat(base_position, trial_position, pattern_length, xf))

    return patterns


def compress_gt(rchirp_song):
    """
    Compresses an RChirp song for Goattracker
    :param rchirp_song: RChirp song to compress
    :type rchirp_song: ctsRChirp.RChirpSong
    :return: compression parameters
    :rtype:
    """
    n_voices = rchirp_song.voice_count()
    order_list = [RChirpOrderList() for i in range(n_voices)]
    for iv, v in enumerate(rchirp_song.voices):
        repeats = find_all_repeats(v.get_filled_rows())
    return repeats

if __name__ == '__main__':
    parsed_gt = ctsGoatTracker.import_sng_file_to_parsed_gt('../test/data/gtTestData.sng')
    rchirp_song = ctsGoatTracker.import_parsed_gt_to_rchirp(parsed_gt, 0)

    compress_gt(rchirp_song)
