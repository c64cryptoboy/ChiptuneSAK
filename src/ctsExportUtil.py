import copy
from ctsErrors import *
import ctsConstants
import ctsSong
import more_itertools as moreit

""" Utility functions for exporting to various formats from the ctsSong.Song representation """


class Measure:
    @staticmethod
    def sort_order(c):
        """
        Sort function for measure contents.
        Items are sorted by time and then, for equal times, in this order:
            Time Signature
            Key Signature
            Tempo
            Other MIDI message(s)
            Notes and rests
        """
        if isinstance(c, ctsSong.Note):
            return (c.start_time, 10)
        elif isinstance(c, ctsSong.Rest):
            return (c.start_time, 10)
        elif isinstance(c, ctsSong.MeasureMarker):
            return (c.start_time, 0)
        elif isinstance(c, ctsSong.TimeSignature):
            return (c.start_time, 1)
        elif isinstance(c, ctsSong.KeySignature):
            return (c.start_time, 2)
        elif isinstance(c, ctsSong.Tempo):
            return (c.start_time, 3)
        elif isinstance(c, ctsSong.Program):
            return (c.start_time, 4)
        else:
            return (c.start_time, 5)

    def __init__(self, start_time, duration, events=None):
        self.reset()
        self.start_time = start_time
        self.duration = duration
        if events:
            self.events = copy.deepcopy(events)

    def reset(self):
        self.start_time = 0
        self.duration = 0
        self.events = []

    def populate(self, track, carry=None):
        n_notes = len(track.notes)
        inote = 0
        while inote < n_notes and track.notes[inote].start_time < self.start_time:
            inote += 1
        # Measure number is obtained from the song.
        self.events.append(ctsSong.MeasureMarker(self.start_time, track.song.get_measure_beat(self.start_time).measure))
        end = self.start_time + self.duration
        last_note_end = self.start_time
        if carry:  # Deal with any notes carried over from the previous measure
            carry.start_time = self.start_time
            carry_end = self.start_time + carry.duration
            if carry.duration <= 0:
                raise ChiptuneSAKValueError("Illegal carry note duration %d" % carry.duration, str(carry))
            if carry_end > end:  # Does the carried note extend past the end of this measure?
                self.events.append(ctsSong.Note(carry.note_num, self.start_time, end-self.start_time, 100, tied=True))
                carry.duration -= end - self.start_time
                last_note_end = end
            else:  # Carried note ends during this measure
                self.events.append(carry)
                last_note_end = self.start_time + carry.duration
                carry = None

        # Now iterate over the notes that begin during this measure
        while inote < n_notes and track.notes[inote].start_time < end:
            n = track.notes[inote]
            gap = n.start_time - last_note_end
            if gap > 0:  # Is there a rest before the note starts?
                self.events.append(ctsSong.Rest(last_note_end, gap))
                last_note_end = n.start_time
            note_end = n.start_time + n.duration  # Time that this note ends
            if note_end <= end:  # Note fits within the current measure
                self.events.append(n)
                last_note_end = note_end
            else:
                carry = copy.copy(n)  # Make a copy of the note to use for the carry
                duration = end - n.start_time
                n.duration = duration  # truncate the note to the end of the measure
                n.tied = True  # And mark it as tied to the next note
                self.events.append(n)
                last_note_end = end
                carry.duration -= duration  # Det the length of the carried note to the remaining time
            inote += 1  # Move to the next note

        gap = end - last_note_end
        if gap > 0:  # Is there a rest needed at the end of the measure?
            self.events.append(ctsSong.Rest(last_note_end, gap))
            last_note_end = end

        # Add any additional track-specific messages to the measure:
        for m in track.other:
            if self.start_time <= m.start_time < end:
                # Leave the time of these messages alone
                if m.msg.type == 'program_change':  # Split out program changes
                    self.events.append(ctsSong.Program(m.start_time, m.msg.program))
                else:
                    self.events.append(m)

        #  Now add all the song-specific events to the measure.
        for ks in track.song.key_signature_changes:
            if self.start_time <= ks.start_time < end:
                # Key signature changes must occur at the start of the measure
                self.events.append(ctsSong.KeySignature(self.start_time, ks.key))

        for ts in track.song.time_signature_changes:
            if self.start_time <= ts.start_time < end:
                # Time signature changes must occur at the start of the measure
                self.events.append(ctsSong.TimeSignature(self.start_time, ts.num, ts.denom))

        for tm in track.song.tempo_changes:
            if self.start_time <= tm.start_time < end:
                # Tempo changes can happen anywhere in the measure
                self.events.append(ctsSong.Tempo(tm.start_time, tm.bpm))

        for m in track.song.other:
            if self.start_time <= m.start_time < end:
                # Leave the time of these messages alone
                self.events.append(m)

        self.events = sorted(self.events, key=self.sort_order)

        return carry

    def count_notes(self):
        return sum(1 for e in self.events if isinstance(e, ctsSong.Note))


def populate_measures(track):
    """
    Converts a track into measures, each of which is a sorted list of notes and other events
    """
    measures_list = []
    measure_starts = track.song.measure_starts()
    # Artificially add an extra measure on the end to finish processing the notes in the last measure.
    measure_starts.append(2 * measure_starts[-1] - measure_starts[-2])
    # First add in the notes to the measure
    imeasure = 0
    carry = None
    for start, end in moreit.pairwise(measure_starts):
        current_measure = Measure(start, end - start)
        carry = current_measure.populate(track, carry)
        measures_list.append(current_measure)
    return measures_list


def trim_measures(measures_list):
    """
    Trims all note-free measures from the end of the song.
    """
    while all(m[-1].count_notes() == 0 for m in measures_list):
        for i in range(len(measures_list)):
            measures_list[i].pop()
    return measures_list


def get_measures(song):
    """
    Gets all the measures from all the tracks in a song, and removes any extra measures from the end.
    """
    all_measures = [populate_measures(t) for t in song.tracks]
    return trim_measures(all_measures)
