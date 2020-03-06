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
    parser.add_argument('-s', '--subtune_number', type=int, default=1,
        help='subtune number (default: 1)')
    
    args = parser.parse_args()

    if not args.sng_in_file.lower().endswith(r'.sng'):
        parser.error(r'Expecting input filename that ends in ".sng"')
    if not path.exists(args.sng_in_file):
        parser.error('Cannot find "%s"' % args.sng_in_file)
    sng_data = ctsGoatTracker.import_sng(args.sng_in_file)

    if args.subtune_number < 1:
        parser.error('subtune_number must be >= 1')
    max_subtune_number = len(sng_data.subtune_orderlists)
    if args.subtune_number > max_subtune_number:
        parser.error('subtune_number must be <= %d' % max_subtune_number)
     
    channels_time_events = ctsGoatTracker.convert_to_note_events(sng_data, args.subtune_number - 1)

    chirp_song = ctsGoatTracker.convert_to_chirp(sng_data.num_channels, channels_time_events, sng_data.headers.song_name)
    # TODO:  Need to consider inferring time signature and/or having the user be able to set it
    #ts = ctsSong.TimeSignature(0, 3, 4)
    #chirp_song.time_signature_changes.insert(0, ts)
    ctsMidi.chirp_to_midi(chirp_song, args.midi_out_file)

    print("\ndone")
    
if __name__ == "__main__":
    main()
