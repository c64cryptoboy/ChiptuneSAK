import chiptunesak
from chiptunesak.constants import project_to_absolute_path

"""
This example shows how to convert the 2-voice song shown in the C128 BASIC manual to *correct* C128 Basic:

 1. Import the song to chirp format from a MIDI file, which already has 16th notes expanded to 8th notes
 3. Convert the song to mchirp format
 3. Save the BASIC as source
 4. Save the BASIC as a prg file

"""

output_folder = str(project_to_absolute_path('examples\\data\\c128')) + '\\'
input_folder = output_folder
input_mid_file = input_folder + 'BWV_784_16th_to_8th.mid'
output_bas_file = output_folder + 'BWV_784.bas'
output_prg_file = output_folder + 'BWV_784.prg'

# Read in the MIDI file, quantizing to eighth notes
chirp_song = chiptunesak.MIDI().to_chirp(input_mid_file, quantization='8', polyphony=False)

# Convert the song to MChirp format
mchirp_song = chirp_song.to_mchirp()

# Create a BASIC output class
basic = chiptunesak.C128Basic()

# First write the BAS file
print(f'Writing {output_bas_file}...')
basic.to_file(
    mchirp_song,
    output_bas_file,
    instruments=['guitar', 'guitar', 'guitar'],
    rem_override="errata for c128 system guide p156 or c128 programmer's ref guide p343",
    format='bas')

# Then create the PRG file
print(f'Writing {output_prg_file}...')
basic.to_file(
    mchirp_song,
    output_prg_file,
    format='prg')  # Remembers instruments and rem_override settings from above
