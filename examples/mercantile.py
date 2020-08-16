import subprocess

import chiptunesak
import chiptunesak.base
from chiptunesak.constants import project_to_absolute_path

"""
This example processes a MIDI file captured from Betrayal at Krondor to both sheet music and
a GoatTracker song.

It is an example of extremely complex music processing, done entirely in ChiptuneSAK.
A program called MidiEditor (windows / linux, https://www.midieditor.org/), was used to
inspect the MIDI file, evaluate and plan the required transformations, and verify the results.

It shows the steps needed for this conversion:
 1. Remove unused tracks, reorder and rename tracks to use
 2. Consolidate two tracks into one, changing instruments partway through
 3. Scale, move and adjust the note data to correspond to musical notes and durations
 4. Set minimum note lengths, quantize the song, and remove polyphony
 5. Truncate the captured song to a reasonable stopping point
 6. Convert the ChirpSong to an MChirpSong
 7. Use the Lilypond I/O object to write lilypond markup for the piece
 8. Convert the ChirpSong to an RChirpSong
 9. Assign GoatTracker instruments to the voices
10. Find repeated loops and compress the song
11. Export the GoatTracker .sng file

"""

output_folder = str(project_to_absolute_path('examples\\data\\mercantile')) + '\\'
input_folder = output_folder
input_file = str(project_to_absolute_path(input_folder + 'betrayalKrondorMercantile.mid'))
output_midi_file = str(project_to_absolute_path(output_folder + 'mercantile.mid'))
output_ly_file = str(project_to_absolute_path(output_folder + 'mercantile.ly'))
output_gt_file = str(project_to_absolute_path(output_folder + 'mercantile.sng'))

# Read in the original MIDI to Chirp
chirp_song = chiptunesak.MIDI().to_chirp(input_file)

# First thing, we rename the song
chirp_song.metadata.name = "Betrayal at Krondor - Mercantile Theme"
chirp_song.metadata.composer = "Jan Paul Moorhead"

print(f'Original song:')
print(f'#tracks = {len(chirp_song.tracks)}')
print(f'    ppq = {chirp_song.metadata.ppq}')
print(f'  tempo = {chirp_song.metadata.qpm} qpm')
print('Track names:')
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
new_program = chiptunesak.base.ProgramEvent(9700, tmp_program.program)
chirp_song.tracks[2].program_changes.append(new_program)

# Now move the notes from track 4 into track 3
chirp_song.tracks[2].notes.extend(chirp_song.tracks[3].notes)

# This is a 1-SID song, so only three voices allowed.
# Delete any extra tracks and name the rest.
chirp_song.tracks = chirp_song.tracks[:3]
chirp_song.tracks[0].name = 'Ocarina'
chirp_song.tracks[1].name = 'Guitar'
chirp_song.tracks[2].name = 'Strings/Bass'

# At this point, with the tracks arranged, run the FitPPQ.py program in the tools directory.

# Result, after some fiddling (and FitPPQ can be *very* fiddly):
# best fit scale_factor = 5.89, offset = 2398
chirp_song.move_ticks(-2398)
chirp_song.scale_ticks(5.89000)
chirp_song.metadata.ppq = 960

# Now get rid of the very weird short notes in the flute part; set minimum length to an eighth note
chirp_song.tracks[0].set_min_note_len(480)

# Quantize the whole song to eighth notes
chirp_song.quantize_from_note_name('8')

# Now we can safely remove any polyphony
chirp_song.remove_polyphony()

#  The song is repetitive. Pick a spot to truncate.
chirp_song.truncate(197280)

# Set the key (D minor)
chirp_song.set_key_signature('Dm')

print(f'Modified song:')
print(f'#tracks = {len(chirp_song.tracks)}')
print(f'    ppq = {chirp_song.metadata.ppq}')
print(f'  tempo = {chirp_song.metadata.qpm} qpm')
print('Track names:')
print('\n'.join(f'{i+1}:  {t.name}' for i, t in enumerate(chirp_song.tracks)))
print()

# Save the result to a MIDi file.
chiptunesak.MIDI().to_file(chirp_song, output_midi_file)

# Convert to MChirp
mchirp_song = chirp_song.to_mchirp()

# Make sheet music output with Lilypond
ly = chiptunesak.Lilypond()
ly.to_file(mchirp_song, output_ly_file)

# If you have Lilypond installed, generate the pdf
# If you do not have Lilypond installed, comment the following line out
subprocess.call('lilypond -o %s %s' % (output_folder, output_ly_file), shell=True)

# Now convert the song to RChirp
rchirp_song = chirp_song.to_rchirp(arch='PAL-C64')

# Let's see what programs are used
# print(rchirp_song.program_map)
# Gives {79: 1, 24: 2, 48: 3, 32: 4}
# From General Midi,
# 79 = Ocarina                   Flute.ins
# 24 = Acoustic Guitar (Nylon)   MuteGuitar.ins
# 48 = String Ensemble 1         SimpleTriangle.ins
# 32 = Acoustic Bass             SoftBass.ins
#
instruments = ['Flute', 'MuteGuitar', 'SimpleTriangle', 'SoftBass']

# Perform loop-finding to compress the song and to take advantage of repetition
# The best minimum pattern length depends on the particular song.
print('Compressing RChirp')
compressor = chiptunesak.OnePassLeftToRight()
rchirp_song = compressor.compress(rchirp_song, min_length=16)

# Now export the compressed song to goattracker format.
print(f'Writing {output_gt_file}')
GT = chiptunesak.GoatTracker()
GT.to_file(rchirp_song, output_gt_file, instruments=instruments)
