import copy
import argparse
import os

from chiptunesak.errors import ChiptuneSAKValueError
from chiptunesak import midi


def main():
    parser = argparse.ArgumentParser(description="Reorder MIDI tracks.")
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('midi_out_file', help='midi filename to export')
    parser.add_argument('track_order', type=int, nargs='*', help='new order (first track is track 1)')

    args = parser.parse_args()

    if not (args.midi_in_file.lower().endswith(r'.mid') or args.midi_in_file.lower().endswith(r'.midi')):
        parser.error(r'Expecting input filename that ends in ".mid"')
    if not os.path.exists(args.midi_in_file):
        parser.error('Cannot find "%s"' % args.midi_in_file)

    song = midi.MIDI().to_chirp(args.midi_in_file)

    if max(args.track_order) > len(song.tracks):
        raise ChiptuneSAKValueError("Illegal track specified: only %d tracks in song" % len(song.tracks))

    old_tracks = copy.deepcopy(song.tracks)

    new_tracks = [old_tracks[it - 1] for it in args.track_order]
    song.tracks = new_tracks

    print("New track order:")
    print("\n".join(t.name for t in song.tracks))

    print("Writing to midi file %s" % args.midi_out_file)
    midi.MIDI().to_file(song, args.midi_out_file)


if __name__ == '__main__':
    main()
