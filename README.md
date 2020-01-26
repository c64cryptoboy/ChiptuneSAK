# chiptune-sak
chiptune-sak (swiss army knife) is a pipeline for processing music and creating output for various constrained playback environments.  It imports many music formats, supports various music processing, and exports to many playback formats and environments.  

## Background:
Many one-off music processing tools were created for the Youd/Knapp/Van Haren [ten-Commodore Orchestrion](https://hackaday.com/2019/09/07/how-many-commodores-does-it-take-to-crack-a-nut/).  Shortly thereafter, Youd/Knapp/Brenner began work on a (not-yet-released) Commodore 64 Ultima-game music demo.  It became apparent that there was low-hanging opportunities to introduce generality into the music processing pipeline code.

That effort has been redirected into this standalone tool / library.  Its workflow is inspired by the LLVM compiler framework, which accepts many programming languages, "raises" them to a common intermediate format that can be manipulated, then "lowers" the code to many target platforms.

## Project Status
The code is currently in a pre-alpha state.  Features are being debated and fundamental data representations are in flux.
Details:

### Music importers
* Standard [MIDI](https://www.midi.org/specifications) file (type 0 or 1):  Contains note on/off events in delta time
* [GoatTracker 2](https://sourceforge.net/p/goattracker2/code/HEAD/tree/): A Commodore 64 pattern-based music editor for Windows/linux/MacOS

#### Importers: under development
* ML64: Human-readable music format for Unknown Realm music contributions from those supporting at the "bard tier"

#### Importers: proposed
* Subset of [MusicXML](https://www.musicxml.com/for-developers/) (a digital sheet music interchange format)
* jellybiscuits [Music Box Composer](http://www.jellybiscuits.com/?page_id=951) file format
* Commodore 64 [SID files](https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt): Arbitrary C64 code that plays music (minus the playloop), wrapped with metadata and well-defined entry points.  Alternative to the closed-source SID2MIDI.
  
### Music intermediate representation (MIR): processing / transformations
* Quantizing of note onset and duration (for "continuous" inputs such as midi)
* Arbitrary metric modulation with support for music with varying meters
* Music compression (compute patterns for trackers, including opportunities based on transposition)
 
#### MIR processing: under development
* Transpose score
* Separate polyphony (currently separates different channels in same track, needs to be generalized)
 
#### MIR processing: proposed
* Measure-aware music compression
  
### Music exporters
* MIDI
* [LilyPond](http://lilypond.org/doc/v2.19/Documentation/notation.pdf): Sheet music markup language
* ML64
 
#### Exporters: Under development
* [Commodore 128 BASIC](https://www.c64-wiki.com/wiki/BASIC#Overview_of_BASIC_Version_7.0_Commands) music program
* GoatTracker 2
  
#### Exporters: Proposed
* Markus's yet-unnamed Dr. Cat-derrived 3-SID C64 player
* [ABC](http://abcnotation.com/wiki/abc:standard:v2.1) Notation: Human-readable music format.  Used to allow user-submitted music in online games including Starbound, Lord of the Rings Online, and Shroud of the Avatar
* Jellyfish Music Box Composer format
* [SID-Wizard](https://sourceforge.net/p/sid-wizard/code/HEAD/tree/) 1.8 (dual / triple SID)
* RobTracker v1.11 (publicly released Dec 25th. 2019)