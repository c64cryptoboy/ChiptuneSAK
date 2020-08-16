import os
import subprocess
import chiptunesak
from chiptunesak.constants import project_to_absolute_path
from chiptunesak.sid import SID

"""
This example shows how to do metric modulation to remove triplets
"""

file_name = 'Skyfox'
output_folder = str(project_to_absolute_path('examples/data/triplets/'))
input_folder = str(project_to_absolute_path('examples/data/sid/'))
input_sid_file = os.path.join(input_folder, file_name + '.sid')
output_mid_file = os.path.join(output_folder, file_name + '.mid')
output_mod_mid_file = os.path.join(output_folder, file_name + '_mod.mid')
output_ly_file = os.path.join(output_folder, file_name + '.ly')
output_ly_file_mod = os.path.join(output_folder, file_name + '_mod.ly')

sid = SID()

# Skyfox SID playback continues to repeat, 100 secs is enough
rchirp_song = sid.to_rchirp(input_sid_file, seconds=100)

# CSV shows 24 plays calls per quarter note
#    24 = 2^3 * 3; the factor of 3 is necessary for all the division-by-three rhythms
play_calls_per_quarter = 24
chirp_song = rchirp_song.to_chirp(milliframes_per_quarter=play_calls_per_quarter * 1000)

# the song is in the key of G and 4/4 time
chirp_song.set_key_signature('G')
chirp_song.set_time_signature(4, 4)

# First thing, we rename the song and add the composer for printing sheet music
chirp_song.metadata.name = "SkyFox - Main Theme"
chirp_song.metadata.composer = "Douglas Fulton"

# Now name the tracks
for t, name in zip(chirp_song.tracks, ['Square1', 'Square2', 'Square3']):
    t.name = name
    t.set_program(81)  # Set program to General Midi square lead

# Quantize the song to a suitable granularity. It turns out we can quantize this to the shortest note duration
chirp_song.quantize(80, 80)

# And remove any polyphony
chirp_song.remove_polyphony()

# Write a MIDI file to look at to be sure it makes sense
chiptunesak.MIDI().to_file(chirp_song, project_to_absolute_path(output_mid_file))

# Convert to MChirp
mchirp_song = chirp_song.to_mchirp(trim_partial=True)

# Generate sheet music with LilyPond
chiptunesak.Lilypond().to_file(mchirp_song, output_ly_file, format='song')

# Change directory to the data directory so we don't fill the source directory with intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file)
# Run lilypond
print('lilypond -o %s %s' % (output_folder, output_ly_file))
subprocess.call('lilypond -o %s %s' % (output_folder, output_ly_file), shell=True)

# Now modulate the song to eliminate triplets
chirp_song.modulate(3, 2)
chirp_song.quantize(120, 120)
# And write the modulated MIDI file because why not?
chiptunesak.MIDI().to_file(chirp_song, output_mod_mid_file)

# Convert the modulated song to MChirp and make sheet music
mchirp_song = chirp_song.to_mchirp(trim_partial=True)
chiptunesak.Lilypond().to_file(mchirp_song, output_ly_file_mod, format='song')

# Change directory to the data directory so we don't fill the source directory with intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file_mod)
# Run lilypond
subprocess.call('lilypond -o %s %s' % (output_folder, output_ly_file_mod), shell=True)
