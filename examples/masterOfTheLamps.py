from chiptunesak.ctsConstants import project_to_absolute_path
from chiptunesak import ctsSID
from chiptunesak import ctsMidi

sid_filename = project_to_absolute_path('tests/sid/Master_of_the_Lamps_PAL.sid')

# TODO:
# The rchirp song goes way too fast when converted to midi, figure out why
#
# Sound comparison:
# https://deepsid.chordian.net/?file=/MUSICIANS/L/Lieblich_Russell/Master_of_the_Lamps_PAL.sid
#
# Dump comparison:
# ./siddump.exe Master_of_the_Lamps_PAL.sid -a6

# 3 genies * 7 pieces * (1 tunnel level + 1 music level) + final tunnel = 43 levels
#     odd numbers are tunnels, even numbers are genies
#     1st genie: level 1-14, 2nd genie: level 15-28, 3rd genie: level 29-42, final tunnel: level 43
# subtunes to extract
to_extract = [  # TODO: these times are incorrect
    # [10, "getting on carpet", 17],
    # [7, "carpet liftoff", 5],
    # [9, "fell off carpet", 5],
    # [8, "finished level", 8],
    # [11, "game won", 25],
    # [0, "tunnel 1", 50],  # level 1, 15, 29
    # [1, "tunnel 2", 67],  # level 3, 17, 31
    # [2, "tunnel 3", 49],  # level 5, 19, 33
    # [3, "tunnel 4", 75],  # level 7, 21, 35
    # [4, "tunnel 5", 68],  # level 9, 23, 37
    # [5, "tunnel 6", 55],   # level 11, 25, 39
    [6, "tunnel 7", 68],  # level 13, 27, 41  # TODO: Primary test file
    # [12, "tunnel 8", 62],  # level 43
]


def find_tunings():
    tunings = []

    for entry in to_extract:
        (subtune, desc, seconds) = entry

        # get a 10 second sample to determine tuning
        sid = ctsSID.SID()
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


def create_output_files():
    for entry in to_extract:
        (subtune, desc, seconds) = entry

        sid = ctsSID.SID()
        sid.set_options(
            sid_in_filename=sid_filename,
            subtune=subtune,
            tuning=439.84,  # above code figured this out
            vibrato_cents_margin=10,  # TODO: Try out
            seconds=seconds,
            gcf_row_reduce=True,
        )

        filename_no_ext = 'tests/sid/motl_%s' % desc.replace(" ", "_")

        # write as CSV file
        print("writing %s.csv" % filename_no_ext)
        sid.to_csv_file(project_to_absolute_path('%s.csv' % filename_no_ext))

        # write as midi file
        print("writing %s.mid" % filename_no_ext)
        rchirp_song = sid.to_rchirp()
        chirp_song = rchirp_song.to_chirp()
        ctsMidi.MIDI().to_file(
            chirp_song, project_to_absolute_path('%s.mid' % filename_no_ext))


if __name__ == "__main__":
    # find_tunings()
    create_output_files()
