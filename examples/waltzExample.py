import sys
import examplesPath
import os
import subprocess
import ctsMidi
import ctsLilypond
from ctsConstants import project_to_absolute_path

"""
This example shows how to do metric modulation to remove triplets


"""

output_folder = str(project_to_absolute_path('examples\\data\\triplets')) + '\\'
input_folder = output_folder
input_mid_file = input_folder + 'chopin_waltz.mid'
output_mid_file = output_folder + 'chopin_waltz_mod.mid'
output_ly_file = output_folder + 'chopin_waltz.ly'
output_ly_file_mod = output_folder + 'chopin_waltz_mod.ly'

chirp_song = ctsMidi.MIDI().to_chirp(input_mid_file)

#  First thing, both hands have 3-note polyphony.

chirp_song.explode_polyphony(1)
chirp_song.explode_polyphony(0)

chirp_song.tracks = [chirp_song.tracks[0], chirp_song.tracks[5], chirp_song.tracks[4]]

chirp_song.quantize(80, 80)
chirp_song.remove_polyphony()

mchirp_song = chirp_song.to_mchirp()

# Create the lilpond I/O class
lp = ctsLilypond.Lilypond()
# Set the format to do a clip and set the measures to those you want
lp.set_options(format='clip', measures=mchirp_song.tracks[0].measures[116:124])
# Write it straight to a file
lp.to_file(mchirp_song, output_ly_file)

# Change directory to the data directory so we don't fill the source directory wiith intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file)
# Run lilypond
args = ['lilypond', '-ddelete-intermediate-files', '-dbackend=eps', '-dresolution=600', '--png', ly_file]
subprocess.call(args, shell=True)



ctsMidi.MIDI().to_file(chirp_song, output_mid_file)

