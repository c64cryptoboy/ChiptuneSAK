import argparse
from os import path

from chiptunesak import midi


def main():
    parser = argparse.ArgumentParser(
        description="Perform transformations on MIDI files.",
        epilog="Operations are performed in the order given in this help."
    )
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('midi_out_file', help='midi filename to export')
    parser.add_argument('-n', '--name', type=str, help='set name of song')
    parser.add_argument('-z', '--removekeyswitchnotes', action="store_true", help='remove keyswitch notes')
    parser.add_argument('-s', '--scaleticks', type=float, help='scale ticks')
    parser.add_argument('-x', '--moveticks', type=str, help='move ticks lXXXX for left and rXXXX for right')
    parser.add_argument('-p', '--ppq', type=int, help='set ppq')
    parser.add_argument('-m', '--modulate', type=str, help='modulate by n/d')
    parser.add_argument('-t', '--transpose', type=str,
                        help='transpose by semitones (uXX or dXX for up or down XX semitones)')
    quant_group = parser.add_mutually_exclusive_group(required=False)
    quant_group.add_argument('-a', '--quantizeauto', action="store_true", help='Auto-quantize')
    quant_group.add_argument('-q', '--quantizenote', type=str, help='quantize to a note value')
    quant_group.add_argument('-c', '--quantizeticks', type=int, help='quantize to ticks')
    parser.add_argument('-r', '--removepolyphony', action="store_true", help='remove polyphony')
    parser.add_argument('-b', '--qpm', type=int, help='set qpm')
    parser.add_argument('-j', '--timesignature', type=str, help='set time signature e.g. 3/4')
    parser.add_argument('-k', '--keysignature', type=str, help='set key signature, e.g. D, F#m')

    args = parser.parse_args()

    if not (args.midi_in_file.lower().endswith(r'.mid') or args.midi_in_file.lower().endswith(r'.midi')):
        parser.error(r'Expecting input filename that ends in ".mid"')
    if not path.exists(args.midi_in_file):
        parser.error('Cannot find "%s"' % args.midi_in_file)

    song = midi.MIDI().to_chirp(args.midi_in_file)

    # Print stats
    print('%d notes' % (sum(len(t.notes) for t in song.tracks)))
    print('PPQ = %d' % (song.metadata.ppq))
    q_state = "" if song.is_quantized() else "not"
    p_state = "" if song.is_polyphonic() else "not"
    print("Input midi is %s quantized and is %s polyphonic" % (q_state, p_state))

    if args.name:
        print("Renaming song to %s" % args.name)
        song.metadata.name = args.name

    if args.removekeyswitchnotes:
        print("Removing control notes...")
        song.remove_keyswitches()

    if args.scaleticks:
        print("Scaling by %lf" % args.scaleticks)
        song.scale_ticks(args.scaleticks)

    if args.moveticks:
        move = args.moveticks
        if move[0] == 'l':
            v = -int(move[1:])
        elif move[0].isdigit():
            v = int(move)
        else:
            v = int(move[1:])
        print("Moving by %d" % v)
        song.move_ticks(v)

    if args.ppq:
        print("setting ppq to %d" % args.ppq)
        song.metadata.ppq = args.ppq

    if args.modulate:
        num, denom = (int(n) for n in args.modulate.split('/'))
        print("modulating by %d/%d" % (num, denom))
        song.modulate(num, denom)

    if args.transpose:
        if args.transpose[0] == 'd':
            transpose = -int(args.transpose[1:])
        else:
            transpose = int(args.transpose[1:])
        print("transposing by %d" % transpose)
        song.transpose(transpose)

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

    if args.qpm:
        print("Setting qpm to %d" % args.qpm)
        song.set_qpm(args.qpm)

    if args.timesignature:
        num, denom = (int(x) for x in args.timesignature.split('/'))
        if num > 0 and denom > 0:
            print('Setting time signature to %d/%d' % (num, denom))
            song.set_time_signature(num, denom)

    if args.keysignature:
        print('Setting key signature to %s' % args.keysignature)
        song.set_key_signature(args.keysignature)

    q_state = "" if song.is_quantized() else "not"
    p_state = "" if song.is_polyphonic() else "not"
    print("Output ChirpSong is %s quantized and %s polyphonic" % (q_state, p_state))

    print("Exporting to MIDI...")

    midi.MIDI().to_file(song, args.midi_out_file)


if __name__ == '__main__':
    main()
