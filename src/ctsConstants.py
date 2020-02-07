from fractions import Fraction

CHIPTUNESAK_VERSION = "0.13"

PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
DURATIONS = {
    Fraction(6, 1):'dotted whole', Fraction(4, 1):'whole',
    Fraction(3, 1):'dotted half', Fraction(2, 1):'half', Fraction(4, 3):'half triplet',
    Fraction(3, 2):'dotted quarter', Fraction(1, 1):'quarter', Fraction(3, 4):'dotted eighth',
    Fraction(2, 3):'quarter triplet', Fraction(1, 2):'eighth', Fraction(3, 8):'dotted sixteenth',
    Fraction(1, 3):'eighth triplet', Fraction(1, 4):'sixteenth', Fraction(3, 16):'dotted thirty-second',
    Fraction(1, 6):'sixteenth triplet', Fraction(1, 8):'thirty-second', Fraction(3, 32):'dotted sixty-fourth',
    Fraction(1, 12):'thirty-second triplet', Fraction(1, 16):'sixty-fourth', Fraction(1, 24):'sixty-fourth triplet'
}

DURATION_STR = {
    '1.':Fraction(6, 1), '1':Fraction(4, 1), '2.':Fraction(3, 1), '2':Fraction(2, 1), '2-3':Fraction(4, 3),
    '4.':Fraction(3, 2), '4':Fraction(1, 1), '8.':Fraction(3, 4), '4-3':Fraction(2, 3),
    '8':Fraction(1, 2), '16.':Fraction(3, 8), '8-3':Fraction(1, 3), '16':Fraction(1, 4),
    '32.':Fraction(3, 16), '16-3':Fraction(1, 6), '32':Fraction(1, 8), '64.':Fraction(3, 32),
    '32-3':Fraction(1, 12), '64':Fraction(1, 16), '64-3':Fraction(1, 24)
}

# Commodore Constants:

BASIC_START_C64  = 2049 # $0801
BASIC_START_C128 = 7169 # $1C01

# A traditional PAL tracker reasoning anchor point between temporally-unitless rows
# and BPM is that 6 frames per row (a fast speed) is easily tied to 125 BPM.
# This forms the basis of many PAL tracker defaults, and is used when giving simple
# concrete examples of computing tempos.
# Details: 6 frames per row * PAL 20msPerFrame = 0.12 sec per row
# that's 1/0.12 = x=8.333333 rows per sec, so 60 seconds / 0.12 sec per row = 500 rows per min
# 500 rows per min / 125 BPM = 4 rows per quarter note in 4/4
# so a row becomes a 16th note

NTSC_FRAMES_PER_SEC = 59.94
PAL_FRAMES_PER_SEC = 50.0
NTSC_MS_PER_FRAME = 1000 / NTSC_FRAMES_PER_SEC # 16.68335002ms
PAL_MS_PER_FRAME = 1000 / PAL_FRAMES_PER_SEC # 20ms

# GoatTracker constants
# TODO: All of these need to be moved into a combined gt importer and exporter
GT_FILE_HEADER = b'GTS5'
GT_OCTAVE_BASE = -1  # -1 means that in goattracker, middle C (261.63 Hz / note 60) is "C4" 
GT_MAX_SUBTUNES_PER_SONG = 32 # Each subtune gets its own orderlist of patterns
                              # "song" means a collection of independently-playable subtunes
GT_MAX_ELM_PER_ORDERLIST = 255 # at minimum, it must contain the endmark and following byte
GT_MAX_INSTR_PER_SONG = 63
GT_MAX_PATTERNS_PER_SONG = 208 # patterns can be shared across channels and subtunes
GT_MAX_ROWS_PER_PATTERN = 128 # and min rows (not including end marker) is 1
GT_REST = 0xBD # A rest in goattracker means NOP, not rest
GT_KEY_OFF = 0xBE
GT_KEY_ON = 0xBF
GT_OL_RST = 0xFF # order list restart marker
GT_PAT_END = 0xFF # pattern end
