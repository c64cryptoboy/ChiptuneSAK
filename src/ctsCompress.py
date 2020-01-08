import sys
import collections
import ctsSong


def find_xform(note1, note2):
    transpose = note2.note_num - note1.note_num
    stretch = note2.duration / note1.duration
    return (transpose, stretch)


def xform(note, xform_params):
    transpose, stretch = xform_params
    return ctsSong.Note(note.note_num + transpose, 0, int(note.duration * stretch))


repeat = collections.namedtuple('repeat', ['Track', 'Start', 'smb', 'Repeat', 'rmb', 'Length', 'XForm'])

if __name__ == '__main__':
    in_song = ctsSong.Song(sys.argv[1])

    in_song.remove_control_notes()
    q = in_song.estimate_quantization()
    print(q)
    in_song.quantize()  # Automatically quantize
    print("Overall quantization = ", (in_song.qticks_notes, in_song.qticks_durations), "ticks")
    # Note:  for ML64 ALWAYS remove_polyphony after quantization.
    in_song.eliminate_polyphony()

    results = []
    for it, t in enumerate(in_song.tracks):
        notes = t.notes
        min_length = 3
        n_notes = len(notes)
        print(t.name, n_notes)

        for first_position in range(0, n_notes - min_length):
            for start_position in range(first_position + min_length, n_notes - min_length):
                params = find_xform(notes[first_position], notes[start_position])
                for i in range(1, n_notes - start_position):
                    start_diff = (notes[start_position + i].start_time - notes[start_position + i - 1].start_time)
                    first_diff = int(
                        (notes[first_position + i].start_time - notes[first_position + i - 1].start_time) * params[
                            1] + 0.1)
                    first_note = notes[first_position + i]
                    tmpxf = xform(first_note, params)
                    start_note = notes[start_position + i]
                    if (start_diff != first_diff) or (tmpxf != start_note):
                        if i > start_position - first_position:
                            i = start_position - first_position
                        if i >= min_length:
                            smb = in_song.get_measure_beat(notes[first_position].start_time)
                            rmb = in_song.get_measure_beat(notes[start_position].start_time)
                            results.append(repeat(it, first_position, smb, start_position, rmb, i, params))
                            i = 0
                        break
                i += 1
                if i >= min_length:
                    smb = in_song.get_measure_beat(notes[first_position].start_time)
                    rmb = in_song.get_measure_beat(notes[start_position].start_time)
                    results.append(repeat(it, first_position, smb, start_position, rmb, i, params))

    # print("Track Start   smb    Repeat   rmb    Length  XForm")
    # print('----- ----- -------- ------ -------- ------  -----')
    # for r in results:
    #     print("%4d %5d %8s %6d %8s %6d  %s" % (r))
    #
    # quit()

    for it, t in enumerate(in_song.tracks):
        last = []
        notes = t.notes
        n_notes = len(notes)
        for i in range(0, n_notes + 1):
            poss = []
            success = False
            tmp = [r for r in results if r.Track == it and r.Start == i]
            for p in tmp:
                for l in last:
                    if l.Track == p.Track and l.Start == p.Start - 1 \
                            and l.Repeat == p.Repeat - 1 and l.Length == p.Length + 1:
                        # print(l, p)
                        success = True
                        break
                if success:
                    break
                poss.append(p)
            last = tmp
            if len(poss) > 0:
                print("Track Start   smb    Repeat   rmb    Length  XForm")
                print('----- ----- -------- ------ -------- ------  -----')
                for r in poss:
                    print("%4d %5d %8s %6d %8s %6d  %s" % (r))
                Lengths = sorted(set(p.Length for p in poss))
                n = 0
                last_loop = 0
                for j in Lengths:
                    tmp_loops = [r for r in poss if r.Length >= j]
                    n = 1
                    loop_end = tmp_loops[0].Start + tmp_loops[0].Length
                    for r in tmp_loops[1:]:
                        if r.Repeat >= loop_end:
                            n += 1
                        tmp = r.Start + r.Length
                        if tmp > loop_end:
                            loop_end = tmp
                    print("%d loops of %d or more (%d notes saved)" % (n + 1, j, j * n))
