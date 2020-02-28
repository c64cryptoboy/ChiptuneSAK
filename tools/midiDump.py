# Placeholder for something better

import sys
from mido import MidiFile

if len(sys.argv) != 2:
    print("Usage: midiDump filename.midi")
    exit()

inFilename = sys.argv[1]

try:
    inMidiFile = MidiFile(inFilename)
except IOError:
    print('Error: Can\'t open "%s"' % (inFilename))
    sys.exit(1)

print("Midi type: %d, PPQ: %d\n" % (inMidiFile.type, inMidiFile.ticks_per_beat))

for i, track in enumerate(inMidiFile.tracks):
    print('Track {}: "{}"'.format(i, track.name))
    for msg in track:
        print(msg)
