import os
import subprocess
import chiptunesak
from chiptunesak.constants import project_to_absolute_path
from chiptunesak.sid import SID

"""
This example shows how to do metric modulation to remove triplets

TODO:
- Can now get the Skyfox data from ChiptuneSAK itself.  Rewrite lilypond export to use that data.
"""

file_name = 'Skyfox'
output_folder = str(project_to_absolute_path('examples/data/triplets/'))
input_folder = str(project_to_absolute_path('examples/sid/'))
input_sid_file = os.path.join(input_folder, file_name + '.sid')
output_mid_file = os.path.join(output_folder, file_name + '.mid')
output_mod_mid_file = os.path.join(output_folder, file_name + '_mod.mid')
output_ly_file = os.path.join(output_folder, file_name + '.ly')
output_ly_file_mod = os.path.join(output_folder, file_name + '_mod.ly')

sid = SID()
sid.set_options(
    sid_in_filename=input_sid_file,
    vibrato_cents_margin=0,
    seconds=100,  # Skyfox SID playback continues to repeat, 100 secs is enough
    verbose=True
)

rchirp_song = sid.to_rchirp()

# CSV shows 24 plays calls per quarter note
#   24 = 2^3 * 3, the factor of 3 is necessary for all the division-by-three rhythms
play_calls_per_quarter = 24
chirp_song = rchirp_song.to_chirp(milliframes_per_quarter=play_calls_per_quarter * 1000)

chirp_song.set_key_signature('G')
chirp_song.set_time_signature(4, 4)

chiptunesak.MIDI().to_file(chirp_song, project_to_absolute_path(output_mid_file))

# First thing, we rename the song
chirp_song.metadata.name = "SkyFox - Main Theme"
chirp_song.metadata.composer = "Douglas Fulton"

# Now name the tracks
for t, name in zip(chirp_song.tracks, ['Square1', 'Square2', 'Square3']):
    t.name = name

chirp_song.quantize(80, 80)
chirp_song.remove_polyphony()

mchirp_song = chirp_song.to_mchirp()
for track in mchirp_song.tracks:
    track.measures.pop()
chiptunesak.Lilypond().to_file(mchirp_song, output_ly_file, format='song')

# Change directory to the data directory so we don't fill the source directory with intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file)
# Run lilypond
subprocess.call('lilypond -o %s %s' % (output_folder, output_ly_file), shell=True)

chirp_song.modulate(3, 2)
chirp_song.quantize(120, 120)
chiptunesak.MIDI().to_file(chirp_song, output_mod_mid_file)

mchirp_song = chirp_song.to_mchirp()
chiptunesak.Lilypond().to_file(mchirp_song, output_ly_file_mod, format='song')

# Change directory to the data directory so we don't fill the source directory with intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file_mod)
# Run lilypond
subprocess.call('lilypond -o %s %s' % (output_folder, output_ly_file_mod), shell=True)
