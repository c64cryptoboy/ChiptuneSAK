from fractions import Fraction

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

# Calibrating with PAL default assumptions:
# in PAL, tempo 6 * 20msPerFrame = 0.12 sec per row
# that's 1/0.12 = x=8.333333 rows per sec
# so 60 seconds / 0.12 sec per row = 500 rows per min
# Traditional PAL reasoning anchor point is that 6 frames per row (a fast speed)
# is tied to 125 BPM, where 500 rows per min / 125 BPM = 4 rows per quarter note in 4/4
# a row is then a 16th note

NTSC_FRAMES_PER_SEC = 59.94
PAL_FRAMES_PER_SEC = 50.0
NTSC_MS_PER_FRAME = 1000 / NTSC_FRAMES_PER_SEC # 16.68335002ms
PAL_FRAMES_PER_SEC = 1000 / PAL_FRAMES_PER_SEC # 20ms

