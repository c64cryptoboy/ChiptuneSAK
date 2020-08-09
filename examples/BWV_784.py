# TODO:
# - Clean this up for demo

import chiptunesak
from chiptunesak.constants import project_to_absolute_path

output_folder = str(project_to_absolute_path('examples\\data')) + '\\'
input_folder = output_folder
input_mid_file = input_folder + 'BWV_784_16th_to_8th.mid'
output_bas_file = output_folder + 'BWV_784.bas'
output_prg_file = output_folder + 'BWV_784.prg'

chirp_song = chiptunesak.MIDI().to_chirp(input_mid_file, quantization='8', polyphony=False)

mchirp_song = chirp_song.to_mchirp()

basic = chiptunesak.C128Basic()

print(f'Writing {output_bas_file}...')
basic.to_file(
    mchirp_song,
    output_bas_file,
    instruments=['guitar', 'guitar', 'guitar'],
    rem_override="errata for c128 system guide p156 or c128 programmer's ref guide p343",
    format='bas')

print(f'Writing {output_prg_file}...')
basic.to_file(
    mchirp_song,
    output_prg_file,
    format='prg')  # Remembers instruments and rem_override settings from above
