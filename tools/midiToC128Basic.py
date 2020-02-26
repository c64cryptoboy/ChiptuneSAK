# Convert midi .mid file into Commodore 128 BASIC .bas (ascii text) or .prg (native) files
#
# TODOs:
# - command line to pick (or modify) default envelopes for the voices

import os
import toolsPath
import argparse
import ctsMidi
from ctsMChirp import MChirpSong
import ctsC128Basic
import ctsGenPrg


def main():
    parser = argparse.ArgumentParser(description="Convert a midi file into a C128 BASIC program.")
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('basic_out_file', help='filename to export')
    parser.add_argument('-t', '--type', choices=['bas', 'prg'], default='prg',
        help='basic output file type (default: prg)')
    parser.add_argument('-i', '--instruments', nargs=3, help="instrument names (3 required)")
    parser.add_argument('-a', '--arch', help="architecture (NTSC or PAL)")

    args = parser.parse_args()

    if not (args.midi_in_file.lower().endswith(r'.mid') or args.midi_in_file.lower().endswith(r'.midi')):
        parser.error(r'Expecting input filename that ends in ".mid"')
    if not os.path.exists(args.midi_in_file):
        parser.error('Cannot find "%s"' % args.midi_in_file)

    # midi -> mchirp
    # TODO: Remove hardcoding in this process
    song = ctsMidi.midi_to_chirp(args.midi_in_file)
    song.remove_control_notes(8)
    song.quantize_from_note_name('16')
    # TODO: transformMidi.py -q 32 -k Am ..\test\BWV_799.mid ..\test\BWV_799_q.mid
    #song.quantize_from_note_name('32')    
    song.remove_polyphony()
    ctsC128Basic.trim_note_lengths(song)
    if len(song.metadata.name) == 0:
        song.metadata.name = args.midi_in_file.split(os.sep)[-1].lower()
    mchirp_song = MChirpSong(song)

    instruments = ('piano', 'piano', 'piano')
    if args.instruments:
        instruments = (i.lower() for i in args.instruments)

    arch = 'NTSC'
    if args.arch:
        arch = args.arch

    # mchirp -> basic (ascii)
    program = ctsC128Basic.midi_to_C128_BASIC(mchirp_song, instruments, arch)

    if args.type == 'bas':
        with open(args.basic_out_file, 'w') as out_file:
            out_file.write(program)
    else: # 'prg'
        with open(args.basic_out_file, 'wb') as out_file:
            tokenized_program = ctsGenPrg.ascii_to_prg_c128(program)
            out_file.write(tokenized_program)

    print("\ndone")

if __name__ == "__main__":
    main()


