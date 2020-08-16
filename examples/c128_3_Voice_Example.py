import chiptunesak
from chiptunesak.constants import project_to_absolute_path

"""
This example shows how to convert a 3-voice song to C128 Basic:

 1. Import the song to chirp format from a MIDI file, quantizing the notes to the nearest 32nd note
 2. Since C128 BASIC cannot do notes shorter than a 16th note, perform a metric modulation to double note lengths
 3. Convert the song to mchirp format
 3. Save the BASIC as source
 4. Save the BASIC as a prg file

"""

output_folder = str(project_to_absolute_path('examples\\data\\C128')) + '\\'
input_folder = str(project_to_absolute_path('examples\\data\\common')) + '\\'
input_mid_file = input_folder + 'BWV_799.mid'
output_bas_file = output_folder + 'BWV_799.bas'
output_prg_file = output_folder + 'BWV_799.prg'

# Read in the MIDI song and quantize
chirp_song = chiptunesak.MIDI().to_chirp(input_mid_file, quantization='32', polyphony=False)

# When imported, the shortest note is a 32nd note, which is too fast for C128 BASIC.
# Perform a metric modulation by making every note length value twice as long, but
# increasing the tempo by the same factor so it sounds the same.  Now the shortest
# note will be a 16th note which the C128 BASIC can play.
print('Modulating music...')
chirp_song.modulate(2, 1)

# Convert to mchirp
print('Converting to MChirp...')
mchirp_song = chirp_song.to_mchirp()

# Write .bas and .prg files
exporter = chiptunesak.C128Basic()
exporter.set_options(instruments=['trumpet', 'guitar', 'guitar'])
print(f'Writing {output_bas_file}...')
exporter.to_file(mchirp_song, output_bas_file, format='bas')
print(f'Writing {output_prg_file}...')
exporter.to_file(mchirp_song, output_prg_file, format='prg')
