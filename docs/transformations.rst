============================================
Music Processing and Transformation in Chirp
============================================

.. contents::

Most music transformation and processing capabilities in ChiptuneSAK are performed in the Chirp representation. The Chirp classes together implement a rich set of transformations to allow straightforward programmatic control over many song details.

To perform these operations, music is imported and converted to the Chirp representation.  The :ref:`ChirpSong` and :ref:`ChirpTrack` classes have a large number of pre-defined music transformation methods, and are designed to make addition of new methods straightforward.

For transformations involving changing notes, if a method is defined for a :ref:`ChirpSong` class, the same method is defined for the :ref:`ChirpTrack` class; the track method is called by the song method for all tracks.

Metadata transformations either apply to the complete song or to an individual track.

Simple Transformations
++++++++++++++++++++++

.. automethod:: chiptunesak.chirp.ChirpSong.transpose
   :noindex:

.. automethod:: chiptunesak.chirp.ChirpSong.scale_ticks
   :noindex:

.. automethod:: chiptunesak.chirp.ChirpSong.move_ticks
   :noindex:

.. automethod:: chiptunesak.chirp.ChirpSong.truncate
   :noindex:

Quantization Transformations
++++++++++++++++++++++++++++

.. automethod:: chiptunesak.chirp.ChirpSong.estimate_quantization
   :noindex:

.. automethod:: chiptunesak.chirp.ChirpSong.quantize
   :noindex:

.. automethod:: chiptunesak.chirp.ChirpSong.quantize_from_note_name
   :noindex:

All the above methods make use of this quantization function:

.. automethod:: chiptunesak.chirp.quantize_fn
   :noindex:


Polyphony Transformations
+++++++++++++++++++++++++

.. automethod:: chiptunesak.chirp.ChirpSong.remove_polyphony
   :noindex:

.. automethod:: chiptunesak.chirp.ChirpSong.explode_polyphony
   :noindex:

Metadata Transformations
++++++++++++++++++++++++

.. automethod:: chiptunesak.chirp.ChirpSong.set_time_signature
   :noindex:

.. automethod:: chiptunesak.chirp.ChirpSong.set_key_signature
   :noindex:

.. automethod:: chiptunesak.chirp.ChirpSong.set_qpm
   :noindex:

Advanced Transformations
++++++++++++++++++++++++

.. automethod:: chiptunesak.chirp.ChirpSong.remove_keyswitches
   :noindex:

.. automethod:: chiptunesak.chirp.ChirpSong.modulate
   :noindex:


The following are meant to be applied to individual tracks and have no corresponding methods in the :ref:`ChirpSong` class:

.. automethod:: chiptunesak.chirp.ChirpTrack.merge_notes
   :noindex:

.. automethod:: chiptunesak.chirp.ChirpTrack.remove_short_notes
   :noindex:

.. automethod:: chiptunesak.chirp.ChirpTrack.set_min_note_len
   :noindex:
