import os
import subprocess

import chiptunesak
from chiptunesak.constants import project_to_absolute_path

"""
This example shows how to process a song into PDF file using Lilypond using the following steps:

 1. Import the song to chirp format from a MIDI file, quantizing the notes to the nearest 32nd note
 2. Convert the song to mchirp format
 3. Save the lilypond source
 4. Run the lilypond converter from within python to generate the PDF file.

"""

output_folder = str(project_to_absolute_path('examples\\data\\lilypond')) + '\\'
input_folder = str(project_to_absolute_path('examples\\data\\common')) + '\\'
input_mid_file = input_folder + 'BWV_799.mid'
output_ly_file = output_folder + 'BWV_799.ly'

# Read in the MIDI song and quantize
chirp_song = chiptunesak.MIDI().to_chirp(input_mid_file, quantization='32', polyphony=False)

# It's in A minor, 3/8 time
chirp_song.set_key_signature('Am')
chirp_song.set_time_signature(3, 8)

# Convert to mchirp
mchirp_song = chirp_song.to_mchirp()

# Write it straight to a file using the Lilypond class with format 'song' for the entire song.
chiptunesak.Lilypond().to_file(mchirp_song, output_ly_file, format='song')

# Change directory to the data directory so we don't fill the source directory with intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file)
# Run lilypond
subprocess.call('lilypond -o %s %s' % (output_folder, output_ly_file), shell=True)
