# Convert midi .mid file into a goattracker .sng file
#
# TODOs:
# - Derive BPM or allow to be set via command line

from os import path
import toolsPath
import argparse
import ctsChirp
import ctsExportGT

def main():
    parser = argparse.ArgumentParser(description="Convert a midi file into a GoatTracker2 sng file.")
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('sng_out_file', help='sng filename to export')
    
    args = parser.parse_args()

    if not (args.midi_in_file.lower().endswith(r'.mid') or args.midi_in_file.lower().endswith(r'.midi')):
        parser.error(r'Expecting input filename that ends in ".mid"')
    if not path.exists(args.midi_in_file):
        parser.error('Cannot find "%s"' % args.midi_in_file)
    
    #in_midi = ctsChirp.ChirpSong()
    #in_midi.import_midi(args.midi_in_file)
    song = ctsChirp.ChirpSong(args.midi_in_file)

    # TODO: Derive these and/or allow to be set via command line
    song.quantize(240, 240)
    song.remove_polyphony()
    song.bpm = 90
    
    ctsExportGT.chirp_to_GT(song, args.sng_out_file)

if __name__ == "__main__":
    main()
