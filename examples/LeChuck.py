import sys
import examplesPath
import copy
import ctsMidi
import ctsRChirp
import ctsGtCompress
import ctsGoatTracker

input_dir = '../test/data\\'
input_file = 'MonkeyIsland1LechuckThemeVer3_manuallyEdited.mid'
output_midi_file = 'LeChuck.mid'
output_gt_file = 'LeChuck.sng'

chirp_song = ctsMidi.import_midi_to_chirp(input_dir + input_file)

print(f'original song:')
print(f'    ppq = {chirp_song.metadata.ppq}')
print(f'  tempo = {chirp_song.metadata.qpm} qpm')


# First thing, we rename the song
chirp_song.metadata.name = "Monkey Island - LeChuck Theme"

# Now order the tracks the way we want them, which is the reverse of the midi we got.
tracks = [copy.copy(chirp_song.tracks[i]) for i in [2, 1, 0]]
chirp_song.tracks = tracks

# Now given the tracks the names we want them to have, because the track names in the original midi were
# used for information that is supposed to go elsewhere in midi files.
for t, n in zip(chirp_song.tracks, ['Lead', 'Chord', 'Bass']):
    t.name = n

# Experimentally determine ticks per measure
# - Counted measures by hand listening to the music.  We identified the note at the start of measure 21
#    (the later the better to give a good average) which was at tick 19187
# -       19187 / 20 = 959.35
#   Very close to 960 ticks/measure.
# A small error here will be fixed by our quantization later

# We desire our new song to use a standard 960 ppq and 4 notes per measure, so we scale the ticks by 4
# (assuming 9 quarter notes per measure)
chirp_song.scale_ticks(4.)
chirp_song.metadata.ppq = 960  # The original ppq is meaningless; it was just the ppq of the midi capture program

# New tempo: original tempo was 240 qpm where ppq was given as 192 which makes 240 * 192 / 60 = 768 ticks/sec
# We scaled the ticks (and the tempo) by a factor of 4 so now we need 768 * 4 = 3072 ticks/sec
# For a quarter note = 960 ticks that comes out to 3072 / 960 = 3.2 qps * 60 = 192
chirp_song.set_qpm(192)

# Looking at the midi and listening to the song, the best quantization appears to be eighth notes.
chirp_song.quantize_from_note_name('8')

# Track 2 has chords in it that have 3 notes at a time.  We need to move those to separate voices, so
#   we split that track:
chirp_song.explode_polyphony(1)

# Any other polyphony is unintentional so make sure it is all gone (in particular, one note in the bass line
#   seems to make a chord, but it's not real.
chirp_song.remove_polyphony()  # There is one place in the bass line that made a chord; this removes it

# Now export the modified chirp to a new midi file, which can be viewed and should look nice and neat
ctsMidi.export_chirp_to_midi(chirp_song, input_dir + output_midi_file)

# Now set the instrument numbers for the goattracker song.  Use some of our standard pre-defined instruments
for i, program in enumerate([9, 10, 10, 10, 6]):
    chirp_song.tracks[i].set_program(program)

# Now that everything is C64 compatible, we convert the song to goattracker format.
rchirp_song = ctsRChirp.RChirpSong(chirp_song)

# Perform loop-finding to compress the song and to take advantage of repetition
# The best minimum pattern length depends on the particular song.
rchirp_song = ctsGtCompress.compress_gt_lr(rchirp_song, 16)

# Now export the compressed song to goattracker format.
ctsGoatTracker.export_rchirp_to_gt(rchirp_song, input_dir + output_gt_file)
