import chiptunesak
from chiptunesak.constants import project_to_absolute_path

"""
This example shows how to convert a song to C128 Basic:

 1. Import the song to chirp format from a MIDI file, quantizing the notes to the nearest 32nd note
 2. Since C1287 cannot do notes shorter than a 16th note, perform a metric modulation
 3. Convert the song to mchirp format
 3. Save the BASIC as source
 4. Save the BASIC as a prg file

"""

output_folder = str(project_to_absolute_path('examples\\data\\C128')) + '\\'
input_folder = output_folder
input_mid_file = input_folder + 'BWV_799.mid'
output_bas_file = output_folder + 'BWV_799.bas'
output_prg_file = output_folder + 'BWV_799.prg'

# Read in the midi song and quantize
chirp_song = chiptunesak.MIDI().to_chirp(input_mid_file, quantization='32', polyphony=False)

# Perform a metric modulation by making every note length value twice as long, but
# increasing the tempo by the same factor so it sounds the same.  Now the shortest
# note will be a 16th note which the C128 BASIC can play.
chirp_song.modulate(2, 1)

# Convert to mchirp, parsing the song for measures
mchirp_song = chirp_song.to_mchirp()

# Write it straight to a file using the Lilypond class with format 'song' for the entire song.
exporter = chiptunesak.C128Basic()
exporter.set_options(instruments=['trumpet', 'guitar', 'guitar'])
exporter.to_file(mchirp_song, output_bas_file, format='bas')
exporter.to_file(mchirp_song, output_prg_file, format='prg')
