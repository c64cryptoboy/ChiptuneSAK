import chiptunesak
from chiptunesak.constants import project_to_absolute_path

"""
This minimal example imports a GoatTracker song and exports as MIDI.

"""

# Set up input and output paths
output_folder = str(project_to_absolute_path('examples\\data\\BWV_147')) + '\\'
input_folder = output_folder
input_file = str(project_to_absolute_path(input_folder + 'BWV_147_Bleibet.sng'))
output_midi_file = str(project_to_absolute_path(output_folder + 'BWV_147_Bleibet.mid'))

# Read in the song using the GoatTracker I/O class
print(f'Reading and converting {input_file}')
rchirp_song = chiptunesak.GoatTracker().to_rchirp(input_file, arch='PAL-C64')

# The song has a ritard at the end that will mess up the algorithm finding the beat, so eliminate it.
print(f'Removing the ritard at the end of the song')
rchirp_song.remove_tempo_changes()

# Turn the song into a ChirpSong object
print(f'Converting from RChirp to Chirp')
chirp_song = rchirp_song.to_chirp()

# We know the key signature and the time signature for the piece so set them (not required for playback)
print(f'Setting time and key signatures')
chirp_song.set_key_signature('G')
chirp_song.set_time_signature(3, 8)

# And write it to a MIDI file.
print(f'Writing to MIDI file {output_midi_file}')
chiptunesak.MIDI().to_file(chirp_song, output_midi_file)
