import sys
import numpy as np
import matplotlib.pyplot as plt
import collections
import ctsSong

def plot_quantization(stats, elements):
    fig = plt.figure()
    fig.patch.set_alpha(0.0)
    ax = fig.add_subplot(111)
    ax.patch.set_alpha(1.0)
    ax.grid(True, which='both', axis='both', zorder=0)
    ax.tick_params(axis='both', direction = 'in')
    ymax = 0
    colors = ['r', 'b', 'g', 'p']
    for i, e in enumerate(elements):
        s = stats[e]
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
        ax.plot(x, y, color=colors[i], label = e, zorder=2-i)

        ax.set_xlabel(e + ' (ticks)')
        ax.set_xlim(0, max(x))
        ax.set_ylabel('Number')
        ax.set_ylim(0, max(y) * 1.1)
        ax.legend()
        ax.set_title('Statistics')
        plt.show()



in_song = ctsSong.Song(sys.argv[1])
in_song.remove_control_notes()

q = in_song.estimate_quantization()
print('Estimated quantization:', q)

in_song.quantize()

in_song.eliminate_polyphony()

print('\n'.join("%s: %s" % (s, in_song.stats[s]) for s in in_song.stats))

plot_quantization(in_song.stats, ['Duration Deltas'])


