import sys
import examplesPath
from ctsBase import *
import ctsMidi
import ctsLilypond
import ctsOnePassCompress
import ctsGoatTracker
from ctsConstants import project_to_absolute_path

"""
This example imports a GoatTracker song to MIDI.  It is a minimal example.
"""

output_folder = str(project_to_absolute_path('examples\\data\\bleibet')) + '\\'
input_folder = output_folder
input_file = str(project_to_absolute_path(input_folder + 'bleibet.sng'))
output_midi_file = str(project_to_absolute_path(output_folder + 'bleibet.mid'))


# Read in the song using the GoatTracker I/O class
rchirp_song = ctsGoatTracker.GoatTracker().to_rchirp(input_file, arch='PAL-C64')

# The song has a ritard at the end that will mess up the algorithm finding the beat, so eliminate it.
rchirp_song.remove_tempo_changes()

# Turn the song into a ChirpSong object
chirp_song = rchirp_song.to_chirp()

# We know the key signature and the time signature for the piece so set them (not required for playback)
chirp_song.set_key_signature('G')
chirp_song.set_time_signature(3, 8)

# And write it to a MIDI file.
ctsMidi.MIDI().to_file(chirp_song, output_midi_file)
