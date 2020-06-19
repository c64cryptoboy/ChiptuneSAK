import toolsPath  # noqa
import ctsConstants
import ctsBase

print("midiNum, noteName, Hz, NTSCFreq, NTSCFreqHex, PALFreq, PALFreqHex")
# From C0 to B7.  References:
# - https://www.colincrawley.com/midi-note-to-audio-frequency-calculator/
# - https://gist.github.com/matozoid/18cddcbc9cfade3c455bc6230e1f6da6
for midi_num in range(ctsConstants.C0_MIDI_NUM, ctsConstants.C0_MIDI_NUM + (8 * 12)):
    tuning = ctsConstants.CONCERT_A     # e.g., tuning = 440.11 used by siddump.c
    freq = ctsConstants.midi_num_to_freq(midi_num, tuning)
    ntsc_freq = ctsConstants.midi_num_to_freq_arch(midi_num, 'NTSC-C64', tuning)
    pal_freq = ctsConstants.midi_num_to_freq_arch(midi_num, 'PAL-C64', tuning)

    print(
        '{:3d}, {: <3}, {:8.3f}, {:5d}, {:04X}, {:5d}, {:05X}'.format(
            midi_num, ctsBase.pitch_to_note_name(midi_num), freq, ntsc_freq,
            ntsc_freq, pal_freq, pal_freq)
    )

"""
midiNum, noteName, Hz, NTSCFreq, NTSCFreqHex, PALFreq, PALFreqHex
 12, C0 ,   16.352,   268, 010C,   278, 00116
 13, C#0,   17.324,   284, 011C,   295, 00127
 14, D0 ,   18.354,   301, 012D,   313, 00139
 15, D#0,   19.445,   319, 013F,   331, 0014B
 16, E0 ,   20.602,   338, 0152,   351, 0015F
 17, F0 ,   21.827,   358, 0166,   372, 00174
 18, F#0,   23.125,   379, 017B,   394, 0018A
 19, G0 ,   24.500,   402, 0192,   417, 001A1
 20, G#0,   25.957,   426, 01AA,   442, 001BA
 21, A0 ,   27.500,   451, 01C3,   468, 001D4
 22, A#0,   29.135,   478, 01DE,   496, 001F0
 23, B0 ,   30.868,   506, 01FA,   526, 0020E
 24, C1 ,   32.703,   536, 0218,   557, 0022D
 25, C#1,   34.648,   568, 0238,   590, 0024E
 26, D1 ,   36.708,   602, 025A,   625, 00271
 27, D#1,   38.891,   638, 027E,   662, 00296
 28, E1 ,   41.203,   676, 02A4,   702, 002BE
 29, F1 ,   43.654,   716, 02CC,   743, 002E7
 30, F#1,   46.249,   759, 02F7,   788, 00314
 31, G1 ,   48.999,   804, 0324,   834, 00342
 32, G#1,   51.913,   852, 0354,   884, 00374
 33, A1 ,   55.000,   902, 0386,   937, 003A9
 34, A#1,   58.270,   956, 03BC,   992, 003E0
 35, B1 ,   61.735,  1013, 03F5,  1051, 0041B
 36, C2 ,   65.406,  1073, 0431,  1114, 0045A
 37, C#2,   69.296,  1137, 0471,  1180, 0049C
 38, D2 ,   73.416,  1204, 04B4,  1250, 004E2
 39, D#2,   77.782,  1276, 04FC,  1325, 0052D
 40, E2 ,   82.407,  1352, 0548,  1403, 0057B
 41, F2 ,   87.307,  1432, 0598,  1487, 005CF
 42, F#2,   92.499,  1517, 05ED,  1575, 00627
 43, G2 ,   97.999,  1608, 0648,  1669, 00685
 44, G#2,  103.826,  1703, 06A7,  1768, 006E8
 45, A2 ,  110.000,  1804, 070C,  1873, 00751
 46, A#2,  116.541,  1912, 0778,  1985, 007C1
 47, B2 ,  123.471,  2025, 07E9,  2103, 00837
 48, C3 ,  130.813,  2146, 0862,  2228, 008B4
 49, C#3,  138.591,  2274, 08E2,  2360, 00938
 50, D3 ,  146.832,  2409, 0969,  2500, 009C4
 51, D#3,  155.563,  2552, 09F8,  2649, 00A59
 52, E3 ,  164.814,  2704, 0A90,  2807, 00AF7
 53, F3 ,  174.614,  2864, 0B30,  2973, 00B9D
 54, F#3,  184.997,  3035, 0BDB,  3150, 00C4E
 55, G3 ,  195.998,  3215, 0C8F,  3338, 00D0A
 56, G#3,  207.652,  3406, 0D4E,  3536, 00DD0
 57, A3 ,  220.000,  3609, 0E19,  3746, 00EA2
 58, A#3,  233.082,  3824, 0EF0,  3969, 00F81
 59, B3 ,  246.942,  4051, 0FD3,  4205, 0106D
 60, C4 ,  261.626,  4292, 10C4,  4455, 01167
 61, C#4,  277.183,  4547, 11C3,  4720, 01270
 62, D4 ,  293.665,  4817, 12D1,  5001, 01389
 63, D#4,  311.127,  5104, 13F0,  5298, 014B2
 64, E4 ,  329.628,  5407, 151F,  5613, 015ED
 65, F4 ,  349.228,  5729, 1661,  5947, 0173B
 66, F#4,  369.994,  6070, 17B6,  6300, 0189C
 67, G4 ,  391.995,  6430, 191E,  6675, 01A13
 68, G#4,  415.305,  6813, 1A9D,  7072, 01BA0
 69, A4 ,  440.000,  7218, 1C32,  7493, 01D45
 70, A#4,  466.164,  7647, 1DDF,  7938, 01F02
 71, B4 ,  493.883,  8102, 1FA6,  8410, 020DA
 72, C5 ,  523.251,  8584, 2188,  8910, 022CE
 73, C#5,  554.365,  9094, 2386,  9440, 024E0
 74, D5 ,  587.330,  9635, 25A3, 10001, 02711
 75, D#5,  622.254, 10208, 27E0, 10596, 02964
 76, E5 ,  659.255, 10815, 2A3F, 11226, 02BDA
 77, F5 ,  698.456, 11458, 2CC2, 11894, 02E76
 78, F#5,  739.989, 12139, 2F6B, 12601, 03139
 79, G5 ,  783.991, 12861, 323D, 13350, 03426
 80, G#5,  830.609, 13626, 353A, 14144, 03740
 81, A5 ,  880.000, 14436, 3864, 14985, 03A89
 82, A#5,  932.328, 15294, 3BBE, 15876, 03E04
 83, B5 ,  987.767, 16204, 3F4C, 16820, 041B4
 84, C6 , 1046.502, 17167, 430F, 17820, 0459C
 85, C#6, 1108.731, 18188, 470C, 18880, 049C0
 86, D6 , 1174.659, 19270, 4B46, 20003, 04E23
 87, D#6, 1244.508, 20415, 4FBF, 21192, 052C8
 88, E6 , 1318.510, 21629, 547D, 22452, 057B4
 89, F6 , 1396.913, 22916, 5984, 23787, 05CEB
 90, F#6, 1479.978, 24278, 5ED6, 25202, 06272
 91, G6 , 1567.982, 25722, 647A, 26700, 0684C
 92, G#6, 1661.219, 27251, 6A73, 28288, 06E80
 93, A6 , 1760.000, 28872, 70C8, 29970, 07512
 94, A#6, 1864.655, 30589, 777D, 31752, 07C08
 95, B6 , 1975.533, 32407, 7E97, 33640, 08368
 96, C7 , 2093.005, 34334, 861E, 35641, 08B39
 97, C#7, 2217.461, 36376, 8E18, 37760, 09380
 98, D7 , 2349.318, 38539, 968B, 40005, 09C45
 99, D#7, 2489.016, 40831, 9F7F, 42384, 0A590
100, E7 , 2637.020, 43259, A8FB, 44904, 0AF68
101, F7 , 2793.826, 45831, B307, 47574, 0B9D6
102, F#7, 2959.955, 48556, BDAC, 50403, 0C4E3
103, G7 , 3135.963, 51444, C8F4, 53401, 0D099
104, G#7, 3322.438, 54503, D4E7, 56576, 0DD00
105, A7 , 3520.000, 57743, E18F, 59940, 0EA24
106, A#7, 3729.310, 61177, EEF9, 63504, 0F810
107, B7 , 3951.066, 64815, FD2F, 67280, 106D0
"""
