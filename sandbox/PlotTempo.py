# visualize note lengths in ticks

import sys
import collections

import matplotlib.pyplot as plt
from chiptunesak import midi


def plot_hist(track):
    ctr = collections.Counter()
    last = 0
    for n in track.notes:
        ctr[n.start_time - last] += 1
        last = n.start_time
    fig = plt.figure()
    fig.patch.set_alpha(0.0)
    ax = fig.add_subplot(111)
    ax.patch.set_alpha(1.0)
    ax.grid(True, which='both', axis='both', zorder=0)
    ax.tick_params(axis='both', direction='in')
    s = ctr
    x = []
    y = []
    last = 0.
    for xv in range(min(s), max(s)):
        x.append(xv - 0.5)
        x.append(xv - 0.5)
        y.append(last)
        y.append(s[xv])
        last = s[xv]
    x.append(xv + 0.5)
    x.append(xv + 0.5)
    y.append(last)
    y.append(0.)
    y = [d + 0.1 for d in y]
    ax.plot(x, y, color='r', label='Track 3')

    ax.set_xlabel('difference (ticks)')
    ax.set_xlim(0, 1000)
    ax.set_ylabel('Number')
    ax.set_yscale('log')
    ax.set_ylim(.1, max(y) * 1.1)
    ax.legend()
    ax.set_title('Statistics')
    plt.show()


song = midi.import_midi_to_chirp(sys.argv[1])

plot_hist(song.tracks[2])
