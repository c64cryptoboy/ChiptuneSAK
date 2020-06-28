import argparse
import subprocess

from chiptunesak import midi
from chiptunesak.lilypond import Lilypond

"""
Prints a MIDI file to Lilypond sheet music.

NOTE:  You must have lilypond in your path for this script to work.
"""


def main():
    parser = argparse.ArgumentParser(description="Convert song into Lilypond score")
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('out_folder', help='output folder')
    parser.add_argument('-a', '--autosort', action="store_true", help='automatically sort staves by average note')

    args = parser.parse_args()

    lp = Lilypond()

    if args.autosort:
        lp.set_options(autosort="True")

    print("Reading %s" % args.midi_in_file)
    chirp_song = midi.MIDI().to_chirp(args.midi_in_file, quantization='auto', polyphony=False)

    print('Converting to measures...')
    mchirp_song = chirp_song.to_mchirp()
    print('Generating lilypond...')
    ly_name = args.midi_in_file.replace('.mid', '.ly')
    lp.to_file(mchirp_song, ly_name)

    subprocess.call('lilypond -o %s %s' % (args.out_folder, ly_name), shell=True)

    print("\ndone")


if __name__ == '__main__':
    main()
