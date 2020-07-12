
===================
Commodore SID Music
===================

SID files
+++++++++

The term "SID" is commonly used to refer to a file containing Commodore 64 music.  This should not be confused with the "SID" (6581/8580 Sound Interface Device) sound chip used in the Commodore 64, 128, MAX, and CBM-II computers.

A SID file contains a Commodore-native-code payload that plays music, along with headers that describe how to execute the payload.  SID files often contain subtunes, which are a collection of tunes that usually share the same playback engine, "instruments", and reusable patterns of musical notes.

A variety of SID file players have been developed over the years, from `native C64 implementations <https://sourceforge.net/projects/sidplay64/>`_  to playback on one's `Android phone <https://play.google.com/store/apps/details?id=org.garageapps.android.sidamp>`_.  Nearly all Commodore games have had their music preserved in SID files, and the format is how contemporary C64 music is exchanged today.  It's described in detail `here <https://www.hvsc.c64.org/download/C64Music/DOCUMENTS/SID_file_format.txt>`_.

To play SID music, 6502 machine language emulation is required.  Under the covers, each SID file contains either a PSID ("PlaySID") or RSID ("Real SID") payload.  PSIDs can play back on low-fidelity emulation, while an RSID requires anywhere from a low-fidelity emulation to a full C64 emulator to play back correctly.   As of release #72 of the `High Voltage SID Collection <https://www.hvsc.c64.org/>`_, the set contains 49,119 PSIDs and 3,208 RSID riles, of which 495 of the RSID files are written in BASIC.   (It's actually quite impressive that this level of generality can be brought to bear on arbitrarily-crafted C64 music code, so hats off to the HVSC team for having normalized the playback experience of tens of thousands of Commodore music programs).

The Commodore-native payload must contain an initialization entry point and a play routine entry point.  The play routine is called by the SID player at regular intervals determined by an interrupt.  The more frequently the play routine is called, the faster the song plays back.  The SID file headers contain a set of "speed" flags, that indicate by which kind of interrupt a particular subtune should have its play routine invoked.  It either specifies using VBI (Vertical Blank Interrupt), declaring that a raster interrupt will call the play routine once per frame, or a CIA (Complex Interface Adapter) timer interrupt, which can give easier control over how often the play routine is called per frame.  For PSID files, the VBI must trigger at some raster value less than 256, while RSID is supposed to only use raster 311.  If CIA, then the CIA 1 timer A cycle count defaults to its PAL or NTSC KERNAL bootup settings.

Some SIDs are "multispeed", meaning that the play routine is called more than once per frame.  Both PSIDs and RSIDs can be multispeed.  It is likely that for multispeed PSID files to play back correctly in many low-fidelity emulation players, those PSIDs must set the CIA #1 Timer A in their init routine to indicate how much shorter the play interval is than the frame interval.


Importing SID files
+++++++++++++++++++

ChiptuneSAK has functionality that can import music in a SID file into RChirp, which can then be converted to a variety of output formats.

Our importer is meant to be an alternative to Michael Schwendt's `SID2MIDI tool <https://csdb.dk/release/?id=136776>`_, as that tool is closed source, has not been updated since 2007, is Windows only, and won't process RSIDs.  SID2MIDI also creates fairly messy sheet music when first imported into music engraving tools (such as Sibelius, Dorico, Finale, MuseScore, etc.), since its output is not processed with the intention of having notes fall cleanly into time-signature governed measures.  Our tool chain is designed to directly addresses these issues.

The ChiptuneSAK's SID importing capabilities were originally based on Lassee Oorni's (Cadaver, of Goat Tracker fame) and Stein Pedersen's excellent `SIDDump tool <https://csdb.dk/release/?id=192079>`_ (i.e., our python emulator_6502.py module is very close in functionality to SIDDump's cpu.c code).

ChiptuneSAK will import PSID and some RSID files.  Likely, some RSID files may require a higher-level of emulation fidelity that we currently provide (e.g., volume-based samples, using additional interrupt sources, etc.).  Not knowing which RSIDs ChiptuneSAK can handle, it will always make the import attempt (unless the RSID is coded in BASIC).  Since this is open source, a non-working example is an opportunity to increase the fidelity of the python parsing code. :)
