from os import path
import toolsPath
import argparse
import ctsGTImport
import ctsSong

def main():
    parser = argparse.ArgumentParser(description="Convert a GoatTracker2 sng file to a midi file.")
    parser.add_argument('sng_in_file', help='sng filename to import')
    parser.add_argument('midi_out_file', help='sng filename to import')
    parser.add_argument('-s', '--subtune_number', type=int, default=1,
        help='subtune number (default: 1)')
    
    args = parser.parse_args()

    if not args.sng_in_file.lower().endswith(r'.sng'):
        parser.error(r'Expecting input filename that ends in ".sng"')
    if not path.exists(args.sng_in_file):
        parser.error('Cannot find "%s"' % args.sng_in_file)
    sng_data = ctsGTImport.import_sng(args.sng_in_file)

    if args.subtune_number < 1:
        parser.error('subtune_number must be >= 1')
    max_subtune_number = len(sng_data.subtune_orderlists)
    if args.subtune_number > max_subtune_number:
        parser.error('subtune_number must be <= %d' % max_subtune_number)
     
    channels_time_events = ctsGTImport.convert_to_note_events(sng_data, args.subtune_number - 1)

    # ctsGTImport.print_note_time_data(channels_time_events)

    chirp_song = ctsGTImport.convert_to_chirp(channels_time_events, sng_data.headers.song_name)

    print(chirp_song.estimate_quantization())
    chirp_song.quantize()
    chirp_song.export_midi(args.midi_out_file)

if __name__ == "__main__":
    main()
