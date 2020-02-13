import sys
import argparse
from os import path
import toolsPath
import ctsChirp
import ctsMidi


def main():
    parser = argparse.ArgumentParser(description="Convert a midi file into a GoatTracker2 sng file.")
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('midi_out_file', help='midi filename to export')
    quant_group = parser.add_mutually_exclusive_group(required=False)
    quant_group.add_argument('-a', '--quantizeauto', action="store_true", help='Auto-quantize')
    quant_group.add_argument('-q', '--quantizenote', type=str, help='quantize to a note value')
    quant_group.add_argument('-t', '--quantizeticks', type=int, help='quantize to ticks')
    parser.add_argument('-b', '--bpm', type=int, help='set bpm')
    parser.add_argument('-r', '--removepolyphony', action="store_true", help='remove polyphony')
    parser.add_argument('-s', '--scaleticks', type=float, help='scale ticks')
    parser.add_argument('-m', '--moveticks', type=int, help='move ticks')
    parser.add_argument('-p', '--ppq', type=int, help='set ppq')

    args = parser.parse_args()

    if not (args.midi_in_file.lower().endswith(r'.mid') or args.midi_in_file.lower().endswith(r'.midi')):
        parser.error(r'Expecting input filename that ends in ".mid"')
    if not path.exists(args.midi_in_file):
        parser.error('Cannot find "%s"' % args.midi_in_file)

    song = ctsMidi.midi_to_chirp(args.midi_in_file)

    # Print stats
    print('%d notes' % (sum(len(t.notes) for t in song.tracks)))
    print('PPQ = %d' % (song.metadata.ppq))
    q_state = "" if song.is_quantized() else "not"
    p_state = "" if song.is_polyphonic() else "not"
    print("Input midi is %s quantized and %s polyphonic" % (q_state, p_state))

    print("Removing control notes...")
    song.remove_control_notes()

    if args.scaleticks:
        print("Scaling by %lf" % args.scaleticks)
        song.scale_ticks(args.scaleticks)
    if args.moveticks:
        print("Moving by %lf" % args.moveticks)
        song.move_ticks(-args.moveticks)

    if args.ppq:
        print("setting ppq to %d" % args.ppq)
        song.metadata.ppq = args.ppq

    if args.bpm:
        print("setting bpm to %d" % args.bpm)
        song.set_bpm(args.bpm)



    if args.quantizenote:
        print("Quantizing...")
        print("to note value %s" % args.quantizenote)
        song.quantize_from_note_name(args.quantizenote)
    elif args.quantizeticks:
        print("Quantizing...")
        print('to %d ticks' % args.quantizeticks)
        song.quantize(args.quantizeticks, args.quantizeticks)
    elif args.quantizeauto:
        print("Quantizing...")
        qticks_n, qticks_d = song.estimate_quantization()
        print('to estimated quantization: %d, %d  ticks' % (qticks_n, qticks_d))
        song.quantize(qticks_n, qticks_d)

    if args.removepolyphony:
        print("Eliminating polyphony...")
        song.remove_polyphony()

    q_state = "" if song.is_quantized() else "not"
    p_state = "" if song.is_polyphonic() else "not"
    print("ChirpSong is %s quantized and %s polyphonic" % (q_state, p_state))

    print('\n'.join("%24s %s" % (s, str(v)) for s, v in song.stats.items()))

    print("Exporting to MIDI...")
    ctsMidi.chirp_to_midi(song, args.midi_out_file)


if __name__ == '__main__':
    main()