import examplesPath  # noqa
from ctsConstants import project_to_absolute_path, DEFAULT_ARCH, ARCH, CONCERT_A
import ctsSID
import ctsMidi

# Notes:
# gongs: f# +.5-> g +.5-> a# +1.5-> b +.5-> c# +1.0v-> d +1.5-> f +.5-> f#


# Sound comparison:
# https://deepsid.chordian.net/?file=/MUSICIANS/L/Lieblich_Russell/Master_of_the_Lamps_PAL.sid
#
# Dump comparison:
# ./siddump.exe Master_of_the_Lamps_PAL.sid -a6


# subtunes to extract
to_extract = [
    # [10, "getting on carpet", 17],
    # [7, "carpet liftoff", 5],
    # [9, "fell off carpet", 5],
    # [8, "finished level", 8],
    # [11, "game won", 25],
    # [3, "TODO", 72],
    # [0, "level 1", 50],
    # [1, "level 2", 67],
    # [2, "level 3", 49],
    # [4, "level 4", 75],
    # [5, "level 5", 68],
    [6, "level 6", 43],
    # [12, "level 7", 62],
]


def main():
    for entry in to_extract:
        (subtune, desc, seconds) = entry

        sid = ctsSID.SID()
        sid.set_options(
            sid_in_filename=project_to_absolute_path('test/sid/Master_of_the_Lamps_PAL.sid'),
            subtune=subtune,
            old_note_factor=1,
            seconds=seconds
        )

        filename_no_ext = 'test/sid/motl_%s' % desc.replace(" ", "_")

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
    main()
