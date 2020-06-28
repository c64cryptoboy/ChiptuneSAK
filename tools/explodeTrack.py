import argparse
import os
from chiptunesak import midi


def main():
    parser = argparse.ArgumentParser(description="Explode MIDI track.")
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('midi_out_file', help='midi filename to export')
    track_group = parser.add_mutually_exclusive_group(required=False)
    track_group.add_argument('-n', '--tracknumber', type=int, help='track number (first track is 1)')
    track_group.add_argument('-t', '--trackname', type=str, help='track name')

    args = parser.parse_args()

    if not (args.midi_in_file.lower().endswith(r'.mid') or args.midi_in_file.lower().endswith(r'.midi')):
        parser.error(r'Expecting input filename that ends in ".mid"')
    if not os.path.exists(args.midi_in_file):
        parser.error('Cannot find "%s"' % args.midi_in_file)

    song = midi.MIDI().to_chirp(args.midi_in_file)

    if args.tracknumber:
        print("Exploding track number %d" % args.tracknumber)
        song.explode_polyphony(args.tracknumber - 1)
    elif args.trackname:
        it = next((it for it, t in enumerate(song.tracks) if t.name == args.trackname), None)
        if it is None:
            print("Track %s not found" % args.trackname)
            exit(1)
        else:
            print("Exploding track %s" % song.tracks[it].name)
            song.explode_polyphony(it)
    else:
        print("No track specified")
        exit(1)

    midi.MIDI().to_file(song, args.midi_out_file)


if __name__ == '__main__':
    main()
