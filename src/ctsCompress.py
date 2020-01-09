import sys
import fractions
from dataclasses import dataclass
import collections
import ctsSong

Transform = collections.namedtuple('Transform', ['transpose', 'stretch'])


@dataclass(init=True, repr=True, eq=True, order=True)
class Repeat:
    track: int
    start: int
    repeat_start: int
    length: int
    xform: Transform


def find_xform(note1, note2):
    transpose = note2.note_num - note1.note_num
    stretch = fractions.Fraction(note2.duration / note1.duration).limit_denominator(64)
    return Transform(transpose, stretch)


def apply_xform(note, xform):
    return ctsSong.Note(note.note_num + xform.transpose, 0, int(note.duration * xform.stretch))


def find_all_repeats(song, min_repeat_length):
    results = []
    for it, t in enumerate(song.tracks):
        notes = t.notes
        n_notes = len(notes)

        for first_position in range(0, n_notes - min_repeat_length):
            for start_position in range(first_position + min_repeat_length, n_notes - min_repeat_length):
                xform = find_xform(notes[first_position], notes[start_position])
                for i in range(1, n_notes - start_position):
                    start_diff = (notes[start_position + i].start_time - notes[start_position + i - 1].start_time)
                    first_diff = int((notes[first_position + i].start_time -
                                      notes[first_position + i - 1].start_time) * xform.stretch + 0.1)
                    first_note = notes[first_position + i]
                    tmpxf = apply_xform(first_note, xform)
                    start_note = notes[start_position + i]
                    if (first_diff != start_diff) or (tmpxf != start_note):
                        if i > start_position - first_position:
                            i = start_position - first_position
                        if i >= min_repeat_length:
                            results.append(Repeat(it, first_position, start_position, i, xform))
                            i = 0
                        break
                i += 1
            if i >= min_repeat_length:
                results.append(Repeat(it, first_position, start_position, i, xform))
    return results

def find_best_compression(repeats, pattern_definition_overhead, pattern_definition_cost_note, pattern_play_cost):
    tmp = []
    pattern_starts = []
    current_track, current_start = 0, 0
    for r in sorted(repeats):

        if r.track != current_track or r.start != current_start:
            pattern_starts.append(tmp)
            tmp = []
            current_track, current_start = r.track, r.start

        tmp.append(r)
    pattern_starts.append(tmp)
    for p in pattern_starts:
        print("start = %d:" % p[0].start)
        lengths = sorted(set(r.length for r in p))
        n = 0
        last_loop = 0
        for pattern_length in lengths:
            tmp_loops = [r for r in p if r.length >= pattern_length]
            poss = []
            nloops = 1
            loop_end = tmp_loops[0].start + tmp_loops[0].length
            for r in tmp_loops:
                if r.repeat_start >= loop_end:
                    nloops += 1
                    poss.append(r)
                tmp = r.start + r.length
                if tmp > loop_end:
                    loop_end = tmp
            cost = pattern_definition_overhead + pattern_definition_cost_note * pattern_length + nloops * pattern_play_cost
            total = pattern_definition_overhead + pattern_definition_cost_note * (pattern_length * nloops)
            net = total - cost
            if net > 0:
                print("%d loops of %d cost = %d for %d base (net %d)" % (nloops, pattern_length, cost, total, net))
                print('   ' + '\n   '.join(str(rp) for rp in poss))





if __name__ == '__main__':
    in_song = ctsSong.Song(sys.argv[1])

    in_song.remove_control_notes()
    q = in_song.estimate_quantization()
    print(q)
    in_song.quantize()  # Automatically quantize
    print("Overall quantization = ", (in_song.qticks_notes, in_song.qticks_durations), "ticks")
    # Note:  for ML64 ALWAYS remove_polyphony after quantization.
    in_song.eliminate_polyphony()

    repeats = find_all_repeats(in_song, 2)

    find_best_compression(repeats, 1, 4, 1)

    # print('\n'.join(str(r) for r in repeats if r.xform.stretch == 1))

    # print("Track Start   smb    Repeat   rmb    Length  XForm")
    # print('----- ----- -------- ------ -------- ------  -----')
    # for r in results:
    #     print("%4d %5d %8s %6d %8s %6d  %s" % (r))
    #
    # quit()

    # for it, t in enumerate(in_song.tracks):
    #     last = []
    #     notes = t.notes
    #     n_notes = len(notes)
    #     for i in range(0, n_notes + 1):
    #         poss = []
    #         success = False
    #         tmp = [r for r in results if r.Track == it and r.Start == i]
    #         for p in tmp:
    #             for l in last:
    #                 if l.Track == p.Track and l.Start == p.Start - 1 \
    #                         and l.Repeat == p.Repeat - 1 and l.Length == p.Length + 1:
    #                     # print(l, p)
    #                     success = True
    #                     break
    #             if success:
    #                 break
    #             poss.append(p)
    #         last = tmp
    #         if len(poss) > 0:
    #             print("Track Start   smb    Repeat   rmb    Length  XForm")
    #             print('----- ----- -------- ------ -------- ------  -----')
    #             for r in poss:
    #                 print("%4d %5d %8s %6d %8s %6d  %s" % (r))
    #             Lengths = sorted(set(p.Length for p in poss))
    #             n = 0
    #             last_loop = 0
    #             for j in Lengths:
    #                 tmp_loops = [r for r in poss if r.Length >= j]
    #                 n = 1
    #                 loop_end = tmp_loops[0].Start + tmp_loops[0].Length
    #                 for r in tmp_loops[1:]:
    #                     if r.Repeat >= loop_end:
    #                         n += 1
    #                     tmp = r.Start + r.Length
    #                     if tmp > loop_end:
    #                         loop_end = tmp
    #                 print("%d loops of %d or more (%d notes saved)" % (n + 1, j, j * n))
