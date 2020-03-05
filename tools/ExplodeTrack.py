import sys
import argparse
import os
import toolsPath
import ctsChirp
import ctsMidi

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

    song = ctsMidi.midi_to_chirp(args.midi_in_file)

    if args.tracknumber:
        print("Exploding track number %d" % args.tracknumber)
        song.explode_polyphony(args.tracknumber - 1)
    elif args.trackname:
        print("Exploding track %s" % args.trackname)
        for i, t in enumerate(song.tracks):
            if t == args.trackname:
                song.explode_polyphony(i)
                break
    else:
        print("No track specified")
        exit(1)

    ctsMidi.chirp_to_midi(song, args.midi_out_file)


if __name__ == '__main__':
    main()

