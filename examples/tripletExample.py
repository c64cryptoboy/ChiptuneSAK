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

sid_filename = project_to_absolute_path('examples/sid/Skyfox.sid')

sid = SID()
sid.set_options(
    sid_in_filename=sid_filename,
    vibrato_cents_margin=0,
    seconds=100,  # Skyfox SID playback continues to repeat, 100 secs is enough
    verbose=True
)

sid_dump = sid.capture()  # noqa: F841

# Notes:
# - between play calls, the voice gates are always on.  They breifly turn off and back on again
#   inside of play calls.  This is detected/handled by ChiptunesSAK.
# - Voice 2 does a portamento from F4 to B2 and back to F3 from frame (play call) 3792 to 3818,
#   during which, freq only seems to be updated every other frame.  Cent deviations are so small
#   that it looks like it was stored as individual notes, and not as a portamento effect.

filename_no_ext = 'examples/data/Skyfox'

csv_filename = '%s.csv' % filename_no_ext
print("writing %s" % csv_filename)
sid.to_csv_file(project_to_absolute_path(csv_filename))

midi_filename = '%s.mid' % filename_no_ext
print("writing %s" % midi_filename)
rchirp_song = sid.to_rchirp()

# CSV shows 24 plays calls per quarter note
#   24 = 2^3 * 3, the factor of 3 is necessary for all the division-by-three rhythms
play_calls_per_quarter = 24
chirp_song = \
    rchirp_song.to_chirp(milliframes_per_quarter=play_calls_per_quarter * 1000)

chirp_song.set_key_signature('G')
chirp_song.set_time_signature(6, 4)

chiptunesak.MIDI().to_file(
    chirp_song, project_to_absolute_path(midi_filename))

exit("early exit")

output_folder = str(project_to_absolute_path('examples\\data\\triplets')) + '\\'
input_folder = output_folder
input_mid_file = input_folder + 'skyfox.mid'
output_mid_file = output_folder + 'skyfox_mod.mid'
output_ly_file = output_folder + 'skyfox.ly'
output_ly_file_mod = output_folder + 'skyfox_mod.ly'

chirp_song = chiptunesak.MIDI().to_chirp(input_mid_file)

original_qpm = chirp_song.metadata.qpm
original_ppq = chirp_song.metadata.ppq

# First thing, we rename the song
chirp_song.metadata.name = "SkyFox - Main Theme"
chirp_song.metadata.composer = "Douglas Fulton"

# Now name the tracks
for t, name in zip(chirp_song.tracks, ['Square1', 'Square2', 'Square3']):
    t.name = name

chirp_song.scale_ticks(6.25)
chirp_song.metadata.ppq = 960
chirp_song.set_qpm(original_qpm * 1.25)
chirp_song.set_time_signature(4, 4)
chirp_song.set_key_signature('G')

chirp_song.quantize(80, 80)
chirp_song.remove_polyphony()

mchirp_song = chirp_song.to_mchirp()
chiptunesak.Lilypond().to_file(mchirp_song, output_ly_file, format='song')

# Change directory to the data directory so we don't fill the source directory with intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file)
# Run lilypond
subprocess.call('lilypond -o %s %s' % (output_folder, output_ly_file), shell=True)

chirp_song.modulate(3, 2)
chirp_song.quantize(120, 120)
chiptunesak.MIDI().to_file(chirp_song, output_mid_file)

mchirp_song = chirp_song.to_mchirp()
chiptunesak.Lilypond().to_file(mchirp_song, output_ly_file_mod, format='song')

# Change directory to the data directory so we don't fill the source directory with intermediate files.
os.chdir(output_folder)

# Adjust the path the the file
ly_file = os.path.basename(output_ly_file_mod)
# Run lilypond
subprocess.call('lilypond -o %s %s' % (output_folder, output_ly_file_mod), shell=True)
