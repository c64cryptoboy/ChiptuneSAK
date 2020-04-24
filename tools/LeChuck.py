import sys
import toolsPath
import copy
import ctsMidi
import ctsRChirp
import ctsGtCompress
import ctsGoatTracker

input_dir = '..\\test\\data\\'
input_file = 'MonkeyIsland1LechuckThemeVer3_manuallyEdited.mid'
output_midi_file = 'LeChuck.mid'
output_gt_file = 'LeChuck.sng'

chirp_song = ctsMidi.import_midi_to_chirp(input_dir + input_file)

chirp_song.metadata.name = "Monkey Island - LeChuck Theme"

tracks = [copy.copy(chirp_song.tracks[i]) for i in [2, 1, 0]]
chirp_song.tracks = tracks

for t, n in zip(chirp_song.tracks, ['Lead', 'Chord', 'Bass']):
    t.name = n

chirp_song.scale_ticks(4.)
chirp_song.metadata.ppq = 960
chirp_song.set_qpm(180)
chirp_song.quantize_from_note_name('8')

chirp_song.explode_polyphony(1)
chirp_song.remove_polyphony()

print('\n'.join(t.name for t in chirp_song.tracks))

ctsMidi.export_chirp_to_midi(chirp_song, input_dir + output_midi_file)

for i, program in enumerate([9, 10, 10, 10, 6]):              # ([9, 1, 6, 7, 12]):
    chirp_song.tracks[i].set_program(program)

rchirp_song = ctsRChirp.RChirpSong(chirp_song)

rchirp_song = ctsGtCompress.compress_gt_lr(rchirp_song, 8)

ctsGoatTracker.export_rchirp_to_gt(rchirp_song, input_dir + output_gt_file)

