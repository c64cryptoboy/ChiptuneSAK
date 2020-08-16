import os
import subprocess

import chiptunesak
from chiptunesak.constants import project_to_absolute_path

"""
This example shows how to process a clip of a song into a PNG file using Lilypond using the following steps:

 1. Import the song to chirp format from a MIDI file, quantizing the notes to the nearest 16th note
 2. Convert the song to mchirp format
 3. Select the measures for the clip
 4. Save the lilypond source
 5. Run the lilypond converter from within python to generate the PNG file.

"""

output_folder = str(project_to_absolute_path('examples\\data\\lilypond')) + '\\'
input_folder = output_folder
input_file = input_folder + 'BWV_775.mid'
output_ly_file = output_folder + 'BWV_775.ly'

# Read in the MIDI song and quantize
chirp_song = chiptunesak.MIDI().to_chirp(input_file, quantization='16', polyphony=False)
# Convert to mchirp
mchirp_song = chirp_song.to_mchirp()

# Create the LilyPond I/O object
lp = chiptunesak.Lilypond()
# Set the format to do a clip and set the measures to the clip we want
lp.set_options(format='clip', measures=mchirp_song.tracks[0].measures[3:8])
# Write it straight to a file
lp.to_file(mchirp_song, output_ly_file)

# Change directory to the data directory so we don't fill the source directory with intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file)
# Run lilypond
args = ['lilypond', '-ddelete-intermediate-files', '-dbackend=eps', '-dresolution=600', '--png', ly_file]
subprocess.call(args, shell=True)
