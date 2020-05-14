# Convert midi .mid file into a goattracker .sng file
#
# TODOs:
# - 

from os import path
import toolsPath
import argparse
import ctsChirp
import ctsGoatTracker
import ctsMidi
from ctsErrors import ChiptuneSAKValueError

def main():
    parser = argparse.ArgumentParser(description="Convert a midi file into a GoatTracker2 sng file.")
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('sng_out_file', help='sng filename to export')
    
    args = parser.parse_args()

    if not (args.midi_in_file.lower().endswith(r'.mid') or args.midi_in_file.lower().endswith(r'.midi')):
        parser.error(r'Expecting input filename that ends in ".mid"')
    if not path.exists(args.midi_in_file):
        parser.error('Cannot find "%s"' % args.midi_in_file)
    
    song = ctsMidi.MIDI().to_chirp(args.midi_in_file)
    
    # generic approach (when quantizable):
    # song.estimate_quantization()
    # song.quantize()

    # For Bleibet (due to rit), do line below instead of above two lines
    # song.quantize_from_note_name("16")

    # For Minuet_106_6ch.mid
    # song.quantize_from_note_name("16")

    # For The-Speedwalker.mid
    song.quantize(60, 60)
    # song.quantize(120, 120)

    song.remove_polyphony()

    if len(song.tracks) > 6:
        raise ChiptuneSAKValueError("Error: GoatTracker doesn't support more than 6 channels")
    tracks_to_include = list(range(1, len(song.tracks)+1))

    is_stereo = len(song.tracks) > 3

    rchirp_song = song.to_rchirp()
    ctsGoatTracker.GoatTracker().to_file(rchirp_song, args.sng_out_file)

    print("\ndone")


if __name__ == "__main__":
    main()
