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