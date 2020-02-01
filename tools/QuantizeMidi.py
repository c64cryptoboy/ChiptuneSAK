import sys

sys.path.append('../src')

import ctsChirp

in_filename = sys.argv[1]
out_filename = sys.argv[2]

in_midi = ctsChirp.ChirpSong()
in_midi.import_midi(in_filename)

# Print stats
print('%d notes' % (sum(len(t.notes) for t in in_midi.tracks)))
print('PPQ = %d' % (in_midi.ppq))
q_state = "" if in_midi.is_quantized() else "not"
p_state = "" if in_midi.is_polyphonic() else "not"
print("Input midi is %s quantized and %s polyphonic" % (q_state, p_state))
qticks_n, qticks_d = in_midi.estimate_quantization()
print("Estimated quantization = (%d, %d) ticks" % (qticks_n, qticks_d))
print("                       = (%s, %s)" % (ctsChirp.duration_to_note_name(qticks_n, in_midi.ppq),
                                             ctsChirp.duration_to_note_name(qticks_d, in_midi.ppq)))

print("Removing control notes...")
in_midi.remove_control_notes()

print("Quantizing...")
in_midi.quantize()

print("Eliminating polyphony...")
in_midi.eliminate_polyphony()
# inMidi.modulate(3, 2)

q_state = "" if in_midi.is_quantized() else "not"
p_state = "" if in_midi.is_polyphonic() else "not"
print("ChirpSong is %s quantized and %s polyphonic" % (q_state, p_state))

print('\n'.join("%24s %s" % (s, str(v)) for s, v in in_midi.stats.items()))

print("Exporting to MIDI...")
in_midi.export_midi(out_filename)