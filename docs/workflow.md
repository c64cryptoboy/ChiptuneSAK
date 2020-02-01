# Flow types:
## Chirp
TODO Desc

## MChirp
TODO Desc

Quantized, and has no single-channel polyphony

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
   * MusicXML .xml file
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
