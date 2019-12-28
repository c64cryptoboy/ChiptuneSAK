import sys
import numpy as np
import matplotlib.pyplot as plt
import MidiSimple
import collections

def save_stats(in_song):
    ctr = collections.Counter(n.duration for t in in_song.tracks for n in t.notes)
    return ctr


stats = []

in_song = MidiSimple.Song(sys.argv[1])
in_song.remove_control_notes()

q = in_song.estimate_quantization()
print('Estimated quantization:', q)

stats.append(save_stats(in_song))

in_song.quantize()

stats.append(save_stats(in_song))

in_song.eliminate_polyphony()

#stats.append(save_stats(in_song))

fig = plt.figure()
fig.patch.set_alpha(0.0)
ax = fig.add_subplot(111)
ax.patch.set_alpha(1.0)
ax.grid(True, which='both', axis='both', zorder=0)
ax.tick_params(axis='both', direction = 'in')
ymax = 0
name = ['Before Quantization', 'After Quantization']
colors = ['r', 'b']
for i, s in enumerate(stats):
    x = []
    y = []
    last = 0.
    for xv in range(max(s)):
        x.append(xv - 0.5)
        x.append(xv - 0.5)
        y.append(last)
        y.append(s[xv])
        last = s[xv]
    x.append(xv + 0.5)
    x.append(xv + 0.5)
    y.append(last)
    y.append(0.)
    maxy = max(y)
    if maxy > ymax:
        ymax = maxy
    ax.plot(x, y, color=colors[i], label = name[i], zorder=2-i)

ax.set_xlabel('Duration')
ax.set_xlim(0, 960)
ax.set_ylabel('Notes')
ax.set_ylim(0, ymax * 1.1)
ax.legend()
ax.set_title(sys.argv[1])
plt.show()
