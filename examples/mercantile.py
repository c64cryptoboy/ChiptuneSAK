import sys
import examplesPath
import copy
from ctsBase import *
import ctsMidi
import ctsRChirp
import ctsOnePassCompress
import ctsGoatTracker
from ctsConstants import project_to_absolute_path

"""
This example processes a MIDI file captured from Betrayal of Krondor to a GoatTracker song.

This is an example of extremely complex music processing, done entirely in ChiptuneSAK.

It shows the steps needed for this conversion:
 1. Remove unused tracks, reorder and rename tracks to use
 2. Consolidate two tracks into one, changing instruments partway through
 3. Scale, move and adjust the note data to correspond to musical notes and durations
 4. Set minimum note lengths, quantize the song, and remove polyphony
 5. Truncate the captured song to a reasonable stopping point
 6. Convert the ChirpSong to an RChirpSong  
 7. Assign GoatTracker instruments to the voices
 8. Find repeated loops and compress the song
 9. Export the GoatTracker .sng file 

"""

input_file = str(project_to_absolute_path('examples/data/mercantile/betrayalKrondorMercantile.mid'))
output_midi_file = str(project_to_absolute_path('examples/data/mercantile/mercantile.mid'))
output_gt_file = str(project_to_absolute_path('examples/data/mercantile/mercantile.sng'))

chirp_song = ctsMidi.MIDI().to_chirp(input_file)

# First thing, we rename the song
chirp_song.metadata.name = "Betrayal at Krondor - Mercantile Theme"

print(f'Original song:')
print(f'#tracks = {len(chirp_song.tracks)}')
print(f'    ppq = {chirp_song.metadata.ppq}')
print(f'  tempo = {chirp_song.metadata.qpm} qpm')
print()
print('Original track names:')
print('\n'.join(f'{i+1}:  {t.name}' for i, t in enumerate(chirp_song.tracks)))
print()

# Truncate to 4 tracks and re-order from melody to bass
chirp_song.tracks = [chirp_song.tracks[j] for j in [3, 1, 2, 0]]

# Truncate the notes in track 3 when the bass line starts
chirp_song.tracks[2].truncate(9570)

# Get rid of any superfluous program changes in the tracks
for t in chirp_song.tracks:
    t.set_program(t.program_changes[-1].program)

# Change the program to the bass at that point
tmp_program = chirp_song.tracks[3].program_changes[0]
new_program = ProgramEvent(9700, tmp_program.program)
chirp_song.tracks[2].program_changes.append(new_program)

# Now move the notes from track 4 into track 3
chirp_song.tracks[2].notes.extend(chirp_song.tracks[3].notes)
chirp_song.tracks = chirp_song.tracks[:3]
chirp_song.tracks[0].name = 'Flute'
chirp_song.tracks[1].name = 'Guitar'
chirp_song.tracks[2].name = 'Strings/Bass'

# At this point, with the tracks arranged, run the FitPPW.py program in the tools directory.

# Result, after some fiddling (and FitPPQ is very fiddly):
# scale_factor = 5.8904467169, offset = 2399, total error = 3136.3 ticks (21.79 ticks/note for ppq = 960)
chirp_song.move_ticks(-2399)
chirp_song.scale_ticks(5.8904467169)
chirp_song.metadata.ppq = 960

# Now get rid of the very weird short notes in the flute part; set minimum length to an eighth note
chirp_song.tracks[0].set_min_note_len(480)

# Quantize the whole song to eighth notes
chirp_song.quantize_from_note_name('8')

# Now we can safely remove any polyphony
chirp_song.remove_polyphony()

#  The song is repetitive. Pick a spot to truncate.
chirp_song.truncate(197280)

# Save the result to a MIDi file.
ctsMidi.MIDI().to_file(chirp_song, output_midi_file)

# Now convert the song to RChirp
rchirp_song = chirp_song.to_rchirp()

# Let's see what prgrams are used
print(rchirp_song.program_map)
# This gives {79: 1, 24: 2, 48: 3, 32: 4}
# From General Midi,
# 79 = Ocarina                   Flute.ins
# 24 = Acoustic Guitar (Nylon)   MuteGuitar.ins
# 48 = String Ensemble 1         SimpleTriangle.ins
# 32 = Acoustic Bass             BassGuitar.ins
#
instruments = ['Flute', 'MuteGuitar', 'SimpleTriangle', 'SoftBass']

# Perform loop-finding to compress the song and to take advantage of repetition
# The best minimum pattern length depends on the particular song.
print('Compressing RChirp')
compressor = ctsOnePassCompress.OnePassLeftToRight()
rchirp_song = compressor.compress(rchirp_song, min_length=16)

# Now export the compressed song to goattracker format.
print(f'Writing {output_gt_file}')
GT = ctsGoatTracker.GoatTracker()
GT.to_file(rchirp_song, output_gt_file, instruments=instruments)
