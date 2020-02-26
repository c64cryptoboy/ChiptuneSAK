# C128 BASIC music programs

## Introduction
The Commodore 128's BASIC 7.0 has commands for playing music.

TODO: Write quick overview

## chiptunesSAK handles the tedium for you
TODO: Write about how the original documentation only did a two voice example, full of errors.

TODO: Include a picture of a single measure of the Bach test data that shows how complicated it can be to establish the play order of the notes correctly

## How tempo is calculated

Tempo is 1 to 255, where 1 is the slowest, and 255 is the fastest speed

Internally, the C128 assigns the following starting duration values to the following note types (see BASIC ROM dissasembly starting at $6F07):
* Whole/Semibreve = 1152 (note: 1152 is 2^7 * 3^2)
* Half/Minim = 576
* Quarter/Crotchet = 288
* Eighth/Quaver = 144
* Sixteenth/Semiquaver = 72

Each voice that is playing a note has a certain amount of duration left.  Once per screen refresh, the C128 BASIC IRQ routine is called, which updates sprites, music, etc.  On each update, each voice's remaining note duration has the tempo value subtracted from it.  When the subtraction results in a value < 0, the note is done.  This implies the following:
1. Otherwise simultanious notes will sometimes playback in a staggered way at certain tempos, due to "roundoff" error caused by subtracting a tempo that does not evenly divide the remaining duration values 
2. NTSC has faster playback than PAL

