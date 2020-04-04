# Recursive Compression experiments (in progress...)


# piece types (since python enums are slow, using constants instead)
UNPROCESSED = 0  # pieces of data not belonging to patterns
PATTERN = 1 # a piece that has been promoted to a pattern
PATTERN_REF = 2 # reference to an earlier-declared pattern

MIN_REUSE_FOR_PAT = 2 # must have at least this many occurrences to be promoted to a pattern
MAX_PAT_LEN = 10
MIN_PAT_LEN = 5

data = '' # chars for now, rows later

class Piece:
    type_decode = ['U', 'P', 'PR']

    def __init__(self, type, start_index, end_index):
        self.type = type
        self.start_index = start_index
        self.end_index = end_index  # inclusive

    def __copy__(self):
        return Piece(self.type, self.start_index, self.end_index)

    def width(self):
        return self.end_index - self.start_index + 1

    def __str__(self):
        return f'({Piece.type_decode[self.type]}, {self.start_index}, {self.end_index})'

    def __eq__(self, other):
        return (self.type == other.type) and (self.start_index == other.start_index) \
            and (self.end_index == other.end_index)

    def __ne__(self, other):
        return not self.__eq__(other)

    def contains_index(self, index):
        return self.start_index <= index <= self.end_index


class Pieces():
    # TODO maintain an unpatterned bytes count (subtracted from)
    # TODO: Add a test that computed unpatterned bytes = the count that's being maintained

    def __init__(self):
        self.pieces = [] # list of ordered Piece instances

    def __len__(self):
        return len(self.pieces)

    def __getitem__(self, index):
        return self.pieces[index]

    def __str__(self):
        return ', '.join(s.__str__() for s in self.pieces)

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

    def clone(self):   # too lazy to properly implement __deepcopy__(self, memo)
        return_val = Pieces()
        return_val_pieces = return_val.pieces
        for piece in self.pieces:
            return_val_pieces.append(piece.__copy__())
        return return_val

    def __iadd__(self, piece):
        self.pieces.append(piece)
        return self

    def validate(self):
        curr_index = -1
        for piece in self.pieces:
            if piece.type not in (UNPROCESSED, PATTERN, PATTERN_REF):
                raise Exception("Error: unrecognized piece type")
            if not (isinstance(piece.start_index, int) and isinstance(piece.end_index, int)):
                raise Exception("Error: ints required for piece start/end indexes")
            if piece.type != PATTERN_REF:
                if piece.end_index <= piece.start_index:
                    raise Exception("Error: piece end index must be > start index")
                if piece.start_index < curr_index:
                    raise Exception("Error: pieces are not in order")  
                curr_index = piece.start_index

# Desired functionality:
# A repetition of length n will sometimes give less coverage than a repetition with
# length n-m; factoring out the length n patterns will block the better n-m patterns.
# This implies that the recursive tree search should sometimes skip viable, larger patterns.
# Example:  Suppose the data has A and B, 2 different kinds of repeats of length n.
# Further suppose A can be matched 3 times, and B 3 times, but if either is matched
# first, the other can only achieve 2 matches.
# Recursively explore...
# 1) no matches of length n (goes on to n-1 with an open playing field)
# 2) 3 'A' matches of length n (goes on to n-1 with that n-length pattern in place)
# 2) 3 'B' matches of length n (goes on to n-1 with that n-length pattern in place)
# 4) 3 'A' matches and 2 'B' matches (goes on to n-1 with those two n-length patterns in place)
# 5) 3 'B' matches and 2 'A' matches (goes on to n-1 with those two n-length patterns in place)

# Recursive search
def find_pats_with_size_le_n(n, pieces):
    if n <= MIN_PAT_LEN:
        return

    size_n_seen_list = set()
    # Find candidate patterns of length n (from left to right) in each piece to
    # search for, starting from current pattern/position through the patterns "to the right"

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
            
                # the i+1 means don't match the candidate pattern at the same index 
                # that we harvested it from   
                cp_matches = find_candidate_pattern_matches(n, pieces, cp, piece_index, i+1)
                if cp_matches is not None: # if this is a recursive path worth exploring
                    new_pieces = make_new_pieces(cp_matches, n, pieces)

                    exit("early exit")

                    # TODO: Get some recursion going here

    # propegate up state that has minimum unpatterned chars remaining
    return # blah


def make_new_pieces(cp_matches, n, pieces):
    # we have a list of non-overlapping starting indexes for the candidate pattern
    # make new patterns based on these matches
    new_pieces = pieces.clone()
    for i, match_index in enumerate(cp_matches):                  
        index_of_piece_to_mod = new_pieces.piece_containing_index(match_index)
        if index_of_piece_to_mod is None:
            raise Exception("Error: couldn't find the piece that we previously found a match within")

        tmp_pieces = []
        piece_to_mod = new_pieces[index_of_piece_to_mod]
        if piece_to_mod.type != UNPROCESSED:
            raise Exception("Error: we shouldn't have found a match in data that's already a pattern")

        if match_index > piece_to_mod.start_index:
            tmp_pieces.append(Piece(UNPROCESSED, piece_to_mod.start_index, match_index-1))

        if i == 0:
            start_of_pattern = match_index
            end_of_pattern = match_index+n-1
            tmp_pieces.append(Piece(PATTERN, start_of_pattern, end_of_pattern))
        else:
            tmp_pieces.append(Piece(PATTERN_REF, start_of_pattern, end_of_pattern))

        if piece_to_mod.end_index > match_index+n-1:
            tmp_pieces.append(Piece(UNPROCESSED, match_index+n, piece_to_mod.end_index))

        # this achieves a list insertion via a slice (which flattens the lists, so no nesting)
        new_pieces.pieces[index_of_piece_to_mod:index_of_piece_to_mod+1] = tmp_pieces

    #print(new_pieces)
    return new_pieces


# find the candidate patterns that exist at least MIN_REUSE_FOR_PAT times.
# these are candidates for further recursion
def find_candidate_pattern_matches(n, pieces, cp, starting_piece_index, offset_for_starting_piece):
    # on first pattern, don't search in the candidate pattern's position            
    #cp_matches = [(starting_piece_index, offset_for_starting_piece-1, offset_for_starting_piece + n-1-1)]
    cp_matches = [offset_for_starting_piece-1]

    offset = offset_for_starting_piece

    # iterate over pieces, starting from current piece through pieces "to the right"
    for piece_index in range(starting_piece_index, len(pieces)):
        if pieces[piece_index].type != UNPROCESSED:
            continue

        # after the initial pattern we check, all subsequent patterns (to the right) begin
        # their searches at 0
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
        print(cp_matches)
        return cp_matches
    
    return None


def matches(data1, data2):
    assert len(data1) == len(data2), "Error: call to matches is broken, fix it"

    if data1[0] == data2[0]:
        for i in range(1, len(data1)): # check for match
            if data1[i] != data2[i]:
                return False
    else: 
        offset = ord(data2[0])-ord(data1[0]) # check for transposition match
        for i in range(1, len(data1)):
            if ord(data1[i])+offset != ord(data2[i]):
                return False        

    return True


# Given a list of starting indexes and match size n, we can tell if some of them will overlap
# this method pics a sublist of indexes that doen't overlap
# TODO:  This will be a recursive search to pick a sublist with a maximum number of non-overlapping
#        matches.  But for right now, it's just greedy processing (not optimal)
def deoverlap_matches(cp_matches, n):
    overlapping_matches = False
    next_allowed_index = -10000
    for match_index in cp_matches:
        if match_index < next_allowed_index:
            overlapping_matches = True
            print("DEBUG: OVERLAP DETECTED, build some recursion to find something more optimal")
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
                print("DEBUG: REMOVED OVERLAPPING MATCH")

    return cp_matches


def recursive_compress(voices):
    global data 
    data = ''.join(voiceData for voiceData in voices)

    pieces = Pieces()
    # pieces are ranges of data in index order, from which common patterns will be extracted
    # we start with one piece for each voice's data
    curr_pos = 0
    for i in range(0, len(voices)):
        pieces.append(Piece(UNPROCESSED, curr_pos, curr_pos + len(voices[i])-1))
        curr_pos += len(voices[i])

    find_pats_with_size_le_n(MAX_PAT_LEN, pieces)


if __name__ == "__main__":
    v1 = "THIS IS A TEST THIS IS TEST TEST THIS IS A TEST"
    v2 = "BTW A TEST THIS IS THIS IS TEST"
    v3 = "DID I MENTION THIS IS A TEST?  YES"
    voices = [v1, v2, v3]

    recursive_compress(voices)

    print("Done")
