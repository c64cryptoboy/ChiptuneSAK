************************************
GoatTracker (and GoatTracker Stereo)
************************************

`GoatTracker <https://cadaver.github.io/>`_ is a SID `tracker <https://en.wikipedia.org/wiki/Music_tracker>`_ that runs on modern platforms.  Songs can be developed on Windows, MacOS, or Linux, and then exported for playback on original C64/C128 hardware.  GoatTracker allows fine control of many of the SID chip's capabilities.

GoatTracker in ChiptuneSAK
++++++++++++++++++++++++++

ChiptuneSAK can import and export GoatTracker song files in the .sng format to the various native Chirp representations.  The :ref:`GoatTracker` class is designed to convert between the GoatTracker sng format and the :ref:`RChirp Representation`.

The GoatTracker sng file format does not contain information about the target architecture or whether the song requires multispeed. As a result, to take advantage of either, music should be exported to the sng file, opened in GoatTracker, and any adjustments made there.

**Note:** GoatTracker does not have separate frequency tables for PAL and NTSC, which means that the notes played back in NTSC mode will *not* be tuned to the standard A440 tuning used by ChiptuneSAK. To make the notes play at the desired pitch, the song must be encoded in PAL mode.

GoatTracker comes in two versions: the original, which can play 3 voices with one SID, and a stereo version, which can play 6 voices using 2 SIDs. ChiptuneSAK supports both versions, automatically selecting the version based on the number of voices.


2SID playback in VICE
#####################

GoatTracker can export songs to native C64 programs.  Unlike other trackers (e.g., SID-Wizard), it doesn't have an export option that includes a routine that will drive (meaning, call at regular intervals) the song's playback routine.  So let's create one.

In the :ref:`Chord Splitting` example, we show how to import an MS-DOS game tune into a stereo GoatTracker sng file called LeChuck.sng.  2SID playback assumes that the C64 has two SID chips (easy to configure when using VICE).

Assuming LeChuck.sng was already created, then in stereo GoatTracker:

1. Use F10 to navigate to and load the LeChuck.sng file.

    * If you want, you can play the song using shift F1, and stop the playback using F4

2. To export the song, press F9.  Accept all defaults by pressing ENTER

3. Accept the default $1000 start address and default zeropage settings.

    * Note: The VIC-II chip cannot "see" the 4K of RAM that starts at $1000 or $9000 (the PLA maps the character ROM to those ranges).  So RAM at $1000 is a common default for music routines.

4. Accept the default format "PRG - C64 native format".  This appends a two-byte load address of $1000 to the binary before exporting.

Next, create a .d64 floppy disk image and write the lechuck.prg export to that image.  Best to change the filename to all lower case before adding to the image.  The file should now appear in the image without the ".prg" filename extension, and should be a file of type PRG.

* On windows, we recommend using `DirMaster <https://style64.org/dirmaster>`_ for .d64 management

* If you plan to script some of the steps of creating disk images and placing generated files into them, you can use the python `subprocess module <https://docs.python.org/3/library/subprocess.html>`_ to automate calls to the `c1541(.exe) <https://vice-emu.sourceforge.io/vice_13.html>`_ command line utility.

Copy-and-paste the following BASIC music driver program into a running C64 VICE instance:

.. code-block::

    10 ifi>0then100
    20 print"stereo goatracker player example"
    30 print"gt2stereo.cfg defaults to sid chips at $d400 and $d500"
    40 print"loading lechuck prg $1000 export..."
    50 poke56,16:clr:i=1:load"lechuck",8,1:rem restart basic program
    100 print"playing..."
    110 poke780,0:sys4096:rem select subtune 0
    120 sys4099
    130 fort=1to1:next
    140 i=i+1:ifi<1610then120

1. In VICE, select 'Edit'->'Paste' (Note: The lowercase text will be converted to uppercase when pasting)
2. Hit the RETURN key one more time to make sure line 140 was entered
3. confirm that the paste worked with the LIST command

Note: If you plan to script the creation of these kinds of BASIC programs, you can use the provided gen_prg.py module to created C64-native PRG files.

When tokenized (made C64-native), the BASIC program is 317 bytes long and lives at $0801.  Line 50 of the driver program sets the end of basic to be $1000 (minus one), which stops the BASIC code, and any normal vars, indexed vars, and strings from encroaching into the music routine (which lives at $1000).

In VICE, select 'Settings'->'Settings...', 'Audio Settings'->'SID Settings', and (assuming you didn't change the SID base addresses in gt2stereo.cfg) choose SID #2 address to be $d500.

Finally, in VICE, select 'File'->'Attach disk image' to navigate to the .d64 image file, then click the Open button.

RUN the BASIC program to play the dual-SID tune.  A hard-coded counter (line 140) will stop the BASIC program at the end of the tune.

Compression for GoatTracker
###########################

Currently, the GoatTracker exporter is the only class in ChiptuneSAK that can take advantage of its row-based compression algorithms.

GoatTracker patterns have several important properties that will affect the options used for compression:
*  GoatTracker patterns can be transposed in the orderlist.  Thus, a pattern and a transposed version of the same pattern can both be played from the original pattern.
*  GoatTracker patterns include the instrument number on *every row*. As a result, patterns can generally only be used for one voice.
*  GoatTracker patterns appear to be relatively expensive, which means that short patterns do not create much (if any) compression.  As a result, the minimum pattern length should be set to a higher value.  In the examples, we generally use a minimum pattern length of 16.

See the :ref:`One-Pass Global Class` and the :ref:`One-Pass Left-to-Right Class` documentation for more details.
