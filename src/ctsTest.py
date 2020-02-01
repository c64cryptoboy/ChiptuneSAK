import sys

import ctsChirp

inFileName = sys.argv[1]
outFileName = sys.argv[2]

inMidi = ctsChirp.ChirpSong()
inMidi.import_midi(inFileName)

print("Removing control notes")
inMidi.remove_control_notes()

print("ChirpSong is %s" % ("polyphonic" if inMidi.is_polyphonic() else "non-polyphonic"))
# Print stats
print('%d notes' % (sum(len(t.notes) for t in inMidi.tracks)))
print('PPQ = %d' % (inMidi.ppq))

qTicksN, qTicksD = inMidi.estimate_quantization()
print("Estimated quantization = ", (qTicksN, qTicksD), "ticks")
print("(%s, %s)" % (ctsChirp.duration_to_note_name(qTicksN, inMidi.ppq), ctsChirp.duration_to_note_name(qTicksN, inMidi.ppq)))
inMidi.quantize()
inMidi.eliminate_polyphony()
# inMidi.modulate(3, 2)

print(inMidi.stats)

inMidi.export_midi(outFileName)
