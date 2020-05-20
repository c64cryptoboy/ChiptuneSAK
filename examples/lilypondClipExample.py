import sys
import examplesPath
import os
import subprocess
import ctsMidi
import ctsLilypond
from ctsConstants import project_to_absolute_path

"""
This example shows how to process a clip of a song into a PNG file using Lilypond using the following steps:

 1. Import the song to chirp format from a MIDI file, quantizing the notes to the nearest 16th note
 2. Convert the song to mchirp format
 3. Select the measures for the clip
 4. Save the lilypond source
 5. Run the lilypond converter from within python to generate the PNG file.

"""

input_file = project_to_absolute_path('examples/data/bach_invention_4.mid')
output_ly_file = project_to_absolute_path('examples/data/lilypond/bach_invention_4.ly')

# Read in the midi song and quantize
chirp_song = ctsMidi.MIDI().to_chirp(input_file, quantization='16', polyphony=False)
# Convert to mchirp
mchirp_song = chirp_song.to_mchirp()

# Create the lilpond I/O class
lp = ctsLilypond.Lilypond()
# Set the format to do a clip and set the measures to those you want
lp.set_options(format='clip', measures=mchirp_song.tracks[0].measures[3:8])
# Write it straight to a file
lp.to_file(mchirp_song, output_ly_file)

# Change directory to the data directory so we don't fill the source directory wiith intermediate files.
os.chdir(project_to_absolute_path('examples/data/lilypond'))

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file)
# Run lilypond
args = ['lilypond', '-ddelete-intermediate-files', '-dbackend=eps', '-dresolution=600', '--png', ly_file]
subprocess.call(args, shell=True)
