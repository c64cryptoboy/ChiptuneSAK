# Export subtunes from Master of the Lamps for processing in Sibelius.
# Used to create this: https://www.youtube.com/watch?v=HH9sVayG0oQ
#
# Notes:
# - 3 genies * 7 pieces * (1 tunnel level + 1 music level) + final tunnel = 43 levels
#       odd numbers are tunnels, even numbers are genies
#       1st genie: level 1-14, 2nd genie: level 15-28, 3rd genie: level 29-42,
#       final tunnel: level 43
# - The starting key signatures (below) don't match the PAL subtunes this parses, instead
#       they should match the NTSC game footage (https://csdb.dk/release/?id=164839) that I
#       captured for the YouTube video that I'm going to match this music up with.

import chiptunesak
from chiptunesak.constants import project_to_absolute_path

sid_filename = project_to_absolute_path('examples/data/sid/Master_of_the_Lamps_PAL.sid')

# list of subtunes to extract
to_extract = [
    # repeats every 1024 frames
    [10, "getting on carpet", 21, 'Ebm', 2, 4],

    [7, "carpet liftoff", 9, 'Em', 2, 4],

    [9, "fell off carpet", 9, 'Am', 4, 4],

    [8, "finished level", 12, 'C', 2, 4],

    [11, "game won", 23, 'C', 4, 4],

    # level 1, 15, 29
    [0, "tunnel 1", 77, 'C', 4, 4],

    # level 3, 17, 31
    [1, "tunnel 2", 86, 'Cm', 4, 4],

    # level 5, 19, 33
    [2, "tunnel 3", 62, 'Gm', 4, 4],

    # level 7, 21, 35
    [3, "tunnel 4", 103, 'C', 4, 4],

    # level 9, 23, 37
    [4, "tunnel 5", 94, 'Cm', 4, 4],

    # level 11, 25, 39
    [5, "tunnel 6", 84, 'Em', 4, 4],

    # level 13, 27, 41
    [6, "tunnel 7", 62, 'Dm', 4, 4],

    # level 43
    [12, "tunnel 8", 86, 'Cm', 4, 4],
]
# to_extract = [to_extract[8]]  # Debugging


def find_tunings():
    tunings = []

    for entry in to_extract:
        (subtune, desc, _, _, _, _) = entry

        # get a 10 second sample to determine tuning
        sid = chiptunesak.SID()
        sid.set_options(
            sid_in_filename=sid_filename,
            subtune=subtune,
            vibrato_cents_margin=0,
            seconds=10,
            gcf_row_reduce=False,
        )
        sid_dump = sid.capture()
        (tuning, min_cents, max_cents) = sid_dump.get_tuning()
        tunings.append(tuning)
        print('subtune {:d}, desc {}, tuning {:6.3f}, min cents {:d}, max cents {:d}'.format(
            subtune, desc, tuning, min_cents, max_cents))

    tunings.sort()
    median = tunings[len(tunings) // 2]
    print('\nmedian {:6.3f}'.format(median))


def create_output_files(write_csv=True, write_midi=True):
    for entry in to_extract:
        (subtune, desc, seconds, starting_key, time_sig_top, time_sig_bottom) = entry

        sid = chiptunesak.SID()
        sid.set_options(
            sid_in_filename=sid_filename,
            subtune=subtune,
            tuning=448.93,  # above code figured this out
            vibrato_cents_margin=10,
            seconds=seconds,
            gcf_row_reduce=True,
        )

        filename_no_ext = 'examples/data/motl/motl_%s' % desc.replace(" ", "_")

        sid_dump = sid.capture()  # noqa: F841

        if write_csv:
            print("writing %s.csv" % filename_no_ext)
            sid.to_csv_file(project_to_absolute_path('%s.csv' % filename_no_ext))

        if write_midi:
            print("writing %s.mid" % filename_no_ext)
            rchirp_song = sid.to_rchirp(sid_filename)

            play_calls_per_quarter = 32  # can see this in the csv output
            # milliframes_per_quarter will determine the QPM/BPM
            chirp_song = \
                rchirp_song.to_chirp(milliframes_per_quarter=play_calls_per_quarter * 1000)

            chirp_song.set_key_signature(starting_key)
            chirp_song.set_time_signature(time_sig_top, time_sig_bottom)

            chiptunesak.MIDI().to_file(
                chirp_song, project_to_absolute_path('%s.mid' % filename_no_ext))


if __name__ == "__main__":
    # find_tunings()
    create_output_files(True, True)
