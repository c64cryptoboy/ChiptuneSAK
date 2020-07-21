import chiptunesak
from chiptunesak.constants import project_to_absolute_path

sid_filename = project_to_absolute_path('examples/sid/Butcher_Hill.sid')


def create_output_files():
    sid = chiptunesak.SID()
    sid.set_options(
        sid_in_filename=sid_filename,
        subtune=1,
        vibrato_cents_margin=0,
        create_gate_off_notes=True,
        assert_gate_on_new_notes=True,
        seconds=175,
        gcf_row_reduce=False,
    )

    filename_no_ext = 'examples/bh'

    sid_dump = sid.capture()  # noqa: F841

    # print(sid_dump.get_tuning())  # Note: tuning almost exactly CONCERT_A

    print('writing %s.csv' % filename_no_ext)
    sid.to_csv_file(project_to_absolute_path('%s.csv' % filename_no_ext))

    print("writing %s.mid" % filename_no_ext)
    rchirp_song = sid.to_rchirp()

    # cvs output shows that a 4/4 measure is 96 play calls, so 24
    play_calls_per_quarter = 24
    # milliframes_per_quarter will determine the QPM/BPM
    chirp_song = \
        rchirp_song.to_chirp(milliframes_per_quarter=play_calls_per_quarter * 1000)

    chirp_song.set_key_signature('D')
    chirp_song.set_time_signature(4, 4)

    chiptunesak.MIDI().to_file(
        chirp_song, project_to_absolute_path('%s.mid' % filename_no_ext))


if __name__ == "__main__":
    create_output_files()
