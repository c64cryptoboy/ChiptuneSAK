# Flow types:
## Chirp
Chirp (**CH**iptune-sak **I**ntermediate **R**e**P**resentation) is chiptune-sak's framework-independent music representation.  Different music formats can be converted to and from chirp.

Chirp maps note events to a tick timeline.  This is different than midi, which records the ticks between events.  Ticks are temporally unitless, and can be mapped to time by applying a BPM.  This has parallels to other music formats such as GoatTracker sng files, in which rows show order and proportion, but are not tied to time until a tempo is applied (number of jiffies per row).

Chirp frequency reasoning will default to a twelve-tone equal temperament system.
Middle C is 261.63Hz, and following Scientific Pitch Notation (SPN), Chirp assigns middle C to be C4 with midi note number 60.  The relationship between the chirp note number and its frequency is 440*2^((m-69)*12), where 69 is the midi number for A4, which is defined as exactly 440Hz.

Some midi conventions differ, e.g., assigning middle C (261.63Hz) to C3 with midi note number 60.  However, since midi really does not have a note-octave representation, this difference is only one of convention. With respect to chirp, such a system has an octave offset of -1.  Non-zero octave offsets are common when comparing note-octave notation systems.


## MChirp
MChirp is Measure-Based Chirp.  It is closely related to chirp, but is measure aware, and is designed to aid reasoning about measures and bars, as is often the case when dealing with sheet music.  MChirp is quantized, and has no single-channel polyphony (polyphony across channels is expected).

Chirp can be converted to MChirp and vise versa.  Because each format retains different details, the conversion is necessarily lossy.

## RChirp
RChirp is Row-Based Chirp.  It is meant to represent row-based sequences, as would be created by a tracker. RChirp is designed to enable operations that are naturally tied to row-based music players, including pattern matching and compression, creation of effects, and conversion between PAL and NTSC.

RChirp is quantized, and has no single-channel polyphony.

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
   
## FileToRChirp
* Input:
   * GoatTracker 2 .sng file
   * Commodore 64 SID .sid file
* Output:
   * RChirp
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

### Midi to Lilypond Sheet Music clip

You'll need to write your own script to perform this workflow.  In your code, read in the midi file, convert it to measures, and then select the measures you want to turn into a clip. Then call `ctsLilypond.clip_to_lilypond()` to create the Lilypond source for the clip.

#### Example:
          
      song = ctsMidi.midi_to_chirp('bach_invention_4.mid')
      song.quantize_from_note_name('16')  # Quantize to sixteenth notes
      song.remove_polyphony()
      m_song = ctsMChirp.MChirpSong(song)
      ly = ctsLilypond.clip_to_lilypond(m_song, m_song.tracks[0].measures[3:8])
      with open('bach.ly', 'w') as f:
          f.write(ly)
          
          
Then execute the Lilypond command:
     
     lilypond -ddelete-intermediate-files -dbackend=eps -dresolution=600 --png bach.ly
     
The result will be `bach.png` that looks like this:

![bach image](bach.png)      

 ### Recorded midi from game to sheet music
 
 Often, the music recorded from a game has no concept of the note lengths for the music; it is recorded in arbitrary ticks with an arbitrary offset.  This example workflow shows how to turn such music into Lilypond-generated sheet music.
 
 First, we use the FitPPQ.py script to estimate the actual note lengths and adjust them to have a ppq of 960.  From the tools directory, run:
 
   `FitPPQ.py ..\test\Betrayal_orig.mid ..\test\betrayal_q.mid`
 
 This should generate the following output:
 ```
Reading file ..\test\betrayal_q.mid
Finding initial parameters...
Refining...
scale_factor = 5.89000, offset = 2398, total error = 2386.2 ticks (22.03 ticks/note for ppq = 960)
Writing file ..\test\betrayal_q.mid
```

It is a good idea to do a sanity check on the output file, as the algorithm in FitPPQ occasionally fails.  Wwe are working on this issue but it's not guaranteed to work for every file.

Now quantize the output midi file to 16th notes.  This writes over the existing midi file with a quantized version:

 `TransformMidi.py -q 16 -r ..\test\betrayal_q.mid ..\test\betrayal_q.mid`
 
Then output will look something like this:

```
638 notes
PPQ = 960
Input midi is not quantized and  polyphonic
Quantizing...
to note value 16
Eliminating polyphony...
Output ChirpSong is  quantized and not polyphonic
  Time Signature Changes 1
   Key Signature Changes 1
           Tempo Changes 1
              MIDI notes 638
                   Notes 638
             Track names ['Copyright (c)1992', 'Dynamix, Inc.', '====================']
       Note Start Deltas Counter({-9: 26, -4: 23, 1: 23, 28: 21, -25: 20, 17: 20, 7: 18, 12: 18, -20: 17, -14: 17, -10: 15, 6: 15, 2: 13, 22: 13, -36: 11, 23: 11, 14: 11, 34: 10, -15: 9, -19: 9, -30: 8, 33: 8, 18: 8, 29: 8, -5: 8, -32: 8, -21: 8, 0: 8, -55: 8, 11: 7, 24: 7, 35: 7, 25: 7, -16: 7, -66: 7, -34: 7, 44: 6, 3: 6, 30: 6, -26: 6, -50: 6, 38: 5, 49: 5, 54: 5, 8: 5, 41: 5, -31: 5, -11: 5, -6: 5, -60: 5, -3: 4, -2: 4, 19: 4, 9: 4, 51: 4, 56: 4, -45: 4, -40: 4, -44: 4, -39: 4, -28: 4, -35: 3, 55: 3, 40: 3, 45: 3, 36: 3, 62: 3, 61: 3, 10: 3, -37: 3, -27: 3, 5: 3, -71: 3, -33: 3, -18: 2, 37: 2, 27: 2, 13: 2, 60: 2, 39: 2, 20: 2, 46: 2, -8: 2, 31: 2, 15: 2, -1: 2, 26: 2, -49: 2, 43: 1, 57: 1, -17: 1, -38: 1, -12: 1, -7: 1, 21: 1, -51: 1, -29: 1, -24: 1, -13: 1})
         Duration Deltas Counter({0: 53, 21: 51, -21: 51, 6: 46, 26: 28, -15: 26, -66: 25, 97: 21, 107: 20, 56: 20, 10: 17, 62: 17, -25: 17, -102: 15, 41: 14, -77: 12, -91: 12, -46: 12, 113: 12, -30: 11, -108: 11, 103: 10, -31: 9, 118: 8, -56: 7, -6: 7, -35: 6, 15: 6, -60: 5, 82: 5, 4: 4, 16: 4, -9: 4, -52: 4, 47: 4, -96: 4, 76: 4, 112: 3, -116: 3, 11: 3, 52: 3, 109: 3, 91: 3, 29: 3, 50: 3, -18: 2, -62: 2, 35: 2, 5: 2, -44: 2, 25: 2, -72: 2, -19: 2, 68: 2, 88: 2, 31: 2, 9: 1, -27: 1, -50: 1, -36: 1, -24: 1, 7: 1, -54: 1, 53: 1, 23: 1, 46: 1})
               Truncated 88
                 Deleted 0
Exporting to MIDI...
```

Now that the file is quantized, it can be made into a pdf:

  `midiToLilypond.py -a ..\test\betrayal_q.mid ..\test`
  
Note that you **must** have lilypond in your path for that script to work.    
 
The output should look something like this:
```    
Reading ..\test\betrayal_q.mid
Removing control notes...
Quantizing...
480 240
Removing polyphony...
Converting to measures...
Generating lilypond...
Writing lilypond to ..\test\betrayal_q.ly
GNU LilyPond 2.18.2
Changing working directory to: `../test'
Processing `../test/betrayal_q.ly'
Parsing...
Interpreting music...[8][16][24][32][40][48][56]
Preprocessing graphical objects...
Finding the ideal number of pages...
Fitting music on 3 or 4 pages...
Drawing systems...
Layout output to `betrayal_q.ps'...
Converting to `./betrayal_q.pdf'...
Success: compilation successfully completed
``` 

And the resulting sheet music should appear as `betrayal-q.pdf` in theb test directory!
 
   
 
