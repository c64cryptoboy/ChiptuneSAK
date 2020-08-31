# Make a SID for Jim Happel's last-minute CRX demo...

import chiptunesak
from chiptunesak.constants import project_to_absolute_path

input_mid_file = project_to_absolute_path('examples\\data\\c128\\BWV_784_16th_to_8th.mid')
output_gt_file = project_to_absolute_path('examples\\temp\\BWV_784.sng')

chirp_song = chiptunesak.MIDI().to_chirp(input_mid_file, quantization='8', polyphony=False)

rchirp_song = chiptunesak.RChirpSong(chirp_song)
gt = chiptunesak.GoatTracker()

# TODO:  Dang, end_with_repeat=True seems to create an unplayable song.  Fix this 
# after CRX
# gt.to_file(rchirp_song, output_gt_file, arch='NTSC-C64', end_with_repeat=True)
gt.to_file(rchirp_song, output_gt_file, arch='NTSC-C64')

