import sandboxPath
import collections
import copy
from ctsBase import *
from ctsConstants import *

from ctsRChirp import RChirpOrderList, RChirpPattern

Transform = collections.namedtuple('Transform', ['transpose', 'stretch'])


@dataclass(order=True)
class Repeat:
    start_row: int = None       #: Starting row of original pattern
    length: int = 0             #: Length of repeated pattern
    repeat_start: int = None    #: Starting rows of repeats
    xform: Transform(0, 0)      #: Transform between repeats


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
    ret_row.note_num += xform.transpose
    ret_row.jiffy_len *= xform.stretch
    return ret_row


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
        repeats = find_all_repeats(v.rows)
