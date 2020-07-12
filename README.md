# ChiptuneSAK

[comment]: # (Note: for now, can't link to image unless authenticated to private repo)
![logo](https://github.com/c64cryptoboy/ChiptuneSAK/blob/master/res/logoSmall.png)

ChiptuneSAK (swiss army knife) is a generalized pipeline for processing music and targeting various constrained playback environments.

It imports from many music formats and converts them to a common representation chirp (**CH**iptunesak **I**ntermediate **R**e**P**resentation).  Chirp can be processed and transformed in many ways, and then exported to various playback formats and environments.

## Background

Many one-off music processing tools were created for the Youd/Knapp/Van Haren [ten-Commodore Orchestrion](https://hackaday.com/2019/09/07/how-many-commodores-does-it-take-to-crack-a-nut/), as well as for processing the music format for user-contributed content to Unknown Realm (Note: we have no details on the development status of the game, so please don't ask).  Recently, Youd/Brenner began work on a (not-yet-released) Commodore 64 Ultima-game music demo, requiring similar processing pipelines.

It became apparent that there were low-hanging opportunities to introduce generality into our workflow.  Therefore, these separate efforts have been redirected into this standalone library.  Its workflow is inspired by the LLVM compiler framework, which accepts many programming languages, "raises" them to a common intermediate format that can be manipulated, then "lowers" the code to many target platforms.

## Team

* David Knapp: core developer
* David Youd: core developer
* Ian Lee: python practices consultant

* We are particularly grateful to:
    * Markus Brenner: For providing Apple II Mockingboard Ultima music importing/exporting
    * Hasse Axəlsson-Svala: For offering up much-needed GoatTracker and GoatTracker stereo sample data

## Project Status

The code is currently in a pre-alpha state.  Features are being debated and fundamental data representations are in flux.  Currently working on a variety of concrete importers and exporters from which to generalize the processing pipeline.  Details:

### Music importers

* Standard [MIDI](https://www.midi.org/specifications) file (type 0 or 1):  Contains note on/off events in delta time
* Commodore 64 [SID files](https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt): C64 code that plays music (minus the playloop), wrapped with metadata and well-defined entry points.  ChiptuneSAK supports PSID and some RSID.  Importer is proposed as alternative to the closed-source SID2MIDI.
* [GoatTracker 2](https://sourceforge.net/p/goattracker2/code/HEAD/tree/): A Commodore 64 pattern-based music editor for Windows/linux/MacOS
* [GoatTracker 2 Stereo](https://sourceforge.net/projects/goattracker2/files/GoatTracker%202%20Stereo/) (2SID)

#### Importers: under development

* tbd

#### Importers: proposed

* Subset of [MusicXML](https://www.musicxml.com/for-developers/): A digital sheet music interchange format
* [MOD](http://web.archive.org/web/20120806024858/http://16-bits.org/mod/) (Amiga Module) files
* [NSF](https://wiki.nesdev.com/w/index.php/NSF) (Nintendo Sound Format).  We already have a pure-python 6502 emulator working for the C64 SID importer that can be reused.
* Many opportunities with VGM (Video Game Music)  -- a sample-accurate sound logging format for [many machines](https://vgmrips.net/packs/systems) and many [sound chips](https://vgmrips.net/packs/chips)
* COMPUTE!'s [Sidplayer](https://archive.org/details/Computes_Music_System_for_the_Commodore_128_and_64/mode/2up) [format](https://ist.uwaterloo.ca/~schepers/formats/SIDPLAY.TXT)

### ChIRp processing / transformations

* Quantizing of note onset and duration
* tick scaling, truncation, voice projection and reordering
* Arbitrary metric modulation with support for music with varying meters
* Transpose score
* Separate ("explode") polyphony into separate voices
* Music compression for trackers: compute patterns, including reused based on transposition and differing tempos

#### ChIRp processing: under development

* Additional tracker compression schemes

#### ChIRp processing: proposed

* tbd

### Music exporters

* MIDI
* [LilyPond](http://lilypond.org/doc/v2.19/Documentation/notation.pdf): Sheet music markup language
* [Commodore 128 BASIC](https://www.c64-wiki.com/wiki/BASIC#Overview_of_BASIC_Version_7.0_Commands) music program
* GoatTracker 2 and GoatTracker 2 Stereo (2SID), both automatically compute patterns for smaller files
* ML64: Human-readable music format for [Unknown Realm](https://www.kickstarter.com/projects/stirringdragongames/unknown-realm-an-8bit-rpg-for-pc-and-commodore-64) music contributions from those supporting at the "bard tier"

#### Exporters: Under development

* [SID-Wizard](https://sourceforge.net/p/sid-wizard/code/HEAD/tree/) 1.8 (targeting dual and triple SID, as SID-Wizard only supports midi->single SID)

#### Exporters: Proposed

* Minecraft [Note Blocks](https://minecraft.gamepedia.com/Note_Block)
* [Mario Paint Composer](https://mariopaintcomposer.proboards.com/)
* Markus's yet-unnamed Dr. Cat-derived 3-SID C64 player
* [ABC](http://abcnotation.com/wiki/abc:standard:v2.1) Notation: Human-readable music format.  Used to allow user-submitted music in online games including Starbound, Lord of the Rings Online, and Shroud of the Avatar
* jellybiscuits [Music Box Composer](http://www.jellybiscuits.com/?page_id=951) file format
* A [Rob Hubbard engine](https://www.1xn.org/text/C64/rob_hubbards_music.txt)
* Other tracker file formats, such as RobTracker v1.11 (publicly released Dec 25th. 2019) or JCH's [SID Factory II](http://olivi.chordian.net/category/sid-factory-ii/)

## Recent milestones

* Exported some Monkey Island (MS-DOS 1990) midi capture into 2SID GoatTracker.  Patterns automatically computed to reduce file size.
* Exported some Betrayal at Krondor (MS-DOS, 1993) midi capture to pdf sheet music, goat tracker, and Commodore 128 BASIC program
* SID imported now implemented

## Requirements/Building

* [Python 3.7+](https://www.python.org/downloads/)
    * pip install
        * matplotlib
        * mido
        * more-itertools
        * numpy
        * parameterized
        * sphinx
* [Lilypond](https://lilypond.org/download.html)
* [MidiEditor](https://www.midieditor.org/) - *optional, useful for visualizing what is happening to the midi files*

### Bootstrap: Ubuntu 20.04

```bash
# Install system dependencies
sudo apt install lilypond python3-venv build-essential

# Convenience Make target for setting things up
make venv
source venv/bin/activate

## Or if you prefer setting things up manually, you might do something like:

# Make and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python development dependencies
pip3 install -r requirements.txt

# Install ChiptuneSAK in editable mode
pip3 install --editable .

# Run the unittests to make sure things are working as expected
python3 -m unittest discover -p "*Test.py"
```

### Bootstrap: Windows 10

The following instructions make the following assumptions:

* You installed [Python 3.8 from the Windows Store](https://www.microsoft.com/en-us/p/python-38/9mssztt1n39l)
* You are doing your development in Windows PowerShell

```ps1
# In a PowerShell Admin window:

# Set Powershell Execution Policy to all running local scripts:
Set-ExecutionPolicy RemoteSigned
# Answer "[A] Yes to All" when prommpted
```

```ps1
# Compare your Python version to what was used writing this README
python --version  # Python 3.8.3

# Create a Python virtual environment (EXPLICITLY use `python` instead of `python3`)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install requirements in to virtualenv
pip install -r .\requirements.txt

# Install ChiptuneSAK in editable mode
pip install --editable .

# Run the unittests to make sure things are working as expected
python -m unittest discover -p "*Test.py"
```

## Generating Documentation

from docs folder:

`make html`

## Running Tests

from the root folder, download the test data:

`python3 res/downloadTestResources.py`

from test folder:

`python3 -m unittest discover -p "*Test.py" -v`

or for an individual test:

`python3 -m unittest chirpTest.py`

## Run a simple example

from `examples/` folder:

`python3 lechuck.py`
