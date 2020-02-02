# Convert midi .mid file into a goattracker .sng file
#
# TODOs:
# - 

from os import path
import toolsPath
import argparse
import ctsChirp
import ctsGTExport
import ctsMidiImport

def main():
    parser = argparse.ArgumentParser(description="Convert a midi file into a GoatTracker2 sng file.")
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('sng_out_file', help='sng filename to export')
    
    args = parser.parse_args()

    if not (args.midi_in_file.lower().endswith(r'.mid') or args.midi_in_file.lower().endswith(r'.midi')):
        parser.error(r'Expecting input filename that ends in ".mid"')
    if not path.exists(args.midi_in_file):
        parser.error('Cannot find "%s"' % args.midi_in_file)
    
    song = ctsMidiImport.midi_to_chirp(args.midi_in_file)
    song.estimate_quantization()
    song.quantize()
    song.remove_polyphony()

    ctsGTExport.chirp_to_GT(song, args.sng_out_file)
    
if __name__ == "__main__":
    main()
