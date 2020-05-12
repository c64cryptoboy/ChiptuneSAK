=========================
Import / Export
=========================

I/O Base Class
-------------------

All import and export of music formats is performed by classes that inherit from the ``ctsBase.ChiptuneSAKIO`` class.

The following methods are available in every I/O class.  If the song format is not supported by the individual I/O class, it will either attempt a conversion or raise a ``ChiptuneSAKNotImplemented`` exception. Either is acceptable behavior.


Import functions
++++++++++++++++

.. autoclass:: ctsBase.ChiptuneSAKIO
    :members: to_chirp, to_rchirp, to_mchirp

Export functions
++++++++++++++++

.. autoclass:: ctsBase.ChiptuneSAKIO
    :members: to_bin, to_file




GoatTracker
---------------------

.. currentmodule:: ctsGoatTracker

.. autoclass:: GoatTracker
    :members: to_rchirp, to_bin, to_file
    :show-inheritance:

import_sng_file_to_rchirp
+++++++++++++++++++++++++

.. autofunction:: import_sng_file_to_rchirp


GoatTracker Classes
-------------------

.. autoclass:: GTSong
    :members:

----

C128 BASIC Play Functions
-------------------------

.. currentmodule:: ctsC128Basic

.. autofunction:: export_midi_to_C128_BASIC

.. currentmodule:: ctsGenPrg

.. autofunction:: ascii_to_prg_c128

----

ML64 Functions
--------------

.. currentmodule:: ctsML64

.. autofunction:: export_mchirp_to_ml64

----

Lilypond sheetmusic Functions
-----------------------------

.. currentmodule:: ctsLilypond

.. autofunction:: export_song_to_lilypond

.. autofunction:: export_clip_to_lilypond

