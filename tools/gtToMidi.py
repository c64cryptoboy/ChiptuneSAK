# Convert goattracker .sng file into a midi .mid file
#
# TODOs:
# - Need to consider inferring time signature and/or having the user be able to set it

from os import path
import toolsPath
import argparse
import ctsGoatTracker
import ctsMidi

def main():
    parser = argparse.ArgumentParser(description="Convert a GoatTracker2 sng file to a midi file.")
    parser.add_argument('sng_in_file', help='sng filename to import')
    parser.add_argument('midi_out_file', help='midi filename to export')
    parser.add_argument('-s', '--subtune_number', type=int, default=0,
        help='subtune number (default: 0)')
    
    args = parser.parse_args()

    rchirp_song = ctsGoatTracker.import_sng_file_to_rchirp(args.sng_in_file, args.subtune_number)

    """
    cvs_filename = '%s.csv' % (args.sng_in_file.split('.')[0])
    with open(cvs_filename, 'w') as out_file:
        out_file.write(rchirp_song.note_time_data_str())
    """

    #chirp_song = ctsGoatTracker.convert_to_chirp(sng_data.num_channels, channels_time_events, sng_data.headers.song_name)
    chirp_song = rchirp_song.convert_to_chirp()

    # TODO:  Need to consider inferring time signature and/or having the user be able to set it
    # chirp_song.time_signature_changes.insert(0, ctsSong.TimeSignature(0, 3, 4))
    
    ctsMidi.export_chirp_to_midi(chirp_song, args.midi_out_file)

    print("\ndone")
    
if __name__ == "__main__":
    main()
