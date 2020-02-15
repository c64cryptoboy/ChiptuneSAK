import sys
import argparse
import functools
import sandboxPath
from ctsBase import *
from ctsConstants import DURATION_STR
import ctsMidi

""" This module contains an algorithm to estimate offset and scale factors for MIDI songs that do not have
    an accurate ppq.  It attempts to infer the ppq from the note starts alone, assuming a minimum note-to-note
    interval of a 16th note.  It then writes out an adjusted midi file set to a ppq of 960 for that inferred
    16th note speed.  
    
    NOTE:  This function does NOT quantize the song.  It puts it into a state from which it may be quantized, but 
    does not perform any quantization.
"""


def objective_function(notes, desired_q, offset, scale_factor):
    err = 0
    for n in notes:
        start = (n.start_time - offset) * scale_factor
        delta = quantization_error(start, desired_q)
        err += abs(delta)
    return err


def find_best_f(notes, desired_q, f_start, f_end, step, offset):
    min_e = objective_function(notes, desired_q, offset, f_start)
    best_f = f_start
    n_steps = int((f_end - f_start) // step) + 1
    for i in range(n_steps):
        f = f_start + i * step
        e = objective_function(notes, desired_q, offset, f)
        if e < min_e:
            min_e = e
            best_f = f
    return (best_f, min_e)


def find_best_offset(notes, desired_q, o_start, o_end, f):
    min_e = objective_function(notes, desired_q, o_start, f)
    best_offset = o_start
    n_steps = (o_end - o_start)
    for offset in range(o_start, o_end + 1):
        e = objective_function(notes, desired_q, offset, f)
        if e < min_e:
            min_e = e
            best_offset = offset
    return (best_offset, min_e)


def main():
    parser = argparse.ArgumentParser(description="Fit best PPQ value for MIDI files.")
    parser.add_argument('midi_in_file', help='midi filename to import')
    parser.add_argument('midi_out_file', help='midi filename to export')
    parser.add_argument('-p', '--ppq', type=int, default=960, nargs='?', help='preferred PPQ (default = 960)')
    parser.add_argument('-m', '--minnote', type=str, default='16', nargs='?', help='minimum interval name (default = 16)')

    args = parser.parse_args()

    desired_ppq = args.ppq
    desired_q = desired_ppq * DURATION_STR[args.minnote]

    print("Reading file %s" % args.midi_out_file)
    song = ctsMidi.midi_to_chirp(args.midi_in_file)
    notes = [n for t in song.tracks for n in t.notes]

    f_min = round(desired_ppq / song.metadata.ppq / 2, 3)
    f_max = f_min * 8.
    f_step = .01
    offset_est = min(n.start_time for n in notes)
    last_min_e = 1.e9
    print('Finding initial parameters...')
    best_f, min_e = find_best_f(notes, desired_q, f_min, f_max, f_step, offset_est)
    best_offset, min_e = find_best_offset(notes, desired_q, offset_est - 20, offset_est + 20, best_f)

    print('Refining...')
    while min_e < last_min_e:
        last_min_e = min_e
        f_step /= 10.
        f_min = best_f - (f_step * 100)
        if (f_min < 1.0):
            f_min = 1.0
        f_max = f_min + (f_step * 200)
        best_f, min_e = find_best_f(notes, desired_q, f_min, f_max, f_step, best_offset)
        best_offset, min_e = find_best_offset(notes, desired_q, offset_est - 20, offset_est + 20, best_f)

    tick_error = min_e / len(notes)
    print("scale_factor = %.5lf, offset = %d, total error = %.1lf ticks (%.2lf ticks/note for ppq = %d)"
          % (best_f, best_offset, min_e, tick_error, desired_ppq))

    song.move_ticks(-best_offset)
    song.scale_ticks(best_f)
    song.metadata.ppq = desired_ppq
    # song.quantize_from_note_name('16')
    print("Writing file %s" % args.midi_out_file)
    ctsMidi.chirp_to_midi(song, args.midi_out_file)


if __name__ == '__main__':
    main()
