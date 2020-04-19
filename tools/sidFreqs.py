from ctsConstants import C0_MIDI_NUM, CONCERT_A, A4_MIDI_NUM
import ctsBase

print("midi num, note name, freq, NTSC freq, PAL freq")
# From C0 to B7.  References:
# - https://www.colincrawley.com/midi-note-to-audio-frequency-calculator/
# - https://gist.github.com/matozoid/18cddcbc9cfade3c455bc6230e1f6da6
for midi_num in range(C0_MIDI_NUM, C0_MIDI_NUM+(8*12)):
    freq = CONCERT_A * pow(2, (midi_num - A4_MIDI_NUM) / 12)
    ntsc_freq = ctsBase.get_arch_freq_for_midi_num(midi_num, 'NTSC')
    pal_freq = ctsBase.get_arch_freq_for_midi_num(midi_num, 'PAL')

    print("%d, %s, % 0.3f, %d, %d" % (midi_num, ctsBase.pitch_to_note_name(midi_num), freq, ntsc_freq, pal_freq))
