import sys
import argparse
from os import path
import toolsPath
import ctsChirp
import ctsMidiImport
import ctsMidiExport


def main():
    parser = argparse.ArgumentParser(description="Convert a midi file into a GoatTracker2 sng file.")
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('midi_out_file', help='midi filename to export')
    quant_group = parser.add_mutually_exclusive_group(required=False)
    quant_group.add_argument('-q', '--quantizenote', type=str, help='quantize to a note value')
    quant_group.add_argument('-t', '--quantizeticks', type=int, help='quantize to ticks')

    args = parser.parse_args()

    if not (args.midi_in_file.lower().endswith(r'.mid') or args.midi_in_file.lower().endswith(r'.midi')):
        parser.error(r'Expecting input filename that ends in ".mid"')
    if not path.exists(args.midi_in_file):
        parser.error('Cannot find "%s"' % args.midi_in_file)

    song = ctsMidiImport.midi_to_chirp(args.midi_in_file)

    # Print stats
    print('%d notes' % (sum(len(t.notes) for t in song.tracks)))
    print('PPQ = %d' % (song.metadata.ppq))
    q_state = "" if song.is_quantized() else "not"
    p_state = "" if song.is_polyphonic() else "not"
    print("Input midi is %s quantized and %s polyphonic" % (q_state, p_state))

    print("Removing control notes...")
    song.remove_control_notes()

    print("Quantizing...")
    if args.quantizenote:
        print("to note value %s" % args.quantizenote)
        song.quantize_from_note_name(args.quantizenote)
    elif args.quantizeticks:
        print('to %d ticks' % args.quantizeticks)
        song.quantize(args.quantizeticks, args.quantizeticks)
    else:
        qticks_n, qticks_d = song.estimate_quantization()
        print('to estimated quantization: %d, %d  ticks' % (qticks_n, qticks_d))
        song.quantize(qticks_n, qticks_d)


    print("Eliminating polyphony...")
    song.remove_polyphony()
    # inMidi.modulate(3, 2)

    q_state = "" if song.is_quantized() else "not"
    p_state = "" if song.is_polyphonic() else "not"
    print("ChirpSong is %s quantized and %s polyphonic" % (q_state, p_state))

    print('\n'.join("%24s %s" % (s, str(v)) for s, v in song.stats.items()))

    print("Exporting to MIDI...")
    ctsMidiExport.chirp_to_midi(song, args.midi_out_file)


if __name__ == '__main__':
    main()