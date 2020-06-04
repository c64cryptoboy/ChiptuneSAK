# Convert midi .mid file into Commodore 128 BASIC .bas (ascii text) or .prg (native) files

import os
import toolsPath
import ctsConstants
import argparse
import ctsMidi
from ctsMChirp import MChirpSong
import ctsC128Basic
import ctsGenPrg


def main():
    parser = argparse.ArgumentParser(
        description="Convert a midi file into a C128 BASIC program."
    )
    parser.add_argument("midi_in_file", help="midi filename to import")
    parser.add_argument("basic_out_file", help="filename to export")
    parser.add_argument(
        "-t",
        "--type",
        choices=["bas", "prg"],
        help="basic output file type (default: prg)",
    )
    parser.add_argument(
        "-i", "--instruments", nargs=3, help="instrument names (3 required)"
    )
    parser.add_argument("-a", "--arch", help="architecture (NTSC or PAL)")

    args = parser.parse_args()

    if not (
        args.midi_in_file.lower().endswith(r".mid")
        or args.midi_in_file.lower().endswith(r".midi")
    ):
        parser.error(r'Expecting input filename that ends in ".mid"')
    if not os.path.exists(args.midi_in_file):
        parser.error('Cannot find "%s"' % args.midi_in_file)

    # midi -> mchirp

    # song = ctsMidi.import_midi_to_chirp(args.midi_in_file) # TODO remove this line
    song = ctsMidi.MIDI().to_chirp(args.midi_in_file)

    song.remove_keyswitches(8)
    song.quantize_from_note_name("16")
    # transformMidi.py -q 32 -k Am ..\test\BWV_799.mid ..\test\BWV_799_q.mid
    # song.quantize_from_note_name('32')
    song.remove_polyphony()

    ctsC128Basic.trim_note_lengths(song)

    if len(song.metadata.name) == 0:
        song.metadata.name = args.midi_in_file.split(os.sep)[-1].lower()

    # chirp -> mchirp

    # mchirp_song = MChirpSong(song) # TODO remove this line
    mchirp_song = song.to_mchirp()

    # mchirp -> C128 Basic

    instruments = ("piano", "piano", "piano")
    if args.instruments:
        instruments = (i.lower() for i in args.instruments)

    arch = ctsConstants.DEFAULT_ARCH
    if args.arch:
        arch = args.arch

    # if -t flag not used, look at output filename extension
    if args.type is None:
        if args.basic_out_file.lower().endswith(".bas"):
            args.type = "bas"
        else:
            args.type = "prg"

    basic_converter = ctsC128Basic.C128Basic()
    basic_converter.set_options(
        arch=args.arch, format=args.type, instruments=instruments
    )
    basic_converter.to_file(mchirp_song, args.basic_out_file)

    print("\ndone")


if __name__ == "__main__":
    main()
