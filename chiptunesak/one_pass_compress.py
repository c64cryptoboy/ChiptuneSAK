import sys
import collections
from dataclasses import dataclass
import copy
from chiptunesak.base import *
from chiptunesak import goat_tracker
from chiptunesak.rchirp import RChirpOrderList, RChirpPattern, RChirpOrderEntry


"""
Compression routines the work for GoatTracker and may work for other formats

"""

MAX_PATTERN_LENGTH = 120


Transform = collections.namedtuple('Transform', ['transpose', 'stretch'])


@dataclass(order=True)
class Repeat:
    start_row: int = None       #: Starting row of original pattern
    repeat_start: int = None    #: Starting row of repeats
    length: int = 0             #: Length of repeated pattern
    xform: Transform = Transform(0, 0)  #: Transform between repeats


def op_row_match(r1, r2, xf=None):
    if r1.note_num is None and r2.note_num is None:
        note_match = True
    elif r1.note_num is None or r2.note_num is None:
        note_match = False
    elif xf is not None:
        note_match = r1.note_num + xf.transpose == r2.note_num
    else:
        note_match = r1.note_num == r2.note_num
    return (
            note_match
            and r1.instr_num == r2.instr_num
            and r1.new_instrument == r2.new_instrument
            and r1.gate == r2.gate
            and r1.milliframe_len == r2.milliframe_len
            and r1.new_milliframe_tempo == r2.new_milliframe_tempo
    )


def op_pattern_match(p1, p2, xf=None):
    if len(p1.rows) != len(p2.rows):
        return False
    n_rows = len(p1.rows)
    for ir in range(n_rows):
        if not op_row_match(p1.rows[ir], p2.rows[ir], xf):
            return False
    return True


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
    if row1.note_num is None and row2.note_num is None:
        return Transform(0, 1)
    elif row1.note_num is None or row2.note_num is None:
        return None
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
    if ret_row.milliframe_len is not None:
        ret_row.milliframe_len *= xform.stretch
    return ret_row


class OnePass(ChiptuneSAKCompress):
    @classmethod
    def cts_type(cls):
        return 'OnePass'

    def __init__(self):
        ChiptuneSAKCompress.__init__(self)
        self.used = []
        self.set_options(min_transposition=-15, max_transposition=14, min_pattern_length=16)

    @staticmethod
    def objective_function(repeats, possible):
        r0 = repeats[0]
        nloops = len(repeats) + 1
        return nloops * r0.length + 5 * r0.length

    def disable_transposition(self):
        self.set_options(min_transposition=0, max_transposition=0)

    def find_best_repeats(self, repeats):
        """
        Find the best repeats to use for a set of repeats.  Right now, the metric is coverage, with the
        shortest repeats that give a certain coverage used, but the metric can easily be changed.
        :param repeats: list of valid repeats
        :type repeats: list of Repeat objects
        :return: list of optimal repeats
        :rtype: list of Repeat objects
        """
        min_length = self.get_option('min_pattern_length', MAX_PATTERN_LENGTH)
        lengths = list(sorted(set(r.length for r in repeats if r.length >= min_length), reverse=True))
        available_rows = self.used.count(False)
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
                objective = self.objective_function(available_repeats, available_rows)
                if objective > max_objective:
                    max_objective = objective
                    best_repeats = copy.deepcopy(available_repeats)
        return best_repeats

    def apply_pattern(self, pattern_index, repeats, order):
        """
        Given a pattern index and a set of repeats that match the pattern, mark the affected rows as used
        and insert them into the temporary orderlist
        :param pattern_index: Pattern number for the cstRChirpSong
        :type pattern_index: int
        :param repeats: Repeats that match the pattern
        :type repeats: list of Repeat objects
        :param order: temporary dictionary for the orderlist
        :type order: dictionary of (start_row, transposition) tuples
        :return: order
        :rtype: orderlist dictionary
        """
        for r in repeats:
            self.used[r.start_row:r.start_row + r.length] = [True for i in range(r.length)]
            self.used[r.repeat_start:r.repeat_start + r.length] = [True for i in range(r.length)]
            order[r.start_row] = (pattern_index, 0)
            # print('length %d at row %d' % (r.length, r.start_row))
            order[r.repeat_start] = (pattern_index, r.xform.transpose)
            # print('length %d at row %d' % (r.length, r.repeat_start))
        return order

    def trim_repeats(self, repeats):
        """
        Trims the list of repeats to exclude rows that have been used.
        :param repeats: list of all repeats
        :type repeats: list of Repeat objects
        :return: list of valid repeats
        :rtype: list of Repeat objects
        """
        min_length = self.get_option('min_pattern_length', 126)
        ret_repeats = []
        for r in repeats:
            if self.used[r.start_row] or self.used[r.repeat_start]:
                continue
            l_tmp = 0
            while l_tmp < r.length and not self.used[r.start_row + l_tmp] and not self.used[r.repeat_start + l_tmp]:
                l_tmp += 1
            r.length = l_tmp
            if r.length >= min_length:
                ret_repeats.append(r)
        return ret_repeats

    def get_hole_lengths(self):
        """
        Creates list of the holes of unused rows in a set of rows.
        :return:
        :rtype:
        """
        retval = []
        n_rows = len(self.used)
        current_hole_size = 0
        for i in range(n_rows):
            if not self.used[i]:
                current_hole_size += 1
            else:
                if current_hole_size > 0:
                    retval.append(current_hole_size)
                    current_hole_size = 0
        if current_hole_size > 0:
            retval.append(current_hole_size)
        return retval

    @staticmethod
    def add_rchirp_pattern_to_song(rchirp_song, pattern):
        """
        Adds a pattern to an RChirpSong.  It checks to be sue that the pattern has not been used.
        :param rchirp_song: An RChirpSong
        :type rchirp_song: rchirpSong
        :param pattern: the pattern to add to the song
        :type pattern:  rchirp.RChirpPattern
        :return: Index of pattern
        :rtype: int
        """
        for ip, p in enumerate(rchirp_song.patterns):
            if op_pattern_match(p, pattern):
                return ip
        rchirp_song.patterns.append(pattern)
        return len(rchirp_song.patterns) - 1

    @staticmethod
    def make_orderlist(order):
        """
        Converts the temporary dictionary-based orderlist into an RChirp-compatible orderlist
        :param order: dictionary orderlist (created internally)
        :type order: dictionary of (start_row, transposition)
        :return: orderlist to put into a rchirp.RChirpVoice
        :rtype: rchirp.RChirpOrderList
        """
        orderlist = RChirpOrderList()
        last = RChirpOrderEntry(0, 0, 0)
        for index in sorted(order):
            p_num, trans = order[index]
            if p_num == last.pattern_num and trans == last.transposition:
                last.repeats += 1
            else:
                if last.repeats > 0:
                    orderlist.append(last)
                last = RChirpOrderEntry(p_num, trans, 1)
        orderlist.append(last)
        return orderlist

    @staticmethod
    def validate_orderlist(patterns, order, total_length):
        """
        Validates that the sparse orderlist is self-consistent.
        :param patterns:
        :type patterns:
        :param order:
        :type order:
        :return:
        :rtype: bool
        """
        retval = True
        positions = sorted(order)
        position_sum = 0
        for p in positions:
            if position_sum != p:
                print("Order mismatch at position %d:  %d" % (position_sum, p))
                retval = False
            o = order[p]
            position_sum += len(patterns[o[0]].rows)
        if position_sum != total_length:
            return False
        return retval


class OnePassGlobal(OnePass):
    """
        Global greedy compression algorithm for GoatTracker

        This algorithm attempts to find the best repeats to compress at every iteration; it begins by finding
        all possible repeats longer than min_pattern_length (which is O(n^2)) and then at each iteration
        chooses the set of repeats with the highest score.  The rows used are removed and the algorithm iterates.
        At each iteration the available repeats are trimmed to avoid the used rows.
    """
    @classmethod
    def cts_type(cls):
        return 'OnePassGlobal'

    def __init__(self):
        OnePass.__init__(self)

    def compress(self, rchirp_song, **kwargs):
        """
        Compresses the RChirp using a single-pass global greedy pattern detection. It finds all repeats in the song and
        turns the lrgest one into a pattern.  It continues this operation until the longest repeat is shorter than
        `min_pattern_length`, after which it fills in the gaps.

        :param rchirp_song: RChirp song to compress
        :type rchirp_song: rchirp.RChirpSong
        :return: rchirp_song with compression information added
        :rtype: rchirp.RChirpSong

        :keyword options:
            * **min_pattern_length** (int) - minimum pattern length in rows
            * **min_transpose** (int) - minimum transposition, in semitones, for a pattern to be a match (GoatTracker = -15)
            * **max_transpose** (int) - maximum transposition, in semitones, allowed for a pattern to be a match (GoatTracker = +14)
            * for no transposition, set both **min_transpose** and **max_transpose** to 0.
        """
        self.set_options(**kwargs)
        return self.compress_global(rchirp_song)

    def find_all_repeats(self, rows):
        """
        Find every possible repeat in the rows longer than a minimum length
        :param rows: list of rows to search for repeats
        :type rows: list of cts.RChirpRows
        :return: list of all repeats found
        :rtype: list of Repeat
        """
        min_length = self.get_option('min_pattern_length', MAX_PATTERN_LENGTH)
        n_rows = len(rows)
        min_transpose = self.get_option('min_transpose', 0)
        max_transpose = self.get_option('max_transpose', 0)
        repeats = []
        for base_position in range(n_rows - min_length):
            last_end = base_position
            for trial_position in range(base_position, n_rows - min_length):
                if trial_position < last_end:
                    continue
                xf = get_xform(rows[base_position], rows[trial_position])
                if xf is None:
                    continue
                if xf.transpose < min_transpose or xf.transpose > max_transpose:
                    continue
                pattern_length = 0
                ib = base_position
                it = trial_position
                while it < n_rows \
                        and pattern_length < MAX_PATTERN_LENGTH \
                        and op_row_match(rows[ib], rows[it], xf) \
                        and not self.used[ib] \
                        and not self.used[it]:
                    ib += 1
                    it += 1
                    pattern_length += 1
                    if ib >= trial_position:
                        break
                if min_length <= pattern_length <= MAX_PATTERN_LENGTH:
                    repeats.append(Repeat(base_position, trial_position, pattern_length, xf))
                    last_end = trial_position + pattern_length
        return repeats

    def compress_global(self, rchirp_song):
        """
        Global greedy compression algorithm for GoatTracker

        This algorithm attempts to find the best repeats to compress at every iteration; it begins by finding
        all possible repeats longer than min_pattern_length (which is O(n^2)) and then at each iteration
        chooses the set of repeats with the highest score.  The rows used are removed and the algorithm iterates.
        At each iteration the available repeats are trimmed to avoid the used rows.

        :param rchirp_song: RChirp song to compress
        :type rchirp_song: rchirp.RChirpSong
        :return: rchirp_song with compression information added
        :rtype: rchirp.RChirpSong
        """

        rchirp_song.patterns = []  # Get rid of any patterns from previous compression
        for iv, v in enumerate(rchirp_song.voices):
            filled_rows = v.make_filled_rows()
            self.used = [False for r in filled_rows]
            n_rows = len(filled_rows)
            order = {}
            repeats = self.find_all_repeats(filled_rows)
            while len(repeats) > 0:
                best_repeats = self.find_best_repeats(repeats)
                if len(best_repeats) > 0:
                    r0 = best_repeats[0]
                    rchirp_song.patterns.append(RChirpPattern(filled_rows[r0.start_row: r0.start_row + r0.length]))
                    pattern_index = len(rchirp_song.patterns) - 1
                    order = self.apply_pattern(pattern_index, best_repeats, order)
                    repeats = self.trim_repeats(repeats)
            while any(not u for u in self.used):
                gap_start = next(iu for iu, u in enumerate(self.used) if not u)
                gap_end = gap_start
                while gap_end < n_rows and not self.used[gap_end]:
                    gap_end += 1
                    if gap_end - gap_start >= MAX_PATTERN_LENGTH:
                        break
                tmp_patt = RChirpPattern(filled_rows[gap_start: gap_end])
                pattern_index = self.add_rchirp_pattern_to_song(rchirp_song, tmp_patt)
                order[gap_start] = (pattern_index, 0)
                for ig in range(gap_start, gap_end):
                    self.used[ig] = True
            assert all(self.used), "Not all rows were used!"
            if not self.validate_orderlist(rchirp_song.patterns, order, len(filled_rows)):
                exit('Orderlist mismatch')
            rchirp_song.voices[iv].orderlist = self.make_orderlist(order)
        rchirp_song.compressed = True
        return rchirp_song


class OnePassLeftToRight(OnePass):
    """
    Left-to-right left single-pass compression for GoatTracker

    This compression algorithm is the fastest; it can compress even the longest song in less than a second.
    It compresses the song in a manner similar to how a GoatTracker song would be constructed; starting from the
    beginning row, it finds the repeats of rows starting at that position that give the best score, and
    then moves to the first gap in the remaining rows and repeats.  If the algorithm does not find any suitable
    repeats at a position, it moves to the next, and the unused rows are put into patterns after all the repeats
    have been found.
    """
    @classmethod
    def cts_type(cls):
        return 'OnePassLeftToRight'

    def __init__(self):
        OnePass.__init__(self)

    def compress(self, rchirp_song, **kwargs):
        """
        Compresses the RChirp using a single-pass left-to-right pattern detection. Starting at the first row, it
        finds the longest pattern that repeats, and if it is longer than `min_pattern_length` it removes the pattern and
        all repeats from the remaining rows.  It then performs the same operation on the first available row until all
        patterns have been found, and then fills in the gaps.

        :param rchirp_song: RChirp song to compress
        :type rchirp_song: rchirp.RChirpSong
        :return: rchirp_song with compression information added
        :rtype: rchirp.RChirpSong


        :keyword options:
            * **min_pattern_length** (int) - minimum pattern length in rows
            * **min_transpose** (int) - minimum transposition, in semitones, for a pattern to be a match (GoatTracker = -15)
            * **max_transpose** (int) - maximum transposition, in semitones, allowed for a pattern to be a match (GoatTracker = +14)
            * for no transposition, set both **min_transpose** and **max_transpose** to 0.

        """
        self.set_options(**kwargs)
        return self.compress_lr(rchirp_song)

    def find_repeats_starting_at(self, index, rows):
        min_length = self.get_option('min_pattern_length', MAX_PATTERN_LENGTH)
        n_rows = len(rows)
        min_transpose = self.get_option('min_transpose', 0)
        max_transpose = self.get_option('max_transpose', 0)
        repeats = []
        base_position = index
        last_end = base_position
        for trial_position in range(base_position, n_rows - min_length):
            if self.used[trial_position] or trial_position < last_end:
                continue
            xf = get_xform(rows[base_position], rows[trial_position])
            if xf is None:
                continue
            if xf.transpose < min_transpose or xf.transpose > max_transpose:
                continue
            pattern_length = 0
            ib = base_position
            it = trial_position
            while it < n_rows \
                    and pattern_length < MAX_PATTERN_LENGTH \
                    and op_row_match(rows[ib], rows[it], xf) \
                    and not self.used[ib] \
                    and not self.used[it]:
                ib += 1
                it += 1
                pattern_length += 1
                if ib >= trial_position:
                    break
            if min_length <= pattern_length <= MAX_PATTERN_LENGTH:
                repeats.append(Repeat(base_position, trial_position, pattern_length, xf))
                last_end = trial_position + pattern_length
        return repeats

    def compress_lr(self, rchirp_song):
        """
        Right-to-left single-pass compression for GoatTracker

        This compression algorithm is the fastest; it can compress even the longest song in less than a second.
        It compresses the song in a manner similar to how a GT song would be constructed; starting from the
        beginning row, it finds the repeats of rows starting at that position that give the best score, and
        then moves to the first gap in the remaining rows and repeats.  If the algorithm does not find any suitable
        repeats at a position, it moves to the next, and the unused rows are put into patterns after all the repeats
        have been found.

        :param rchirp_song: RChirp song to compress
        :type rchirp_song: rchirp.RChirpSong
        :return: rchirp_song with compression information added
        :rtype: rchirp.RChirpSong
        """
        min_length = self.get_option('min_pattern_length', 126)
        rchirp_song.patterns = []  # Get rid of any patterns from previous compression
        for iv, v in enumerate(rchirp_song.voices):
            filled_rows = v.make_filled_rows()
            self.used = [False for r in filled_rows]
            n_rows = len(filled_rows)
            order = {}
            for i in range(n_rows - min_length):
                if self.used[i]:
                    continue
                repeats = self.find_repeats_starting_at(i, filled_rows)
                while len(repeats) > 0:
                    best_repeats = self.find_best_repeats(repeats)
                    if len(best_repeats) > 0:
                        r0 = best_repeats[0]
                        rchirp_song.patterns.append(RChirpPattern(filled_rows[r0.start_row: r0.start_row + r0.length]))
                        pattern_index = len(rchirp_song.patterns) - 1
                        order = self.apply_pattern(pattern_index, best_repeats, order)
                        repeats = self.trim_repeats(repeats)
            while any(not u for u in self.used):
                gap_start = next(iu for iu, u in enumerate(self.used) if not u)
                gap_end = gap_start
                while gap_end < n_rows and not self.used[gap_end]:
                    gap_end += 1
                    if gap_end - gap_start >= MAX_PATTERN_LENGTH:
                        break
                tmp_patt = RChirpPattern(filled_rows[gap_start: gap_end])
                pattern_index = self.add_rchirp_pattern_to_song(rchirp_song, tmp_patt)
                order[gap_start] = (pattern_index, 0)
                for ig in range(gap_start, gap_end):
                    self.used[ig] = True
            assert all(self.used), "Not all rows were used!"
            if not self.validate_orderlist(rchirp_song.patterns, order, len(filled_rows)):
                exit('Orderlist mismatch')
            rchirp_song.voices[iv].orderlist = self.make_orderlist(order)
        rchirp_song.compressed = True
        return rchirp_song


def validate_gt_limits(rchirp_song):
    n_patterns = len(rchirp_song.patterns)
    if n_patterns > goat_tracker.GT_MAX_PATTERNS_PER_SONG:
        print(f'Too many patterns: {n_patterns}', file=sys.stderr)
        return False
    for iv, v in enumerate(rchirp_song.voices):
        orderlist_length = get_gt_orderlist_length(v.orderlist)
        if orderlist_length > goat_tracker.GT_MAX_ELM_PER_ORDERLIST:
            print(f'Orderlist too long in voice {iv+1}: {orderlist_length} bytes', file=sys.stderr)
            return False
    for ip, p in enumerate(rchirp_song.patterns):
        if len(p.rows) + 1 > goat_tracker.GT_MAX_ROWS_PER_PATTERN:
            print(f'Pattern {ip} too long: {len(p.rows)} rows', file=sys.stderr)
            return False
    return True


def get_gt_orderlist_length(orderlist):
    """
    Calculates the length of the orderlist in the GoatTracker .sng file.
    A simple pattern with no transposition played once requires 1 entry
    If there is a transposition change, that adds another entry
    Multiple repeats add one entry unless there are more than 16, in which case
    2 bytes are added per 16 repeats; one for the repeat number and another for the
    pattern number (none is needed for transposition and it cannot change for repeats).
    :param orderlist: An orderlist from a voice
    :type orderlist: rchirp.RChirpOrderlist
    :return: Number of entries required for the GoatTracker orderlist
    :rtype: int
    """
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


GT_PATTERN_OVERHEAD = 5


def estimate_song_size(rchirp_song):
    total = GT_PATTERN_OVERHEAD * len(rchirp_song.patterns)
    total += sum(len(p.rows) for p in rchirp_song.patterns)
    total += sum(len(v.orderlist) for v in rchirp_song.voices)
    return total
