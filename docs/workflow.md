# Flow types:
## Chirp
Chirp (**CH**iptune-sak **I**ntermediate **R**e**P**resentation) is chiptune-sak's framework-independent music representation.  Different music formats can be converted to and from chirp.

Chirp maps note events to a tick timeline.  This is different than midi, which records the ticks between events.  Ticks are temporally unitless, and can be mapped to time by applying a BPM.  This has parallels to other music formats such as GoatTracker sng files, in which rows show order and proportion, but are not tied to time until a tempo is applied (number of jiffies per row).

Chirp frequency reasoning will default to a twelve-tone equal temperament system.
Middle C is 261.63Hz, and following Scientific Pitch Notation (SPN), Chirp assigns middle C to be C4 with midi note number 60.  The relationship between the chirp note number and its frequency is 440*2^((m-69)*12), where 69 is the midi number for A4, which is defined as exactly 440Hz.

Some midi conventions differ, e.g., assigning middle C (261.63Hz) to C3 with midi note number 60.  However, since midi really does not have a note-octave representation, this difference is only one of convention.    
With respect to chirp, such a system has an octave offset of -1.  Non-zero octave offsets are common when comparing note-octave notation systems.


## MChirp
MChirp is closely related to chirp, but is measure aware, and is used when reasoning about sheet music measures/bars.  MChirp is quantized, and has no single-channel polyphony (polyphony across channels is expected).

Chirp can be converted to MChirp and vise versa.  Because each format retains different details, the conversion is necessarily lossy.


# Workflow Components

## FileToChirp
* Input:
   * GoatTracker 2 .sng file
   * Midi .mid file
   * ML64 .ml64 file
   * Music Box Composer .mbc file
   * Commmodore 64 SID .sid file
* Output:
   * Chirp
* Notes:
   * Functionality may live with respective importers

## FileToMChirp
* Input:
   * MusicXML .mxl file
* Output:
   * MChirp
* Notes:
   * Functionality may live with respective importers

## Quantizer
* Input:
   * Chirp
* Output:
   * Chirp

## Remove Polyphony
* Input:
   * Chirp
* Output:
   * Chirp

## Measurize
* Input:
   * Chirp
* Output:
   * MChirp
* Notes:
   * input Chirp will be checked to make sure it is quantized and non-polyphonic

## DeMeasurize
* Input: 
   * MChirp
* Output:
   * Chirp

## ChirpTrans
* Input:
   * Chirp
* Output:
   * Chirp
   * text statistics

## MChirpTrans
* Input:
   * MChirp
* Output:
   * MChirp
   * text statistics

## Example workflows:
* GoatTracker2 to Lilypond sheetmusic
   * TODO: 
