import sys
import sandboxPath
from ctsBase import *
import ctsMidi

song = ctsMidi.midi_to_chirp(sys.argv[1])

desired_ppq = 960
desired_q = 960 // 4
factor = 1.0


notes = [n for t in song.tracks for n in t.notes]

def objective_function(params):
    offset, scale_factor = params
    err = 0
    for n in notes:
        start = (n.start_time - offset) * scale_factor
        delta = quantization_error(start, desired_q)
        err += delta * delta / scale_factor
    return err


fstart = 960 / song.metadata.ppq / 2
fend = fstart * 2
f = fstart
offset_est = min(n.start_time for n in notes)
best_f = f
best_offset = offset_est
min_e = 1.e7
while f < fend:
    for offset in range(offset_est - 10, offset_est + 10):
        e = objective_function([offset, f])
        if e < min_e:
            min_e = e
            best_f = f
            best_offset = offset
        f += 0.001

print(best_f, best_offset, min_e)

song.move_ticks(-best_offset)
song.scale_ticks(best_f)
song.metadata.ppq = 960
song.quantize_from_note_name('16')
ctsMidi.chirp_to_midi(song, sys.argv[2])
