==================
Music Quantization
==================

Written music on a page has notes of exact lengths and start times, but live performance of music is always a little imprecise; that is, in part, what makes a live performance feel *live*.

Most early computer-music formats required that notes start and end on exact time intervals. Many popular music genres today use similarly exact notes and rhythms.

The process of converting live-performance or inexact to exact start times and durations is called *quantization*.

Much of the processing that ChiptuneSAK uses to modify, display, and convert between music formats requires quantized music. ChiptuneSAK uses unique algorithms to quantize music and also provides the ability to de-quantize music output to some formats.

ChiptuneSAK Quantization
------------------------

If the desired quantization is known *a priori*, ChiptuneSAK will quantize note starts and durations to known parameters.

For source material where note starts and durations are close to exact note lengths, but are noisy, and/or the  minimum note length is not known, ChiptuneSAK provides an algorithm that automatically finds and applies the optimum quantization.

For source material where the note lengths and time offsets are not known well, ChiptuneSAK provides tools to help adjust the music to the point where quantization can be used.

Base Quantization Functions
+++++++++++++++++++++++++++

All the quantization functions are applied in the :ref:`Chirp Representation` of the music.

The base quantization functions that encapsulate the algorithm and perform the quantization are:

.. autofunction:: ctsChirp.find_quantization

.. autofunction:: ctsChirp.find_duration_quantization

.. autofunction:: ctsChirp.quantize_fn

Quantization Methods
++++++++++++++++++++

Primary use of the quantization algorithms occurs through methods of the :ref:`ChirpSong` and :ref:`ChirpTrack` classes.

.. autoclass:: ctsChirp.ChirpSong
    :members: estimate_quantization, quantize, quantize_from_note_name
    :noindex:

.. autoclass:: ctsChirp.ChirpTrack
    :members: estimate_quantization, quantize
    :noindex:

