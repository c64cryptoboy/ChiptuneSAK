# Export subtunes from Master of the Lamps for processing in Sibelius.
#
# Notes:
# - 3 genies * 7 pieces * (1 tunnel level + 1 music level) + final tunnel = 43 levels
#       odd numbers are tunnels, even numbers are genies
#       1st genie: level 1-14, 2nd genie: level 15-28, 3rd genie: level 29-42,
#       final tunnel: level 43
# - Song duration (in seconds) = ceil(last frame in spreadsheet / 50.124542)
#       ChiptuneSAK trims spreadsheets when song ends, but some subtunes endlessly repeat
# - TODO: I don't see the v2 pitch bends in either this tool or siddump.c.  It's an RSID,
#       so there's a small chance that the code that pitch bends is setup by the init routine?
#       Guess I should look at the interrupt handler to see if it does pitch bend handing
#       outside of play calls.  If so, freq would stay at its set point (since it's the only
#       code getting called), which is what I observe.
# - The starting key signatures (below) don't match the PAL subtunes this parses, instead
#       they should match the NTSC game footage (https://csdb.dk/release/?id=164839) that I
#       captured for the YouTube video that I'm going to match this music up with.
#
# TODOs:
# - output midi is pretty fast when LCD=2, and reasonable when LCD=1.  Need
#   to get a handle on how to set parameters for each subtune so that they
#   comes into Sibelius closer to target.

from chiptunesak.constants import project_to_absolute_path
from chiptunesak.sid import SID
from chiptunesak import midi

sid_filename = project_to_absolute_path('tests/sid/Master_of_the_Lamps_PAL.sid')

# list of subtunes to extract
to_extract = [
    # GCD=2
    # repeats every 1024 frames
    # nice appoggiatura auditory illusion on the step up to the 5th intervals in v2 when
    #     combined with v1
    [10, "getting on carpet", 21, 'Ebm', 2, 4],

    # GCD=2, no key
    # v2 sound effect, v1-v3 end with woosh
    [7, "carpet liftoff", 9, 'C', 2, 4],

    # GCD=2, no key
    # V2 pitch bends
    [9, "fell off carpet", 9, 'C', 4, 4],

    # GCD=2
    [8, "finished level", 12, 'C', 2, 4],

    # GCD=2
    [11, "game won", 23, 'C', 4, 4],

    # level 1, 15, 29
    # GCD=2
    # V2 split between sound effects (down sweeps) or notes (in sections)
    # V3 split between percussions (down sweeps) and notes (in sections)
    [0, "tunnel 1", 77, 'C', 4, 4],

    # level 3, 17, 31
    # GCD=2
    # V3 split between percussions and notes (in sections)
    [1, "tunnel 2", 86, 'C', 4, 4],

    # level 5, 19, 33
    # GCD=1
    # V2 some detuning and upward pitch bends
    # V3 split between percussions and notes (in sections)
    [2, "tunnel 3", 62, 'Gm', 4, 4],

    # level 7, 21, 35
    # GCD=2
    # V2 some detuning and pitch bends (both up and down)
    # V3 split between percussions and notes (in sections)
    [3, "tunnel 4", 103, 'Cm', 4, 4],

    # level 9, 23, 37
    # GCD=2
    # V2 some sound effects, detuning and pitch bends (both up and down)
    # V3 split between percussions and notes (in sections)
    [4, "tunnel 5", 94, 'Cm', 4, 4],

    # level 11, 25, 39
    # GCD=2
    # V2 pitch bends
    # V3 percussion (except for last note)
    [5, "tunnel 6", 84, 'Em', 4, 4],

    # level 13, 27, 41
    # GCD=2
    [6, "tunnel 7", 62, 'Dm', 4, 4],

    # level 43
    # GCD=2
    # V3 splits between percussion and notes (in sections)
    [12, "tunnel 8", 86, 'Cm', 4, 4],
]
to_extract = [to_extract[8]]  # Debugging


def find_tunings():
    tunings = []

    for entry in to_extract:
        (subtune, desc, _, _, _, _) = entry

        # get a 10 second sample to determine tuning
        sid = SID()
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

        sid = SID()
        sid.set_options(
            sid_in_filename=sid_filename,
            subtune=subtune,
            # Not sure if the PAL version of the game (from which this SID is ripped)
            # still uses the original NTSC frequency tables or not, but since the SID
            # headers indicate PAL, the tuning should change to ~448.93 to minimize
            # cents
            tuning=448.93,  # above code figured this out
            vibrato_cents_margin=10,
            seconds=seconds,
            gcf_row_reduce=True,
        )

        filename_no_ext = 'tests/sid/motl_%s' % desc.replace(" ", "_")

        if write_csv:
            print("writing %s.csv" % filename_no_ext)
            sid.to_csv_file(project_to_absolute_path('%s.csv' % filename_no_ext))

        if write_midi:
            print("writing %s.mid" % filename_no_ext)
            rchirp_song = sid.to_rchirp()

            chirp_song = rchirp_song.to_chirp(jiffies_per_quarter=32)

            chirp_song.set_key_signature(starting_key)
            chirp_song.set_time_signature(time_sig_top, time_sig_bottom)

            midi.MIDI().to_file(
                chirp_song, project_to_absolute_path('%s.mid' % filename_no_ext))


if __name__ == "__main__":
    # find_tunings()
    create_output_files(False, True)
