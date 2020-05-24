import sys
import examplesPath
import os
import subprocess
import ctsMidi
import ctsLilypond
from ctsConstants import project_to_absolute_path

"""
This example shows how to process a song into PDF file using Lilypond using the following steps:

 1. Import the song to chirp format from a MIDI file, quantizing the notes to the nearest 16th note
 2. Convert the song to mchirp format
 3. Save the lilypond source
 4. Run the lilypond converter from within python to generate the PDF file.

"""

output_folder = str(project_to_absolute_path('examples\\data\\lilypond')) + '\\'
input_folder = output_folder
input_mid_file = input_folder + 'bwv_799.mid'
output_ly_file = output_folder + 'bwv_799.ly'

# Read in the midi song and quantize
chirp_song = ctsMidi.MIDI().to_chirp(input_mid_file, quantization='16', polyphony=False)

# It's in A minor, 3/8 time
chirp_song.set_key_signature('Am')
chirp_song.set_time_signature(3, 8)

# Convert to mchirp
mchirp_song = chirp_song.to_mchirp()

# Create the lilpond I/O class
lp = ctsLilypond.Lilypond()
# Set the format to do a clip and set the measures to those you want
lp.set_options(format='song')
# Write it straight to a file
lp.to_file(mchirp_song, output_ly_file)

# Change directory to the data directory so we don't fill the source directory with intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file)
# Run lilypond
subprocess.call('lilypond -o %s %s' % (output_folder, output_ly_file), shell=True)
