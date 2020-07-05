import os
import subprocess
from chiptunesak import midi
from chiptunesak.lilypond import Lilypond
from chiptunesak.constants import project_to_absolute_path

"""
This example shows how to do metric modulation to remove triplets


"""

output_folder = str(project_to_absolute_path('examples\\data\\triplets')) + '\\'
input_folder = output_folder
input_mid_file = input_folder + 'skyfox.mid'
output_mid_file = output_folder + 'skyfox_mod.mid'
output_ly_file = output_folder + 'skyfox.ly'
output_ly_file_mod = output_folder + 'skyfox_mod.ly'

chirp_song = midi.MIDI().to_chirp(input_mid_file)

original_qpm = chirp_song.metadata.qpm
original_ppq = chirp_song.metadata.ppq

# First thing, we rename the song
chirp_song.metadata.name = "SkyFox - Main Theme"
chirp_song.metadata.composer = "Douglas Fulton"

# Now name the tracks
for t, name in zip(chirp_song.tracks, ['Square1', 'Square2', 'Square3']):
    t.name = name

chirp_song.scale_ticks(6.25)
chirp_song.metadata.ppq = 960
chirp_song.set_qpm(original_qpm * 1.25)
chirp_song.set_time_signature(4, 4)
chirp_song.set_key_signature('B')

chirp_song.quantize(80, 80)
chirp_song.remove_polyphony()

mchirp_song = chirp_song.to_mchirp()
Lilypond().to_file(mchirp_song, output_ly_file, format='song')


# Change directory to the data directory so we don't fill the source directory with intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file)
# Run lilypond
subprocess.call('lilypond -o %s %s' % (output_folder, output_ly_file), shell=True)

chirp_song.modulate(3, 2)
chirp_song.quantize(120, 120)
midi.MIDI().to_file(chirp_song, output_mid_file)

mchirp_song = chirp_song.to_mchirp()
Lilypond().to_file(mchirp_song, output_ly_file_mod, format='song')

# Change directory to the data directory so we don't fill the source directory with intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file_mod)
# Run lilypond
subprocess.call('lilypond -o %s %s' % (output_folder, output_ly_file_mod), shell=True)

