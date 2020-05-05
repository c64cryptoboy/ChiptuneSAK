import sys
import argparse
import subprocess
from os import path
import toolsPath
import ctsMidi
from ctsMChirp import MChirpSong
import ctsLilypond

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

    exporter = ctsLilypond.LilypondExporter()

    autosort = False
    if args.autosort:
        exporter.options['Autosort'] = True

    print("Reading %s" % args.midi_in_file)
    chirp_song = ctsMidi.import_midi_to_chirp(args.midi_in_file)
    print("Removing control notes...")
    chirp_song.remove_keyswitches()
    print("Quantizing...")
    qticks_n, qticks_d = chirp_song.estimate_quantization()
    print(qticks_n, qticks_d)
    chirp_song.quantize(qticks_n, qticks_d)
    print("Removing polyphony...")
    chirp_song.remove_polyphony()

    print('Converting to measures...')
    mchirp_song = MChirpSong(chirp_song)
    print('Generating lilypond...')
    ly_out = exporter.export_str(mchirp_song)
    ly_name = args.midi_in_file.replace('.mid', '.ly')
    print("Writing lilypond to %s" % ly_name)
    with open(ly_name, 'w') as f:
        f.write(ly_out)

    subprocess.call('lilypond -o %s %s' % (args.out_folder, ly_name), shell=True)

    print("\ndone")

if __name__ == '__main__':
    main()