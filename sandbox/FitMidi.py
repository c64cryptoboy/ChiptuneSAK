import sys
import sandboxPath
from ctsBase import *
import ctsMidi

""" This module contains an algorithm to estimate offset and scale factors for MIDI songs that do not have
    an accurate ppq.  It attempts to infer the ppq from the note starts alone, assuming a minimum note-to-note
    interval of a 16th note.  It then writes out an adjusted midi file set to a ppq of 960 for that inferred
    16th note speed.
"""

song = ctsMidi.midi_to_chirp(sys.argv[1])

desired_ppq = 960
desired_q = 960 // 4  # Sixteenth notes are the target here.

notes = [n for t in song.tracks for n in t.notes]

def objective_function(offset, scale_factor):
    err = 0
    for n in notes:
        start = (n.start_time - offset) * scale_factor
        delta = quantization_error(start, desired_q)
        err += abs(delta)
    return err

def find_best_f(f_start, f_end, step, offset):
    min_e = objective_function(offset, f_start)
    best_f = f_start
    n_steps = int((f_end - f_start) // step) + 1
    for i in range(n_steps):
        f = f_start + i * step
        e = objective_function(offset, f)
        if e < min_e:
            min_e = e
            best_f = f
    return (best_f, min_e)

def find_best_offset(o_start, o_end, f):
    min_e = objective_function(o_start, f)
    best_offset = o_start
    n_steps = (o_end - o_start)
    for offset in range(o_start, o_end + 1):
        e = objective_function(offset, f)
        if e < min_e:
            min_e = e
            best_offset = offset
    return (best_offset, min_e)

f_min = round(960 / song.metadata.ppq / 2, 3)
f_max = f_min * 4
f_step = .01
offset_est = min(n.start_time for n in notes)
last_min_e = 1.e9
best_f, min_e = find_best_f(f_min, f_max, f_step, offset_est)
best_offset, min_e = find_best_offset(offset_est - 20, offset_est + 20, best_f)

while min_e < last_min_e:
    last_min_e = min_e
    f_step /= 10.
    f_min = best_f - (f_step * 100)
    f_max = best_f + (f_step * 100)
    best_f, min_e = find_best_f(f_min, f_max, f_step, best_offset)
    best_offset, min_e = find_best_offset(offset_est - 20, offset_est + 20, best_f)

tick_error = min_e / len(notes)
print("scale_factor = %.5lf, offset = %d, total error = %.1lf ticks (%.2lf ticks/note for ppq = 960)"
      % (best_f, best_offset, min_e, tick_error))

song.move_ticks(-best_offset)
song.scale_ticks(best_f)
song.metadata.ppq = 960
#song.quantize_from_note_name('16')
ctsMidi.chirp_to_midi(song, sys.argv[2])
