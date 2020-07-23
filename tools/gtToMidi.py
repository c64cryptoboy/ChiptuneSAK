# Convert goattracker .sng file into a midi .mid file

import argparse

from chiptunesak import goat_tracker
from chiptunesak import midi


def main():
    parser = argparse.ArgumentParser(description="Convert a GoatTracker2 sng file to a midi file.")
    parser.add_argument('sng_in_file', help='sng filename to import')
    parser.add_argument('midi_out_file', help='midi filename to export')
    parser.add_argument(
        '-s', '--subtune_number', type=int, default=0, help='subtune number (default: 0)'
    )

    args = parser.parse_args()

    rchirp_song = goat_tracker.GoatTracker().to_rchirp(args.sng_in_file, subtune=args.subtune_number)

    """
    cvs_filename = '%s.csv' % (args.sng_in_file.split('.')[0])
    with open(cvs_filename, 'w') as out_file:
        out_file.write(rchirp_song.note_time_data_str())
    """

    chirp_song = rchirp_song.to_chirp()

    # TODO:  Allow time signature to be set here?
    midi.MIDI().to_file(chirp_song, args.midi_out_file)

    print("\ndone")


if __name__ == "__main__":
    main()
