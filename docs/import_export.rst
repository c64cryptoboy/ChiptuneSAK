=========================
Import / Export
=========================

.. contents::

I/O Base Class
-------------------

All import and export of music formats is performed by classes that inherit from the ``chiptunesak.base.ChiptuneSAKIO`` class.

The following methods are available in every I/O class.  If the song format is not supported by the individual I/O class, it will either attempt a conversion or raise a ``chiptunesak.errors.ChiptuneSAKNotImplemented`` exception. Either is acceptable behavior.


Import functions
++++++++++++++++

.. autoclass:: chiptunesak.base.ChiptuneSAKIO
    :members: to_chirp, to_rchirp, to_mchirp
    :noindex:

Export functions
++++++++++++++++

.. autoclass:: chiptunesak.base.ChiptuneSAKIO
    :members: to_bin, to_file
    :noindex:


MIDI
----

.. currentmodule:: chiptunesak.midi

.. autoclass:: MIDI
    :members: to_chirp, to_file
    :show-inheritance:
    :noindex:

GoatTracker
---------------------

.. currentmodule:: chiptunesak.goat_tracker

.. autoclass:: GoatTracker
    :members: to_rchirp, to_bin, to_file
    :show-inheritance:
    :noindex:

Lilypond
--------

.. currentmodule:: chiptunesak.lilypond

.. autoclass:: Lilypond
    :members: to_bin, to_file
    :show-inheritance:
    :noindex:

C128 BASIC
----------

.. currentmodule:: chiptunesak.c128_basic

.. autoclass:: C128Basic
    :members: to_bin, to_file
    :show-inheritance:
    :noindex:

ML64
----

.. currentmodule:: chiptunesak.ml64

.. autoclass:: ML64
    :members: to_bin, to_file
    :show-inheritance:
    :noindex:
