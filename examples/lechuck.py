import copy

import chiptunesak
from chiptunesak.constants import project_to_absolute_path

"""
This example processes a MIDI file captured from Secret of Monkey Island to a GoatTracker song.

It shows the steps needed for this conversion:
  1. Scale and adjust the note data to correspond to musical notes and durations
  2. Split a track with chords into 3 separate tracks
  3. Assign GoatTracker instruments to the voices
  4. Export the 5-track to a stereo GoatTracker .sng file
"""

input_file = str(project_to_absolute_path('examples/data/lechuck/MonkeyIsland_LechuckTheme.mid'))
output_midi_file = str(project_to_absolute_path('examples/data/lechuck/LeChuck.mid'))
output_gt_file = str(project_to_absolute_path('examples/data/lechuck/LeChuck.sng'))

chirp_song = chiptunesak.MIDI().to_chirp(input_file)

print(f'Original song:')
print(f'#tracks = {len(chirp_song.tracks)}')
print(f'    ppq = {chirp_song.metadata.ppq}')
print(f'  tempo = {chirp_song.metadata.qpm} qpm')
print('Track names:')
print('\n'.join(f'{i+1}:  {t.name}' for i, t in enumerate(chirp_song.tracks)))
print()


# First thing, we rename the song
chirp_song.metadata.name = "Monkey Island - LeChuck Theme"

print('Truncating original song...')
chirp_song.truncate(21240)

# Now select and order the tracks the way we want them, which is the reverse of the midi we got.
print('Selecting and ordering tracks...')
tracks = [copy.copy(chirp_song.tracks[i]) for i in [3, 2, 1]]
chirp_song.tracks = tracks

print(f'Now {len(chirp_song.tracks)} tracks')

# Now given the tracks the names we want them to have, because the track names in the original midi were
# used for information that is supposed to go elsewhere in midi files.
print('Renaming tracks...')
for t, n in zip(chirp_song.tracks, ['Lead', 'Chord', 'Bass']):
    t.name = n

print('Tracks:')
print('\n'.join(f'  {t.name}' for t in chirp_song.tracks))
print()

print('Adjusting ppq and tempo...')

# Experimentally determine ticks per measure
# - Counted measures by hand listening to the music.  We identified the note at the start of measure 21
#    (the later the better to give a good average) which was at tick 19187
# -       19187 / 20 = 959.35
#   Very close to 960 ticks/measure.
# Any small error here will be fixed by our quantization later

# We desire our new song to use a standard 960 ppq and 4 notes per measure, so we scale the ticks by 4
# (assuming 9 quarter notes per measure)
chirp_song.scale_ticks(4.0)
chirp_song.metadata.ppq = 960  # The original ppq is meaningless; it was just the ppq of the midi capture program

# New tempo: original tempo was 240 qpm where ppq was given as 192 which makes 240 * 192 / 60 = 768 ticks/sec
# We scaled the ticks (and the tempo) by a factor of 4 so now we need 768 * 4 = 3072 ticks/sec
# For a quarter note = 960 ticks that comes out to 3072 / 960 = 3.2 qps * 60 = 192
chirp_song.set_qpm(192)

# Looking at the midi and listening to the song, the best quantization appears to be eighth notes.
chirp_song.quantize_from_note_name('8')

# Track 2 has chords in it that have 3 notes at a time.  We need to move those to separate voices, so
# we split that track:
print('Exploding polyphony of chord track...')
chirp_song.explode_polyphony(1)

print(f'Now {len(chirp_song.tracks)} tracks')
print('Tracks:')
print('\n'.join(f'  {t.name}' for t in chirp_song.tracks))
print()

# Any other polyphony is unintentional so make sure it is all gone (in particular, one note in the bass line
# seems to make a chord, but it's not real.
print('Removing remaining polyphony')
chirp_song.remove_polyphony()

# Now export the modified chirp to a new midi file, which can be viewed and should look nice and neat
print(f'Writing to MIDI file {output_midi_file}')
chiptunesak.MIDI().to_file(chirp_song, output_midi_file)

# Now set the instrument numbers for the GoatTracker song.
# Since we want control over the instruments we specify the GT ones in track order.
print(f'Setting GoatTracker instruments...')
for i, program in enumerate([1, 2, 2, 2, 3]):
    chirp_song.tracks[i].set_program(program)

# Now that everything is C64 compatible, we convert the song to RChirp format.
print(f'Converting ChirpSong to RChirpSong...')
rchirp_song = chiptunesak.RChirpSong(chirp_song)

# Perform loop-finding to compress the song and to take advantage of repetition
# The best minimum pattern length depends on the particular song.  For this one we chose 16 rows.
print('Compressing RChirp')
compressor = chiptunesak.OnePassLeftToRight()
rchirp_song = compressor.compress(rchirp_song, min_length=16)

# Now export the compressed song to goattracker format.
print(f'Writing GoatTracker file {output_gt_file}')
GT = chiptunesak.GoatTracker()
GT.set_options(instruments=['LeChuckLead', 'C128Xylophone', 'LeChuckBass'])
GT.to_file(rchirp_song, output_gt_file)
