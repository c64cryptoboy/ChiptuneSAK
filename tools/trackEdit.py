import argparse
from os import path

from chiptunesak import midi


def main():
    parser = argparse.ArgumentParser(description="Perform operations on individual tracks of MIDI files.",
                                     epilog="Operations are performed in the order given in this help.")
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('midi_out_file', help='midi filename to export')
    parser.add_argument('track', type=str, help='Track either number (starting with 1) or name')
    parser.add_argument('-n', '--name', type=str, help='Set track name')
    quant_group = parser.add_mutually_exclusive_group(required=False)
    quant_group.add_argument('-a', '--quantizeauto', action="store_true", help='Auto-quantize')
    quant_group.add_argument('-q', '--quantizenote', type=str, help='quantize to a note value')
    quant_group.add_argument('-c', '--quantizeticks', type=int, help='quantize to ticks')
    quant_group.add_argument('-d', '--quantizelongticks', type=int, help='quantize long notes to ticks')
    parser.add_argument('-m', '--merge', type=int, help='merge track (max num ticks to merge)')
    short_note_group = parser.add_mutually_exclusive_group(required=False)
    short_note_group.add_argument('-r', '--removeshort', type=int, help='remove notes <= tick value')
    short_note_group.add_argument('-l', '--setminnotelen', type=int, help='set the minimum note length to tick value,'
                                                                          ' possibly consuming portion of '
                                                                          'following note')

    args = parser.parse_args()

    if not (args.midi_in_file.lower().endswith(r'.mid') or args.midi_in_file.lower().endswith(r'.midi')):
        parser.error('Expecting input filename that ends in ".mid"')
    if not path.exists(args.midi_in_file):
        parser.error('Cannot find "%s"' % args.midi_in_file)

    song = midi.MIDI().to_chirp(args.midi_in_file)

    track = None
    if all(t.isdigit() for t in args.track):
        track = song.tracks[int(args.track) - 1]
        print("Editing track %d" % int(args.track))
    else:
        for t in song.tracks:
            if t.name == args.track:
                track = t
        if track is None:
            print('Track %s not found. Available tracks:')
            for t in song.tracks:
                print(t.name)
            parser.error('No track named %s found.' % args.track)

    if args.name:
        track.name = args.name

    if args.quantizelongticks:
        print("Quantizing long notes to %d" % args.quantizelongticks)
        track.quantize_long(args.quantizelongticks)

    if args.removeshort:
        print("Removing notes under %d ticks" % args.removeshort)
        track.remove_short_notes(args.removeshort)

    if args.setminnotelen:
        print("Setting minimum note length to %d" % args.setminnotelen)
        track.set_min_note_len(args.setminnotelen)

    if args.merge:
        print("Merging notes under %d" % args.merge)
        track.merge_notes(args.merge)

    print("Exporting to MIDI...")
    midi.MIDI().to_file(song, args.midi_out_file)


if __name__ == '__main__':
    main()
