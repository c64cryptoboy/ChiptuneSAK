# Constants for ChiptuneSAK
#

import os
from fractions import Fraction
from dataclasses import dataclass
from pathlib import Path
from math import log2
from chiptunesak.errors import *


# Version information.  Update BUILD_VERSION with every significant bugfix;
# update MINOR_VERSION with every feature addition
MAJOR_VERSION = 0
MINOR_VERSION = 6
BUILD_VERSION = 0

CHIPTUNESAK_VERSION = f"{MAJOR_VERSION}.{MINOR_VERSION}.{BUILD_VERSION}"
CHIPTUNESAK_RELEASE = f"{MAJOR_VERSION}.{MINOR_VERSION}"

BIG_NUMBER = 0xFFFFFFFF

DEFAULT_MIDI_PPQN = 960
DEFAULT_ARCH = 'NTSC-C64'

C0_MIDI_NUM = 12
C4_MIDI_NUM = 60
A4_MIDI_NUM = C4_MIDI_NUM + 9
CONCERT_A = 440.0


PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

KEYS = {'major': ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B'],
        'minor': ['Am', 'Bbm', 'Bm', 'Cm', 'C#m', 'Dm', 'Ebm', 'Em', 'Fm', 'F#m', 'Gm', 'G#m']
        }

DURATIONS = {
    'US': {
        Fraction(8, 1): 'double whole', Fraction(6, 1): 'dotted whole', Fraction(4, 1): 'whole',
        Fraction(3, 1): 'dotted half', Fraction(2, 1): 'half', Fraction(4, 3): 'half triplet',
        Fraction(3, 2): 'dotted quarter', Fraction(1, 1): 'quarter', Fraction(3, 4): 'dotted eighth',
        Fraction(2, 3): 'quarter triplet', Fraction(1, 2): 'eighth', Fraction(3, 8): 'dotted sixteenth',
        Fraction(1, 3): 'eighth triplet', Fraction(1, 4): 'sixteenth',
        Fraction(3, 16): 'dotted thirty-second', Fraction(1, 6): 'sixteenth triplet',
        Fraction(1, 8): 'thirty-second', Fraction(3, 32): 'dotted sixty-fourth',
        Fraction(1, 12): 'thirty-second triplet', Fraction(1, 16): 'sixty-fourth',
        Fraction(1, 24): 'sixty-fourth triplet'
    },
    'UK': {
        Fraction(8, 1): 'breve', Fraction(6, 1): 'dotted semibreve', Fraction(4, 1): 'semibreve',
        Fraction(3, 1): 'dotted minim', Fraction(2, 1): 'minim', Fraction(4, 3): 'minim triplet',
        Fraction(3, 2): 'dotted crochet', Fraction(1, 1): 'crochet', Fraction(3, 4): 'dotted quaver',
        Fraction(2, 3): 'crochet triplet', Fraction(1, 2): 'quaver', Fraction(3, 8): 'dotted semiquaver',
        Fraction(1, 3): 'quaver triplet', Fraction(1, 4): 'semiquaver', Fraction(3, 16): 'dotted demisemiquaver',
        Fraction(1, 6): 'semiquaver triplet', Fraction(1, 8): 'demisemiquaver',
        Fraction(3, 32): 'dotted hemidemisemiquaver', Fraction(1, 12): 'demisemiquaver triplet',
        Fraction(1, 16): 'hemidemisemiquaver', Fraction(1, 24): 'hemidemisemiquaver triplet'
    }
}

# Duration fractions are defined in terms of quarter notes
DURATION_STR = {
    '1.': Fraction(6, 1), '1': Fraction(4, 1), '2.': Fraction(3, 1), '2': Fraction(2, 1), '2-3': Fraction(4, 3),
    '4.': Fraction(3, 2), '4': Fraction(1, 1), '8.': Fraction(3, 4), '4-3': Fraction(2, 3),
    '8': Fraction(1, 2), '16.': Fraction(3, 8), '8-3': Fraction(1, 3), '16': Fraction(1, 4),
    '32.': Fraction(3, 16), '16-3': Fraction(1, 6), '32': Fraction(1, 8), '64.': Fraction(3, 32),
    '32-3': Fraction(1, 12), '64': Fraction(1, 16), '64-3': Fraction(1, 24)
}

# Commodore Constants:
BASIC_START_C64 = 2049   # $0801
BASIC_START_C128 = 7169  # $1C01

BASIC_LINE_MAX_C64 = 80    # 2 lines of 40 col
BASIC_LINE_MAX_VIC20 = 88  # 4 lines of 22 col
BASIC_LINE_MAX_C128 = 160  # 4 lines of 40 col


@dataclass(frozen=True)
class ArchDescription:
    system_clock: int
    cycles_per_line: int
    lines_per_frame: int
    visible_lines: int

    @property
    def cycles_per_frame(self):
        return self.lines_per_frame * self.cycles_per_line

    @property
    def frame_rate(self):
        return self.system_clock / self.cycles_per_frame

    @property
    # e.g., 'PAL-C64' is ~19.95ms
    def ms_per_frame(self):
        return 1000. / self.frame_rate

    @property
    def blank_lines(self):
        return self.lines_per_frame - self.visible_lines


# Someday this will hopefully have settings for Atari Pokey chip, the NES RP2A03 (NTSC) and RP2A07
# (PAL) chips, etc.
ARCH = {
    # NTSC C64 and C128 (1Mhz mode)
    'NTSC-C64': ArchDescription(system_clock=1022727,     # The "new" NTSC 6567R8
                                cycles_per_line=65,
                                lines_per_frame=263,
                                visible_lines=235),
    # Old NTSC C64 and C128 (1Mhz mode)
    'NTSC-R56A': ArchDescription(system_clock=1022727,    # The "old" NTSC 6567R56A
                                 cycles_per_line=64,
                                 lines_per_frame=262,
                                 visible_lines=234),
    # PAL C64 and C128 (1Mhz mode)
    'PAL-C64': ArchDescription(system_clock=985248,       # 6569 chip
                               cycles_per_line=63,
                               lines_per_frame=312,
                               visible_lines=284),
    'NTSC-VIC20': ArchDescription(system_clock=1022727,   # 6560-101 chip
                                  cycles_per_line=65,
                                  lines_per_frame=261,
                                  visible_lines=233),
    'PAL-VIC20': ArchDescription(system_clock=1108405,    # 6561-101 chip
                                 cycles_per_line=71,
                                 lines_per_frame=312,
                                 visible_lines=284),
}


def midi_num_to_freq(midi_num, cents=0, tuning=CONCERT_A):
    """
    Convert a midi number into its frequency

    :param midi_num: midi number
    :type midi_num: int
    :param tuning: frequency, defaults to CONCERT_A
    :type tuning: float, optional
    :return: frequency for midi number
    :rtype: float
    """
    return tuning * pow(2, (midi_num + cents / 100 - A4_MIDI_NUM) / 12)


def midi_num_to_freq_arch(midi_num, cents=0, arch=DEFAULT_ARCH, tuning=CONCERT_A):
    """
    Convert a pitch frequency into a frequency for a particular architecture (e.g. PAL C64)

    :param midi_num: midi note number
    :type midi_num: int
    :param architecture: Architecture description string
    :type architecture: str
    :return: int frequency for arch
    :rtype: int
    """
    if arch not in ('NTSC-C64', 'PAL-C64'):
        raise ChiptuneSAKValueError("Error: arch type not supported for freq conversion")
    # ref: https://codebase64.org/doku.php?id=base:how_to_calculate_your_own_sid_frequency_table
    # SID oscillator is 24-bit (phase-accumulating design)
    return round((0x1000000 / ARCH[arch].system_clock) * midi_num_to_freq(midi_num, cents, tuning))


def freq_to_midi_num(freq, tuning=CONCERT_A):
    """
    Converts a frequency in Hz to a midi number and an offset from the midi pitch in cents.
    The cent is musical term indicating an small change in pitch; 100 cents is a semitone.
    Positive cents means the frequency is sharp relative to the midi note;
    Negative cents means the frequency is flat relative to the midi note.

    :param freq: Frequency, in Hz
    :type freq: float
    :param tuning: pitch of A4
    :type tuning: float
    :return: (midi_num, cents)
    :rtype: tuple of int, int
    """

    # SID oscillator val 0 is legit on a C64, but invites log(0) badness
    if freq <= 0:
        raise ChiptuneSAKValueError("Error: Illegal frequency %d" % freq)

    midi_num_float = (log2(freq) - log2(tuning)) * 12. + A4_MIDI_NUM
    midi_num = int(round(midi_num_float))
    cents = int(round((midi_num_float - midi_num) * 100))
    return (midi_num, cents)


def freq_arch_to_midi_num(freq_arch, arch=DEFAULT_ARCH, tuning=CONCERT_A):
    """
    Converts a particular frequency in an architecture to (midi_num, cents)

    :param freq_arch: frequency as specified in the architecture
    :type freq_arch: int
    :param arch: Architecture description string
    :type arch: str
    :return: midi_num, cents
    :rtype: (int, int)
    """
    if arch not in ('NTSC-C64', 'PAL-C64'):
        raise ChiptuneSAKValueError("Error: arch type not supported for freq conversion")

    freq = freq_arch_to_freq(freq_arch, arch)

    return freq_to_midi_num(freq, tuning)


def freq_arch_to_freq(freq_arch, arch=DEFAULT_ARCH):
    """
    Converts a architecture-based frequency into its true audio frequency

    :param freq_arch: frequency as specified in the architecture
    :type freq_arch: int
    :param arch: Architecture description string, defaults to 'NTSC-C64'
    :type arch: str, optional
    :return: frequency
    :rtype: int
    """
    if arch not in ('NTSC-C64', 'PAL-C64'):
        raise ChiptuneSAKValueError("Error: arch type not supported for freq conversion")

    return freq_arch * ARCH[arch].system_clock / 0x1000000


def freq_to_freq_arch(freq, arch=DEFAULT_ARCH):
    """
    Converts an audio frequency into an architecture-based frequency
    (e.g., a SID oscillator freq)

    :param freq: an audio frequency
    :type freq: int
    :param arch: Architecture description string, defaults to 'NTSC-C64'
    :type arch: str, optional
    :return: frequency as specified in the architecture
    :rtype: int
    """
    if arch not in ('NTSC-C64', 'PAL-C64'):
        raise ChiptuneSAKValueError("Error: arch type not supported for freq conversion")

    return freq * 0x1000000 / ARCH[arch].system_clock


def project_to_absolute_path(file_path):
    """Returns project root folder"""
    return os.path.normpath(os.path.join(Path(__file__).parent.parent.absolute(), file_path))
