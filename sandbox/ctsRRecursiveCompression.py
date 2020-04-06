# Recursive Compression experiments (in progress...)

# TODO:
# Write check on dictionary that patterns don't repeat values, don't overlap, etc.

import copy

MIN_REUSE_FOR_PAT = 2 # must have at least this many occurrences to be promoted to a pattern
MAX_PAT_LEN = 10
MIN_PAT_LEN = 5

# these are overriden in config()
ALLOW_TRANSPOSE = True
TRANSPOSE_MAX = 14   # 6 wholesteps
TRANSPOSE_MIN = -15  # 6.5 wholesteps

GT_MAX_ROWS_PER_PATTERN = 128 # refactor this out

data = '' # chars for now, rows later

DEBUG = False

results = []

class Piece:
    def __init__(self, start_index, end_index):
        self.start_index = start_index
        self.end_index = end_index  # inclusive

    def __copy__(self):
        return Piece(self.start_index, self.end_index)

    def width(self):
        return self.end_index - self.start_index + 1

    def __str__(self):
        return f'{self.start_index} to {self.end_index}'

    def __eq__(self, other):
        return self.start_index == other.start_index and self.end_index == other.end_index

    def __ne__(self, other):
        return not self.__eq__(other)

    def contains_index(self, index):
        return self.start_index <= index <= self.end_index


class Pieces():
    def __init__(self):
        self.pieces = [] # list of ordered Piece instances

    def __len__(self):
        return len(self.pieces)

    def __getitem__(self, index):
        return self.pieces[index]

    def __str__(self):
        return ', '.join(s.__str__() for s in self.pieces)

    def piece_width_sum(self):
        sum = 0
        for piece in self.pieces:
            sum += piece.width()
        return sum

    def piece_containing_index(self, search_index):
        # potential future optimization:
        #    if len(self.pieces) > some size threshold, switch over to a binary search
        #    something like this:
        #       https://stackoverflow.com/questions/38346013/binary-search-in-a-python-list
        #    but recursively passing indexes instead of unnecessary costly slice copies
        for piece_index in range(len(self.pieces)):
            if self.pieces[piece_index].contains_index(search_index):
                return piece_index
        return None

    def append(self, piece):
        self.pieces.append(piece)

    def __iadd__(self, piece):
        self.pieces.append(piece)
        return self

    def clone(self):   # too lazy to properly implement __deepcopy__(self, memo)
        return_val = Pieces()
        return_val_pieces = return_val.pieces
        for piece in self.pieces:
            return_val_pieces.append(piece.__copy__())
        return return_val

    def validate(self):
        curr_index = -1
        for piece in self.pieces:
            if not (isinstance(piece.start_index, int) and isinstance(piece.end_index, int)):
                raise Exception("Error: ints required for piece start/end indexes")
            if piece.end_index <= piece.start_index:
                raise Exception("Error: piece end index must be >= start index")
            if piece.start_index < curr_index:
                raise Exception("Error: pieces are not in order")  
            curr_index = piece.start_index


class Pattern:
    def __init__(self, start_index, end_index):
        self.start_index = start_index
        self.end_index = end_index  # inclusive
        self.other_start_indexes = []

        self.debug_add_order = -1

    def __lt__(self, other):
         return self.start_index < other.start_index

    def __copy__(self):
        new_copy = Pattern(self.start_index, self.end_index)
        new_copy.other_start_indexes = self.other_start_indexes.copy()

        new_copy.debug_add_order = self.debug_add_order

        return new_copy

    def __str__(self):
        #return f'{self.start_index} to {self.end_index} {self.other_start_indexes}'
        return f'{self.debug_add_order}:{self.start_index} to {self.end_index} {self.other_start_indexes}'

    def append(self, start_index):
        self.other_start_indexes.append(start_index)

    def __iadd__(self, start_index):
        self.other_start_indexes.append(start_index)
        return self

    def width(self):
        return self.end_index - self.start_index + 1

    def repeated(self):
        return len(self.other_start_indexes) > 0


def patterns_to_string(patterns_dict):
    result = [] # my comprehension's not working, so doing this the long way
    for key in sorted(patterns_dict):
        result.append("%s" % patterns_dict[key])
    return ', '.join(result)


def config(target):
    global ALLOW_TRANSPOSE, TRANSPOSE_MAX, TRANSPOSE_MIN

    if target == 'gt': # if goattracker
        ALLOW_TRANSPOSE = True
        TRANSPOSE_MAX = 14
        TRANSPOSE_MIN = -15
    elif target == '': # if sidwizard (no orderlist-based transpositions supported)
        ALLOW_TRANSPOSE = False
        TRANSPOSE_MAX = TRANSPOSE_MIN = 0


# Desired functionality:
# A repetition of length n will sometimes give less coverage than a repetition with
# length n-m; factoring out the length n patterns will block the better n-m patterns.
# This implies that the recursive tree search should sometimes skip viable, larger patterns.
# Example:  Suppose the data has A and B, 2 different kinds of repeats of length n.
# Further suppose A can be matched 3 times, and B 3 times, but if either is matched
# first, the other can only achieve 2 matches.
# Recursively explore...
# 1) no matches of length n (goes on to n-1)
# 2) 3 'A' matches of length n (goes on to n-1 with that n-length pattern in place)
# 2) 3 'B' matches of length n (goes on to n-1 with that n-length pattern in place)
# 4) 3 'A' matches and 2 'B' matches (goes on to n-1 with those two n-length patterns in place)
# 5) 3 'B' matches and 2 'A' matches (goes on to n-1 with those two n-length patterns in place)

# Simulating the recursion that I'm after:
#
# call size n with [] // starts with empty pattern list
# 	[Ax3]: // Found n-size pattern "A" 3 times
# 		call size n with [Ax3]:
# 			[Ax3, Bx2]:	 // B is there 3 times, but one match overlaps with A, so we only get 2 times
# 				call size n with [Ax3, Bx2]:
# 					no size n patterns found, so we never call size n
# 				call size n-1 with [Ax3, Bx2]:
# 					. . .
# 		call size n-1 with [Ax3]: // go on to n-1 without exploring size n further
# 			. . .
# 	[Bx3]: // If we don't match pattern "A" first, we can find "B" 3 times, and "A" 2 times
# 		call size n with [Bx3]:
# 			[Bx3, Ax2]:
# 				call size n with [Bx3, Ax2]:
# 					no size n patterns found, so we never call size n
# 				call size n-1 with [Bx3, Ax2]:
# 					. . .
# 		call size n-1 with [Bx3]:
# 			. . .
# 	[]: call size n-1  // skip matching on size n
# 		. . .


# bootstrap recursive search
def find_patterns(pieces):
    find_pats_with_size_le_n(MAX_PAT_LEN, pieces, {})


def add_solution(n, pieces, patterns):
    global results

    # convert remaining pieces to (non-repeating) patterns

    pattern_bytes = 0
    for pattern in patterns.values():
        pattern_bytes += pattern.width()

    unpatterned_count = 0
    for piece in pieces:
        width = piece.width()
        unpatterned_count += width
        pattern_bytes += width

        # convert piece into 1 or more patterns
        while width > GT_MAX_ROWS_PER_PATTERN:
            patterns[piece.start_index] = \
                Pattern(piece.start_index, piece.start_index+GT_MAX_ROWS_PER_PATTERN-1)
            patterns[piece.start_index].debug_add_order = len(patterns)    
            piece.start_index += GT_MAX_ROWS_PER_PATTERN
            width -= GT_MAX_ROWS_PER_PATTERN
        patterns[piece.start_index] = Pattern(piece.start_index, piece.end_index)
        patterns[piece.start_index].debug_add_order = len(patterns) 

    percent_coverage = (len(data) - unpatterned_count) / len(data) * 100
    percent_new_size = (pattern_bytes / len(data)) * 100

    if len(results) == 0 or results[-1][0] > percent_new_size:
        results.append((percent_new_size, percent_coverage, patterns))

        reduction_str = "{0:.2f}% of original".format(percent_new_size)
        coverage_str = "{0:.2f}% coverage".format(percent_coverage)
        patterns_str = ', '.join(str(pattern) for pattern in sorted(patterns.values()))
        print('%s, %s\n%s\n' % (reduction_str, coverage_str, patterns_str))


# Recursive search
def find_pats_with_size_le_n(n, pieces, patterns):
    # if we reached the bottom of a particular search path, update (global) results
    if n <= MIN_PAT_LEN:
        add_solution(n, pieces, patterns)
        return

    # Find candidate patterns of length n (from left to right) in each piece to
    # search for, starting from current pattern/position through the patterns "to the right"

    size_n_seen_list = set()

    # iterate over pieces
    for piece_index in range(len(pieces)):
        piece = pieces[piece_index]
        piece_start_index = piece.start_index
        piece_end_index = piece.end_index

        if piece.width() < n:
            continue
        
        # for this piece, find all the candidate patterns
        for i in range(piece_start_index, piece_end_index-n+2):
            cp = data[i:i+n]  # assign candidate pattern to look for
            if cp not in size_n_seen_list: # but only if we've not seen this cp before   
                size_n_seen_list.add(cp)
            
                # cp_matches comes from the pieces we started with at this n level
                # (not new_pieces).  That way, a second or later match of size-n can have
                # a chance to be matches before the 1st size-n match we encountered.
                # the i+1 means don't match the candidate pattern at the same index 
                # that we harvested it from   
                cp_matches = find_candidate_pattern_matches(n, pieces, cp, piece_index, i+1)
                # print(cp_matches) DEBUG
                
                if cp_matches is not None: # if this is a recursive path worth exploring

                    (new_pieces, new_patterns) = make_new_pieces(cp_matches, n, pieces.clone(), copy.deepcopy(patterns))

                    if DEBUG: print('length %d pattern "%s" found' % (n, cp))
                    if 1 == 1: #debug point
                        pass

                    # with this new pattern in place, continue search this size n window
                    if DEBUG: print("n=%d looking for more len n patterns" % n)
                    find_pats_with_size_le_n(n, new_pieces, new_patterns)
                    
                    # with this new pattern in place, skip other size n matches, and go on to n-1
                    # prevents a worse, larger match not to block a smaller, better match (more coverage)
                    # Note: this is the only recursive call that can reach n=MIN_PAT_LEN and store
                    # a potential solution
                    if DEBUG: print("n=%d keep len n patten(s), but move to n-1" % n)
                    find_pats_with_size_le_n(n-1, new_pieces, new_patterns)
                else:
                    pass
                    if DEBUG: print('length %d pattern "%s" not found' % (n, cp))
        # Now it's time to search where skipping any pattern creation of size n, again to prevent
        # a worse, larger match from blocking a smaller, better match.
        # However, don't bother if n-1 is MIN_PAT_LEN, since that's not exploring anything
        if 1 == 1: #debug point
            pass

        if DEBUG: print("n=%d skip len n pattern search, move to n-1" % n)
        if n > MIN_PAT_LEN+1:
            find_pats_with_size_le_n(n-1, pieces.clone(), copy.deepcopy(patterns))

    return # recursive calls return nothing, easier design that way


# cloned pieces and patterns sent to make_new_pieces, and they will be updated
def make_new_pieces(cp_matches, n, new_pieces, new_patterns):
    # we have a list of non-overlapping starting indexes for the candidate pattern
    # make new patterns based on these matches

    for i, match_index in enumerate(cp_matches):                  
        index_of_piece_to_mod = new_pieces.piece_containing_index(match_index)
        assert index_of_piece_to_mod is not None, \
            "Error: couldn't find the piece that we previously found a match within"

        tmp_pieces = []
        piece_to_mod = new_pieces[index_of_piece_to_mod]

        # possibly make a piece left of the match
        if match_index > piece_to_mod.start_index:
            tmp_pieces.append(Piece(piece_to_mod.start_index, match_index-1))

        # pull out a pattern
        if i == 0:
            new_patterns[match_index] = Pattern(match_index, match_index+n-1)
            new_patterns[match_index].debug_add_order = len(new_patterns)
            new_pattern_index = match_index
        else:
            new_patterns[new_pattern_index].append(match_index)

        # possibly make a piece right of the match
        if piece_to_mod.end_index > match_index+n-1:
            tmp_pieces.append(Piece(match_index+n, piece_to_mod.end_index))

        # replace the old piece with 0 to 2 new pieces
        #    this achieves a list insertion via a slice (which flattens the lists, so no nesting)
        new_pieces.pieces[index_of_piece_to_mod:index_of_piece_to_mod+1] = tmp_pieces

    # DEBUG:
    #print("candidate match indexes: %s" % cp_matches)
    #print("updated pieces %s" % new_pieces)
    #print("updated patterns %s" % patterns_to_string(new_patterns))

    return (new_pieces, new_patterns)


# find the candidate patterns that exist at least MIN_REUSE_FOR_PAT times.
# these are candidates for further recursion
def find_candidate_pattern_matches(n, pieces, cp, starting_piece_index, offset_for_starting_piece):
    # on first pattern, don't search in the candidate pattern's position            
    #cp_matches = [(starting_piece_index, offset_for_starting_piece-1, offset_for_starting_piece + n-1-1)]
    cp_matches = [offset_for_starting_piece-1]

    offset = offset_for_starting_piece

    # iterate over pieces, starting from current piece through pieces "to the right"
    for piece_index in range(starting_piece_index, len(pieces)):

        # the first piece searched doesn't begin at offset zero (skipping the source of the
        # candidate pattern), but start at 0 for the other pieces
        if piece_index > starting_piece_index:
            offset = 0

        piece = pieces[piece_index]
        piece_start_index = piece.start_index
        piece_end_index = piece.end_index

        # skip if piece is too small for matching candidate pattern
        if piece_start_index + offset + n-1 > piece_end_index:    
            continue
        
        for i in range(piece_start_index + offset, piece_end_index-n+2):
            if matches(data[i:i+n], cp):   
                # cp_matches.append((piece_index, i, i+n-1))
                cp_matches.append(i)

    cp_matches = deoverlap_matches(cp_matches, n)

    if len(cp_matches) >= MIN_REUSE_FOR_PAT:
        # print(cp_matches) # DEBUG
        return cp_matches
    
    return None


def matches(data1, data2):
    assert len(data1) == len(data2), "Error: call to matches is broken, fix it"

    if data1[0] == data2[0]:
        for i in range(1, len(data1)): # check for match
            if data1[i] != data2[i]:
                return False
    else:
        if not ALLOW_TRANSPOSE: # check for transposition match
            return False
        offset = ord(data2[0])-ord(data1[0])
        if not (TRANSPOSE_MIN <= offset <= TRANSPOSE_MAX):
            return False
        for i in range(1, len(data1)):
            if ord(data1[i])+offset != ord(data2[i]):
                return False        

    return True


# Given a list of starting indexes and match size n, we can tell if some of them will overlap
# this method pics a sublist of indexes that doesn't overlap
# TODO:  This will be a recursive search to pick a sublist with a maximum number of non-overlapping
#        matches.  But for right now, it's just greedy processing (not optimal)
def deoverlap_matches(cp_matches, n):
    overlapping_matches = False
    next_allowed_index = -10000
    for match_index in cp_matches:
        if match_index < next_allowed_index:
            overlapping_matches = True
            #print("DEBUG: OVERLAP DETECTED")
            break
        next_allowed_index = match_index+n

    # TODO: For now, just doing a greedy approach, but changes to a tree approach later
    if overlapping_matches:
        tmp_cp_matches = cp_matches
        cp_matches = []
        next_allowed_index = -10000
        for match_index in tmp_cp_matches:
            if match_index >= next_allowed_index:
                cp_matches.append(match_index)
                next_allowed_index = match_index+n
            else:
                print("DEBUG: Resolved a single pattern's match overlaps from left to right; tree search could do better")

    return cp_matches


def recursive_compress(voices):
    global data 
    data = ''.join(voiceData for voiceData in voices)

    pieces = Pieces()
    # pieces are ranges of data in index order, from which common patterns will be extracted
    # we start with one piece for each voice's data
    curr_pos = 0
    for i in range(0, len(voices)):
        pieces.append(Piece(curr_pos, curr_pos + len(voices[i])-1))
        curr_pos += len(voices[i])

    find_patterns(pieces)

if __name__ == "__main__":
    v1 = "THIS IS A TEST THIS IS TEST TEST THIS IS A TEST"
    v2 = "BTW A TEST THIS IS THIS IS TEST"
    v3 = "DID I MENTION THIS IS A TEST?  YES"
    voices = [v1, v2, v3]

    recursive_compress(voices)

    print("Done")
