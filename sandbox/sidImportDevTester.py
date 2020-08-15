# Place where I'm testing various SID importing
# TODO: Need to write a script to test against all HVSC, that'll find a lot of gotchas

import chiptunesak
from chiptunesak.constants import project_to_absolute_path

dest = 'examples/temp/'


def create_output_files():
    params = [
        # has the notes that sid2midi misses
        (project_to_absolute_path('examples/sid/Pool_of_Radiance.sid'), 0, dest + 'por', 12, 120),

        (project_to_absolute_path('examples/sid/Skyfox.sid'), 0, dest + 'skyfox', 24, 100),

        # contains digi, which is ignored
        (project_to_absolute_path('examples/sid/Great_Giana_Sisters.sid'), 0, dest + 'ggs', 24, 30),

        # assert_gate_on_new_note: True includes arpeggios, and False includes just the chord root
        (project_to_absolute_path('examples/sid/Butcher_Hill.sid'), 1, dest + 'bh', 12, 175),

        (project_to_absolute_path('examples/sid/Nitro.sid'), 1, dest + 'nitro', 12, 15),

        (project_to_absolute_path('examples/sid/HelloWorld.sid'), 1, dest + 'hw', 12, 15),

    ]
    params = params[5]  # select one

    sid_filename = params[0]
    filename_no_ext = params[2]

    sid = chiptunesak.SID()
    sid.set_options(
        sid_in_filename=sid_filename,
        subtune=params[1],
        vibrato_cents_margin=0,
        seconds=params[4],
        # create_gate_off_notes=False,
        # assert_gate_on_new_note=False,
        gcf_row_reduce=True,
    )

    sid_dump = sid.capture()  # noqa: F841

    print('writing %s.csv' % filename_no_ext)
    sid.to_csv_file(project_to_absolute_path('%s.csv' % filename_no_ext))

    print("writing %s.mid" % filename_no_ext)
    rchirp_song = sid.to_rchirp(sid_filename)

    play_calls_per_quarter = params[3]
    chirp_song = \
        rchirp_song.to_chirp(milliframes_per_quarter=play_calls_per_quarter * 1000)

    chirp_song.set_time_signature(4, 4)

    chiptunesak.MIDI().to_file(
        chirp_song, project_to_absolute_path('%s.mid' % filename_no_ext))


if __name__ == "__main__":
    create_output_files()
