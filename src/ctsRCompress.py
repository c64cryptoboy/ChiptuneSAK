from dataclasses import dataclass
import copy
import math
import collections
from ctsBase import *
from ctsConstants import *
import ctsGoatTracker
from ctsRChirp import RChirpOrderList, RChirpPattern, RChirpOrderEntry

STARTING_MIN_LENGTH = 16
PATTERN_LENGTH_MAX = 126

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
    if row1.note_num is None or row2.note_num is None:
        return Transform(0, 1)
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


def find_all_repeats(rows, min_length=4):
    """
    Find every possible repeat in the rows longer than a minimum length
    :param rows: list of rows to search for repeats
    :type rows: list of cts.RChirpRows
    :param min_length: Minimum length pattern to find
    :type min_length: int
    :return: list of all repeats found
    :rtype: list of Repeat
    """
    n_rows = len(rows)
    repeats = []
    for base_position in range(n_rows - min_length):
        for trial_position in range(base_position, n_rows - min_length):
            xf = get_xform(rows[base_position], rows[trial_position])
            pattern_length = 1
            ib = base_position + 1
            it = trial_position + 1
            while it < n_rows and rows[ib].gt_match(rows[it], xf):
                ib += 1
                it += 1
                pattern_length += 1
                if ib >= trial_position:
                    break
            if min_length <= pattern_length <= PATTERN_LENGTH_MAX:
                repeats.append(Repeat(base_position, trial_position, pattern_length, xf))
    return repeats


def find_best_repeats(repeats, used, objective_function, min_length=4):
    """
    Find the best repeats to use for a set of repeats.  Right now, the metric is coverage, with the
    shortest repeats that give a certain coverage used, but the metric can easily be changed.
    :param repeats: list of valid repeats
    :type repeats: list of Repeat objects
    :param used: boolean list of which rows have already been used
    :type used: list of bool
    :return: list of optimal repeats
    :rtype: list of Repeat objects
    """
    lengths = list(sorted(set(r.length for r in repeats if r.length >= min_length), reverse=True))
    available_rows = used.count(False)
    max_objective = 0
    best_repeats = []
    for length in lengths:
        # Find a set of non-overlapping repeats for length
        tmp_repeats = sorted([r for r in repeats if r.length >= length])
        starts = list(sorted(set(r.start_row for r in tmp_repeats)))
        for start in starts:
            repeats_group = [r for r in tmp_repeats if r.start_row == start]
            # Any repeat contains any smaller repeat in it.  So truncate them all.
            for i, r in enumerate(repeats_group):
                assert r.length >= length
                repeats_group[i].length = length
            r0 = repeats_group[0]
            last_used = r0.start_row + r0.length
            available_repeats = [r0]
            for r in repeats_group[1:]:
                if r.repeat_start >= last_used:
                    available_repeats.append(r)
                    last_used = r.repeat_start + r.length
            objective = objective_function(available_repeats, available_rows)
            if objective > max_objective:
                max_objective = objective
                best_repeats = copy.deepcopy(available_repeats)
    return best_repeats


def apply_pattern(pattern_index, repeats, used, order):
    """
    Given a pattern index and a set of repeats that match the pattern, mark the affected rows as used
    and insert them into the temporary orderlist
    :param pattern_index: Pattern number for the cstRChirpSong
    :type pattern_index: int
    :param repeats: Repeats that match the pattern
    :type repeats: list of Repeat objects
    :param used: list of rows, marked by whether they have been used
    :type used: list of bool
    :param order: temporary dictionary for the orderlist
    :type order: dictionary of (start_row, transposition) tuples
    :return: used, order
    :rtype: tuple of list of bool, dictionary
    """
    for r in repeats:
        used[r.start_row:r.start_row + r.length] = [True for i in range(r.length)]
        used[r.repeat_start:r.repeat_start + r.length] = [True for i in range(r.length)]
        order[r.start_row] = (pattern_index, 0)
        order[r.repeat_start] = (pattern_index, r.xform.transpose)
    return used, order


def make_orderlist(order):
    """
    Turns the temporary dictionary-based orderlist into an RChirp-compatible orderlist
    :param order: dictionary orderlist
    :type order: dictionary of (start_row, transposition)
    :return: orderlist to put into an RChirp song
    :rtype: ctsRChirp.RChirpOrderList
    """
    orderlist = RChirpOrderList()
    last = RChirpOrderEntry(0, 0, 0)
    for index in sorted(order):
        p_num, trans = order[index]
        if p_num == last.pattern_num and trans == last.transposition:
            last.repeats += 1
        else:
            orderlist.append(last)
            last = RChirpOrderEntry(p_num, trans, 1)
    orderlist.append(last)
    return orderlist


def trim_repeats(repeats, used):
    """
    Trims the list of repeats to exclude rows that have been used.
    :param repeats: list of all repeats
    :type repeats: list of Repeat objects
    :param used:
    :type used:
    :return: list of valid repeats
    :rtype: list of Repeat objects
    """
    ret_repeats = []
    for r in repeats:
        if used[r.start_row] or used[r.repeat_start]:
            continue
        r_end = r.start_row + r.length
        l_tmp = 0
        while l_tmp < r.length and not used[r.start_row + l_tmp] and not used[r.repeat_start + l_tmp]:
            l_tmp += 1
        r.length = l_tmp
        if r.length > 1:
            ret_repeats.append(r)
    return ret_repeats


def compress_gt(rchirp_song):
    """
    Compresses an RChirp song for Goattracker
    :param rchirp_song: RChirp song to compress
    :type rchirp_song: ctsRChirp.RChirpSong
    :return: rchirp_song with compression information added
    :rtype: ctsRChirp.RChirpSong
    """
    def objective(repeats, possible):
        r0 = repeats[0]
        nloops = len(repeats) + 1
        variation = abs(r0.length - STARTING_MIN_LENGTH + 0.5)
        return nloops * r0.length - abs(r0.length - STARTING_MIN_LENGTH) / 10

    rchirp_song.patterns = []  # Get rid of any patterns from previous compression
    last_pattern_count = 0
    for iv, v in enumerate(rchirp_song.voices):
        filled_rows = v.get_filled_rows()
        used = [False for r in filled_rows]
        n_rows = len(filled_rows)
        print("\nVoice %d: %d rows" % (iv, n_rows))
        order = {}
        repeats = find_all_repeats(filled_rows, min_length=4)
        it = 0
        min_length = 8
        while len(repeats) > 0 or min_length > 4:
            print('iteration %d:' % it, len(repeats), 'valid repeats;', used.count(False), 'rows left')
            best_repeats = find_best_repeats(repeats, used, objective, min_length=min_length)
            if len(best_repeats) > 0:
                r0 = best_repeats[0]
                rchirp_song.patterns.append(RChirpPattern(filled_rows[r0.start_row: r0.start_row + r0.length]))
                pattern_index = len(rchirp_song.patterns) - 1
                used, order = apply_pattern(pattern_index, best_repeats, used, order)
                print('created pattern of %d rows, used %d times' % (best_repeats[0].length, len(best_repeats) + 1))
                repeats = trim_repeats(repeats, used)
            min_length = max(min_length - 1, 4)
            it += 1
            if it > 20:
                repeats = []
        while any(not u for u in used):
            it += 1
            print('cleanup:', used.count(False), 'rows left')
            gap_start = next(iu for iu, u in enumerate(used) if not u)
            gap_end = gap_start
            while gap_end < n_rows and not used[gap_end]:
                gap_end += 1
            rchirp_song.patterns.append(RChirpPattern(filled_rows[gap_start: gap_end]))
            pattern_index = len(rchirp_song.patterns) - 1
            order[gap_start] = (pattern_index, 0)
            for ig in range(gap_start, gap_end):
                used[ig] = True
            print('created pattern of %d rows, used once' % (gap_end - gap_start))
        assert all(used), "Not all rows were used!"
        print('voice complete. %d patterns created; %d max patterns in orderlist' % (len(rchirp_song.patterns) - last_pattern_count, len(order)))
        last_pattern_count = len(rchirp_song.patterns)
        rchirp_song.voices[iv].orderlist = make_orderlist(order)
    print('\nTotal patterns = %d; longest pattern = %d'
          % (len(rchirp_song.patterns), max(len(p.rows) for p in rchirp_song.patterns)))
    rchirp_song.compressed = True
    return rchirp_song


def find_repeats_starting_at(index, rows, used, min_length=4):
    n_rows = len(rows)
    repeats = []
    base_position = index
    for trial_position in range(base_position, n_rows - min_length):
        if used[trial_position]:
            continue
        xf = get_xform(rows[base_position], rows[trial_position])
        pattern_length = 1
        ib = base_position + 1
        it = trial_position + 1
        il = 1
        while it < n_rows \
                and il < PATTERN_LENGTH_MAX \
                and rows[ib].gt_match(rows[it], xf) \
                and not used[ib] \
                and not used[it]:
            ib += 1
            it += 1
            il += 1
            pattern_length += 1
            if ib >= trial_position:
                break
        if min_length <= pattern_length <= PATTERN_LENGTH_MAX:
            repeats.append(Repeat(base_position, trial_position, pattern_length, xf))
    return repeats


def compress_gt_2(rchirp_song):
    """
    Compresses an RChirp song for Goattracker
    :param rchirp_song: RChirp song to compress
    :type rchirp_song: ctsRChirp.RChirpSong
    :return: rchirp_song with compression information added
    :rtype: ctsRChirp.RChirpSong
    """
    def objective(repeats, possible):
        r0 = repeats[0]
        nloops = len(repeats) + 1
        return nloops * r0.length - abs(r0.length - STARTING_MIN_LENGTH) / 10

    rchirp_song.patterns = []  # Get rid of any patterns from previous compression
    last_pattern_count = 0
    min_pattern_length = 4
    for iv, v in enumerate(rchirp_song.voices):
        filled_rows = v.get_filled_rows()
        used = [False for r in filled_rows]
        n_rows = len(filled_rows)
        print("\nVoice %d: %d rows" % (iv, n_rows))
        order = {}
        for i in range(n_rows - min_pattern_length):
            if used[i]:
                continue
            repeats = find_repeats_starting_at(i, filled_rows, used, min_length=min_pattern_length)
            it = 0
            min_length = 8
            while len(repeats) > 0 or min_length > min_pattern_length:
                best_repeats = find_best_repeats(repeats, used, objective, min_length=min_length)
                if len(best_repeats) > 0:
                    r0 = best_repeats[0]
                    rchirp_song.patterns.append(RChirpPattern(filled_rows[r0.start_row: r0.start_row + r0.length]))
                    pattern_index = len(rchirp_song.patterns) - 1
                    used, order = apply_pattern(pattern_index, best_repeats, used, order)
                    print('position %d: created pattern of %d rows, used %d times' % (i, best_repeats[0].length, len(best_repeats) + 1))
                    repeats = trim_repeats(repeats, used)
                min_length = max(min_length - 1, min_pattern_length)
                it += 1
                if it > 20:
                    repeats = []
        while any(not u for u in used):
            print('cleanup:', used.count(False), 'rows left')
            gap_start = next(iu for iu, u in enumerate(used) if not u)
            gap_end = gap_start
            while gap_end < n_rows and not used[gap_end]:
                gap_end += 1
            rchirp_song.patterns.append(RChirpPattern(filled_rows[gap_start: gap_end]))
            pattern_index = len(rchirp_song.patterns) - 1
            order[gap_start] = (pattern_index, 0)
            for ig in range(gap_start, gap_end):
                used[ig] = True
            print('created pattern of %d rows, used once' % (gap_end - gap_start))
        assert all(used), "Not all rows were used!"
        print('voice complete. %d patterns created; %d max patterns in orderlist' % (len(rchirp_song.patterns) - last_pattern_count, len(order)))
        last_pattern_count = len(rchirp_song.patterns)
        rchirp_song.voices[iv].orderlist = make_orderlist(order)
    print('\nTotal patterns = %d; longest pattern = %d'
          % (len(rchirp_song.patterns), max(len(p.rows) for p in rchirp_song.patterns)))
    rchirp_song.compressed = True
    return rchirp_song


def get_gt_orderlist_length(orderlist):
    retval = 2  # Start and end commands
    prev_transposition = 0
    for entry in orderlist:
        if entry.transposition != prev_transposition:
            retval += 1
            prev_transposition = entry.transposition
        if entry.repeats > 16:
            retval += (2 * (entry.repeats // 16))  # 2 bytes for each repeat
        if entry.repeats % 16 != 0:
            retval += 1
            if entry.repeats % 16 != 1:
                retval += 1
    return retval

if __name__ == '__main__':
    rchirp_song = ctsGoatTracker.import_sng_file_to_rchirp('../test/data/gtTestData.sng')

    rchirp_song = compress_gt_2(rchirp_song)

    for i, v in enumerate(rchirp_song.voices):
        print('Voice %d:' % (i + 1))
        print('%d orderlist entries' % len(v.orderlist))
        print('%d estimated orderlist rows' % get_gt_orderlist_length(v.orderlist))
