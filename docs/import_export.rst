=========================
Import / Export
=========================

.. contents::

I/O Base Class
-------------------

All import and export of music formats is performed by classes that inherit from the ``ctsBase.ChiptuneSAKIO`` class.

The following methods are available in every I/O class.  If the song format is not supported by the individual I/O class, it will either attempt a conversion or raise a ``ChiptuneSAKNotImplemented`` exception. Either is acceptable behavior.


Import functions
++++++++++++++++

.. autoclass:: ctsBase.ChiptuneSAKIO
    :members: to_chirp, to_rchirp, to_mchirp
    :noindex:

Export functions
++++++++++++++++

.. autoclass:: ctsBase.ChiptuneSAKIO
    :members: to_bin, to_file
    :noindex:


MIDI
----

.. currentmodule:: ctsMidi

.. autoclass:: MIDI
    :members: to_chirp, to_file
    :show-inheritance:
    :noindex:

GoatTracker
---------------------

.. currentmodule:: ctsGoatTracker

.. autoclass:: GoatTracker
    :members: to_rchirp, to_bin, to_file
    :show-inheritance:
    :noindex:

Lilypond
--------

.. currentmodule:: ctsLilypond

.. autoclass:: Lilypond
    :members: to_bin, to_file
    :show-inheritance:
    :noindex:

C128 BASIC
----------

.. currentmodule:: ctsC128Basic

.. autoclass:: C128Basic
    :members: to_bin, to_file
    :show-inheritance:
    :noindex:

ML64
----

.. currentmodule:: ctsML64

.. autoclass:: ML64
    :members: to_bin, to_file
    :show-inheritance:
    :noindex:

