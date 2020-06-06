import ctsConstants
import ctsBase


def hexit(num):
    return hex(num)[2:]


print("midi num, note name, freq, NTSC freq, PAL freq")
# From C0 to B7.  References:
# - https://www.colincrawley.com/midi-note-to-audio-frequency-calculator/
# - https://gist.github.com/matozoid/18cddcbc9cfade3c455bc6230e1f6da6
for midi_num in range(ctsConstants.C0_MIDI_NUM, ctsConstants.C0_MIDI_NUM + (8 * 12)):
    tuning = ctsConstants.CONCERT_A     # e.g., tuning = 440.11 used by siddump.c
    freq = ctsConstants.midi_num_to_freq(midi_num, tuning)
    ntsc_freq = ctsConstants.midi_num_to_freq_arch(midi_num, 'NTSC-C64', tuning)
    pal_freq = ctsConstants.midi_num_to_freq_arch(midi_num, 'PAL-C64', tuning)

    print(
        "%d, %s, % 0.3f, %d, %s, %d, %s" %
        (
            midi_num, ctsBase.pitch_to_note_name(midi_num), freq, ntsc_freq,
            hexit(ntsc_freq), pal_freq, hexit(pal_freq)
        )
    )
