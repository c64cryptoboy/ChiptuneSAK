# chiptunesSAK music intermediate representations

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
