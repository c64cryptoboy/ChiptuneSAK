# chiptune-sak
chiptune-sak (swiss army knife) is a pipeline for processing music and creating output for various constrained playback environments.  It imports many music formats, supports various music processing, and exports to many playback formats and environments.  

## Background:
Many one-off music processing tools were created for the Youd/Knapp/Van Haren [ten-Commodore Orchestrion](https://hackaday.com/2019/09/07/how-many-commodores-does-it-take-to-crack-a-nut/).  Shortly thereafter, Youd/Knapp/Brenner began work on a (not-yet-released) Commodore 64 Ultima-game music demo.  It became apparent that there was low-hanging opportunities to introduce generality into the music processing pipeline code.  That effort has been redirected into this standalone tool / library.  Its workflow is inspired by the LLVM compiler framework, which accepts many programming languages, "raises" them to a common intermediate format that can be manipulated, then "lowers" the code to many target platforms.

## Team
* David Knapp
* David Youd
* Markus Brenner: Ultima music importing/exporting
* Hasse Axəlsson-Svala: GoatTracker consultant

## Project Status
The code is currently in a pre-alpha state.  Features are being debated and fundamental data representations are in flux.  Currently working on a variety of concrete importers and exporters from which to generalize the processing pipeline.  Details:

### Music imports

#### Under development
* MIDI (type 0 or 1)
* GoatTracker 2
  
#### Proposed
* MusicXML (a subset)
* Jellyfish Music Box Composer format
  
### Music processing / transformations

#### Currently under development
* Quantizing of note onset and duration (for "continuous" inputs such as midi)
* Making the intermediate representation measure aware
* Separate polyphony
* Arbitrary metric modulation with support for music with varying meters
* Music compression (compute patterns for trackers, including opportunities based on transposition)
 
#### Proposed
* measure-aware music compression
  
### Music exports

#### Currently under development
* MIDI
* ML64
* C128 BASIC

#### Proposed
* Markus's yet-unnamed Dr. Cat-derived 3-SID C64 player
* GoatTracker 2
* ABC Notation
* LilyPond
* Jellyfish Music Box Composer format
* SID-Wizard 1.8 (dual / triple SID)
* RobTracker v1.11 (publicly released Dec 25th. 2019)


