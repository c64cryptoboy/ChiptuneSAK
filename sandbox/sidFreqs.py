from math import log10, floor
from chiptunesak import constants
from chiptunesak import base


def get_freqs():
    freqs = []

    # From C0 to B7.  References:
    # - https://www.colincrawley.com/midi-note-to-audio-frequency-calculator/
    # - https://gist.github.com/matozoid/18cddcbc9cfade3c455bc6230e1f6da6
    for midi_num in range(constants.C0_MIDI_NUM, constants.C0_MIDI_NUM + (8 * 12)):
        tuning = constants.CONCERT_A     # e.g., tuning = 440.11 used by siddump.c
        freq = constants.midi_num_to_freq(midi_num, 0, tuning)
        ntsc_freq = constants.midi_num_to_freq_arch(midi_num, 0, 'NTSC-C64', tuning)
        pal_freq = constants.midi_num_to_freq_arch(midi_num, 0, 'PAL-C64', tuning)

        freq = {
            'midiNum' : midi_num,
            'noteName' : base.pitch_to_note_name(midi_num),
            'Hz' : round(freq * 1000) / 1000,
            'NTSCFreq' : ntsc_freq,
            'NTSCFreqHex' : '%04X' % ntsc_freq,
            'PALFreq' : pal_freq,
            'PALFreqHex' : '%04X' % pal_freq}
        freqs.append(freq)  

    return freqs


def print_ntsc_pal_comparison(freqs):
    print("midiNum, noteName, Hz, NTSCFreq, NTSCFreqHex, PALFreq, PALFreqHex")

    for freq in freqs:
        print('{:3d}, {: <3}, {:8.3f}, {:5d}, ${: >4}, {:5d}, ${: >4}'.format(
            freq['midiNum'], freq['noteName'], freq['Hz'], freq['NTSCFreq'],
            freq['NTSCFreqHex'], freq['PALFreq'], freq['PALFreqHex']))


# Create tables for CBM prg Studio
def print_asm_tables(freqs, ntsc=True):
    _print_asm_tables(freqs, ntsc, True) # lo bytes
    _print_asm_tables(freqs, ntsc, False) # hi bytes


def _print_asm_tables(freqs, ntsc, lo):
    if lo:
        lo_or_hi = 'lo'
    else:
        lo_or_hi = 'hi'
    if ntsc:
        ntsc_or_pal = 'NTSC'
    else:
        ntsc_or_pal = 'PAL'
    print('; %s frequencies: %s bytes' % (ntsc_or_pal, lo_or_hi))

    for i in range(8):
        line = []
        for j in range(i*12, (i+1)*12):
            if ntsc:
                freq = freqs[j]['NTSCFreq']
            else:
                freq = freqs[j]['PALFreq']
            if lo:
                freq %= 256
            else:
                freq //= 256
            if not ntsc and freqs[j]['noteName'] == 'B7':
                freq = 0xff # set PAL B7 as high as we can go
            line.append('$%02x' % freq)
        print('data %s ; %s-%s' % (
            ','.join(line), freqs[i * 12]['noteName'], freqs[(i + 1) * 12 - 1]['noteName']))
    print()


""" for debugging:
print("\n")
for ntsc_f in range(269, -1, -1):  # C0 to D0 in NTSC freq for 440 tuning
#for ntsc_f in range(65000, 65536):
    midi_num, cents = constants.freq_arch_to_midi_num(
        ntsc_f,
        arch='PAL-C64',
        tuning=constants.CONCERT_A)
    print('{:d}, {:d}, {}, {:d}'.format(ntsc_f, midi_num, base.pitch_to_note_name(midi_num), cents))
    #print('{:d}, {:d}, {:d}'.format(ntsc_f, midi_num, cents))
"""

if __name__=="__main__":
    freqs = get_freqs()
    print_ntsc_pal_comparison(freqs)
    #print_asm_tables(freqs, False)


'''
midiNum, noteName, Hz, NTSCFreq, NTSCFreqHex, PALFreq, PALFreqHex
 12, C0 ,   16.352,   268, $010C,   278, $0116
 13, C#0,   17.324,   284, $011C,   295, $0127
 14, D0 ,   18.354,   301, $012D,   313, $0139
 15, D#0,   19.445,   319, $013F,   331, $014B
 16, E0 ,   20.602,   338, $0152,   351, $015F
 17, F0 ,   21.827,   358, $0166,   372, $0174
 18, F#0,   23.125,   379, $017B,   394, $018A
 19, G0 ,   24.500,   402, $0192,   417, $01A1
 20, G#0,   25.957,   426, $01AA,   442, $01BA
 21, A0 ,   27.500,   451, $01C3,   468, $01D4
 22, A#0,   29.135,   478, $01DE,   496, $01F0
 23, B0 ,   30.868,   506, $01FA,   526, $020E
 24, C1 ,   32.703,   536, $0218,   557, $022D
 25, C#1,   34.648,   568, $0238,   590, $024E
 26, D1 ,   36.708,   602, $025A,   625, $0271
 27, D#1,   38.891,   638, $027E,   662, $0296
 28, E1 ,   41.203,   676, $02A4,   702, $02BE
 29, F1 ,   43.654,   716, $02CC,   743, $02E7
 30, F#1,   46.249,   759, $02F7,   788, $0314
 31, G1 ,   48.999,   804, $0324,   834, $0342
 32, G#1,   51.913,   852, $0354,   884, $0374
 33, A1 ,   55.000,   902, $0386,   937, $03A9
 34, A#1,   58.270,   956, $03BC,   992, $03E0
 35, B1 ,   61.735,  1013, $03F5,  1051, $041B
 36, C2 ,   65.406,  1073, $0431,  1114, $045A
 37, C#2,   69.296,  1137, $0471,  1180, $049C
 38, D2 ,   73.416,  1204, $04B4,  1250, $04E2
 39, D#2,   77.782,  1276, $04FC,  1325, $052D
 40, E2 ,   82.407,  1352, $0548,  1403, $057B
 41, F2 ,   87.307,  1432, $0598,  1487, $05CF
 42, F#2,   92.499,  1517, $05ED,  1575, $0627
 43, G2 ,   97.999,  1608, $0648,  1669, $0685
 44, G#2,  103.826,  1703, $06A7,  1768, $06E8
 45, A2 ,  110.000,  1804, $070C,  1873, $0751
 46, A#2,  116.541,  1912, $0778,  1985, $07C1
 47, B2 ,  123.471,  2025, $07E9,  2103, $0837
 48, C3 ,  130.813,  2146, $0862,  2228, $08B4
 49, C#3,  138.591,  2274, $08E2,  2360, $0938
 50, D3 ,  146.832,  2409, $0969,  2500, $09C4
 51, D#3,  155.563,  2552, $09F8,  2649, $0A59
 52, E3 ,  164.814,  2704, $0A90,  2807, $0AF7
 53, F3 ,  174.614,  2864, $0B30,  2973, $0B9D
 54, F#3,  184.997,  3035, $0BDB,  3150, $0C4E
 55, G3 ,  195.998,  3215, $0C8F,  3338, $0D0A
 56, G#3,  207.652,  3406, $0D4E,  3536, $0DD0
 57, A3 ,  220.000,  3609, $0E19,  3746, $0EA2
 58, A#3,  233.082,  3824, $0EF0,  3969, $0F81
 59, B3 ,  246.942,  4051, $0FD3,  4205, $106D
 60, C4 ,  261.626,  4292, $10C4,  4455, $1167
 61, C#4,  277.183,  4547, $11C3,  4720, $1270
 62, D4 ,  293.665,  4817, $12D1,  5001, $1389
 63, D#4,  311.127,  5104, $13F0,  5298, $14B2
 64, E4 ,  329.628,  5407, $151F,  5613, $15ED
 65, F4 ,  349.228,  5729, $1661,  5947, $173B
 66, F#4,  369.994,  6070, $17B6,  6300, $189C
 67, G4 ,  391.995,  6430, $191E,  6675, $1A13
 68, G#4,  415.305,  6813, $1A9D,  7072, $1BA0
 69, A4 ,  440.000,  7218, $1C32,  7493, $1D45
 70, A#4,  466.164,  7647, $1DDF,  7938, $1F02
 71, B4 ,  493.883,  8102, $1FA6,  8410, $20DA
 72, C5 ,  523.251,  8584, $2188,  8910, $22CE
 73, C#5,  554.365,  9094, $2386,  9440, $24E0
 74, D5 ,  587.330,  9635, $25A3, 10001, $2711
 75, D#5,  622.254, 10208, $27E0, 10596, $2964
 76, E5 ,  659.255, 10815, $2A3F, 11226, $2BDA
 77, F5 ,  698.456, 11458, $2CC2, 11894, $2E76
 78, F#5,  739.989, 12139, $2F6B, 12601, $3139
 79, G5 ,  783.991, 12861, $323D, 13350, $3426
 80, G#5,  830.609, 13626, $353A, 14144, $3740
 81, A5 ,  880.000, 14436, $3864, 14985, $3A89
 82, A#5,  932.328, 15294, $3BBE, 15876, $3E04
 83, B5 ,  987.767, 16204, $3F4C, 16820, $41B4
 84, C6 , 1046.502, 17167, $430F, 17820, $459C
 85, C#6, 1108.731, 18188, $470C, 18880, $49C0
 86, D6 , 1174.659, 19270, $4B46, 20003, $4E23
 87, D#6, 1244.508, 20415, $4FBF, 21192, $52C8
 88, E6 , 1318.510, 21629, $547D, 22452, $57B4
 89, F6 , 1396.913, 22916, $5984, 23787, $5CEB
 90, F#6, 1479.978, 24278, $5ED6, 25202, $6272
 91, G6 , 1567.982, 25722, $647A, 26700, $684C
 92, G#6, 1661.219, 27251, $6A73, 28288, $6E80
 93, A6 , 1760.000, 28872, $70C8, 29970, $7512
 94, A#6, 1864.655, 30589, $777D, 31752, $7C08
 95, B6 , 1975.533, 32407, $7E97, 33640, $8368
 96, C7 , 2093.005, 34334, $861E, 35641, $8B39
 97, C#7, 2217.461, 36376, $8E18, 37760, $9380
 98, D7 , 2349.318, 38539, $968B, 40005, $9C45
 99, D#7, 2489.016, 40831, $9F7F, 42384, $A590
100, E7 , 2637.020, 43259, $A8FB, 44904, $AF68
101, F7 , 2793.826, 45831, $B307, 47574, $B9D6
102, F#7, 2959.955, 48556, $BDAC, 50403, $C4E3
103, G7 , 3135.963, 51444, $C8F4, 53401, $D099
104, G#7, 3322.438, 54503, $D4E7, 56576, $DD00
105, A7 , 3520.000, 57743, $E18F, 59940, $EA24
106, A#7, 3729.310, 61177, $EEF9, 63504, $F810
107, B7 , 3951.066, 64815, $FD2F, 67280, $106D0
'''

'''
; NTSC frequencies: lo bytes
data $0c,$1c,$2d,$3f,$52,$66,$7b,$92,$aa,$c3,$de,$fa ; C0-B0
data $18,$38,$5a,$7e,$a4,$cc,$f7,$24,$54,$86,$bc,$f5 ; C1-B1
data $31,$71,$b4,$fc,$48,$98,$ed,$48,$a7,$0c,$78,$e9 ; C2-B2
data $62,$e2,$69,$f8,$90,$30,$db,$8f,$4e,$19,$f0,$d3 ; C3-B3
data $c4,$c3,$d1,$f0,$1f,$61,$b6,$1e,$9d,$32,$df,$a6 ; C4-B4
data $88,$86,$a3,$e0,$3f,$c2,$6b,$3d,$3a,$64,$be,$4c ; C5-B5
data $0f,$0c,$46,$bf,$7d,$84,$d6,$7a,$73,$c8,$7d,$97 ; C6-B6
data $1e,$18,$8b,$7f,$fb,$07,$ac,$f4,$e7,$8f,$f9,$2f ; C7-B7

; NTSC frequencies: hi bytes
data $01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01 ; C0-B0
data $02,$02,$02,$02,$02,$02,$02,$03,$03,$03,$03,$03 ; C1-B1
data $04,$04,$04,$04,$05,$05,$05,$06,$06,$07,$07,$07 ; C2-B2
data $08,$08,$09,$09,$0a,$0b,$0b,$0c,$0d,$0e,$0e,$0f ; C3-B3
data $10,$11,$12,$13,$15,$16,$17,$19,$1a,$1c,$1d,$1f ; C4-B4
data $21,$23,$25,$27,$2a,$2c,$2f,$32,$35,$38,$3b,$3f ; C5-B5
data $43,$47,$4b,$4f,$54,$59,$5e,$64,$6a,$70,$77,$7e ; C6-B6
data $86,$8e,$96,$9f,$a8,$b3,$bd,$c8,$d4,$e1,$ee,$fd ; C7-B7

-----------

; PAL frequencies: lo bytes
data $16,$27,$39,$4b,$5f,$74,$8a,$a1,$ba,$d4,$f0,$0e ; C0-B0
data $2d,$4e,$71,$96,$be,$e7,$14,$42,$74,$a9,$e0,$1b ; C1-B1
data $5a,$9c,$e2,$2d,$7b,$cf,$27,$85,$e8,$51,$c1,$37 ; C2-B2
data $b4,$38,$c4,$59,$f7,$9d,$4e,$0a,$d0,$a2,$81,$6d ; C3-B3
data $67,$70,$89,$b2,$ed,$3b,$9c,$13,$a0,$45,$02,$da ; C4-B4
data $ce,$e0,$11,$64,$da,$76,$39,$26,$40,$89,$04,$b4 ; C5-B5
data $9c,$c0,$23,$c8,$b4,$eb,$72,$4c,$80,$12,$08,$68 ; C6-B6
data $39,$80,$45,$90,$68,$d6,$e3,$99,$00,$24,$10,$ff ; C7-B7

; PAL frequencies: hi bytes
data $01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$02 ; C0-B0
data $02,$02,$02,$02,$02,$02,$03,$03,$03,$03,$03,$04 ; C1-B1
data $04,$04,$04,$05,$05,$05,$06,$06,$06,$07,$07,$08 ; C2-B2
data $08,$09,$09,$0a,$0a,$0b,$0c,$0d,$0d,$0e,$0f,$10 ; C3-B3
data $11,$12,$13,$14,$15,$17,$18,$1a,$1b,$1d,$1f,$20 ; C4-B4
data $22,$24,$27,$29,$2b,$2e,$31,$34,$37,$3a,$3e,$41 ; C5-B5
data $45,$49,$4e,$52,$57,$5c,$62,$68,$6e,$75,$7c,$83 ; C6-B6
data $8b,$93,$9c,$a5,$af,$b9,$c4,$d0,$dd,$ea,$f8,$ff ; C7-B7
'''
