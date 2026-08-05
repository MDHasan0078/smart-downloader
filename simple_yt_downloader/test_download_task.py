"""Tests for the phase-aware download status labels in download_task.py.

Runs with the stdlib test runner (no GTK, no pytest, no network):
    python3 -m unittest simple_yt_downloader.test_download_task
"""

import unittest

from simple_yt_downloader.download_task import (
    PHASE_AUDIO,
    PHASE_MERGE,
    PHASE_VIDEO,
    PhaseTracker,
    phase_for_stream,
    phase_label,
)


class PhaseForStreamTests(unittest.TestCase):
    def test_video_mode_two_streams(self):
        self.assertEqual(phase_for_stream("video", 1), PHASE_VIDEO)
        self.assertEqual(phase_for_stream("video", 2), PHASE_AUDIO)

    def test_audio_mode_is_always_audio(self):
        self.assertEqual(phase_for_stream("audio", 1), PHASE_AUDIO)
        self.assertEqual(phase_for_stream("audio", 2), PHASE_AUDIO)


class PhaseLabelTests(unittest.TestCase):
    def test_download_phase_labels(self):
        self.assertEqual(phase_label(PHASE_VIDEO), "Downloading video")
        self.assertEqual(phase_label(PHASE_AUDIO), "Downloading audio")

    def test_merge_phase_is_tag_aware(self):
        self.assertEqual(phase_label(PHASE_MERGE, "Merger"), "Merging…")
        self.assertEqual(phase_label(PHASE_MERGE, "ExtractAudio"), "Converting to audio…")

    def test_merge_phase_fallbacks(self):
        self.assertEqual(phase_label(PHASE_MERGE, "Metadata"), "Merging…")
        self.assertEqual(phase_label(PHASE_MERGE, None), "Merging…")

    def test_unknown_phase_falls_back_to_downloading(self):
        self.assertEqual(phase_label("something-else"), "Downloading")


class PhaseTrackerTests(unittest.TestCase):
    def test_two_stream_video_sequence(self):
        tracker = PhaseTracker("video", expected_streams=2)
        self.assertEqual(tracker.phase_label, "Downloading video")
        self.assertEqual(tracker.stream_number, 0)

        self.assertEqual(
            tracker.note_line('[download] Destination: clip.f137.mp4'),
            "Downloading video",
        )
        self.assertEqual(tracker.stream_number, 1)
        self.assertEqual(tracker.phase, PHASE_VIDEO)

        self.assertIsNone(
            tracker.note_line('[download]  45.0% of 10.00MiB at 1.00MiB/s ETA 00:10')
        )

        self.assertEqual(
            tracker.note_line('[download] Destination: clip.f140.m4a'),
            "Downloading audio",
        )
        self.assertEqual(tracker.stream_number, 2)
        self.assertEqual(tracker.phase, PHASE_AUDIO)

        self.assertEqual(
            tracker.note_line('[Merger] Merging formats into "clip.mp4"'),
            "Merging…",
        )
        self.assertEqual(tracker.phase, PHASE_MERGE)
        self.assertEqual(tracker.postprocess_tag, "merger")

    def test_single_stream_audio_with_extractaudio(self):
        tracker = PhaseTracker("audio", expected_streams=1)
        self.assertEqual(tracker.phase_label, "Downloading audio")

        self.assertEqual(
            tracker.note_line('[download] Destination: clip.f140.m4a'),
            "Downloading audio",
        )
        self.assertEqual(
            tracker.note_line('[ExtractAudio] Destination: clip.mp3'),
            "Converting to audio…",
        )
        self.assertEqual(tracker.phase, PHASE_MERGE)
        self.assertEqual(tracker.postprocess_tag, "extractaudio")

    def test_already_downloaded_advances_ordinal_without_reemit(self):
        tracker = PhaseTracker("video", expected_streams=2)
        self.assertIsNone(
            tracker.note_line('[download] clip.f137.mp4 has already been downloaded')
        )
        self.assertEqual(tracker.stream_number, 1)

        self.assertEqual(
            tracker.note_line('[download] Destination: clip.f140.m4a'),
            "Downloading audio",
        )
        self.assertEqual(tracker.stream_number, 2)

    def test_progress_dict_keeps_raw_fields_and_adds_phase(self):
        tracker = PhaseTracker("video", expected_streams=2)
        payload = tracker.progress_dict(42.5, "10.0MiB", "1.0MiB/s", "00:10")

        self.assertEqual(payload["percent"], 42.5)
        self.assertEqual(payload["size"], "10.0MiB")
        self.assertEqual(payload["speed"], "1.0MiB/s")
        self.assertEqual(payload["eta"], "00:10")
        self.assertEqual(payload["phase"], PHASE_VIDEO)
        self.assertEqual(payload["phase_label"], "Downloading video")
        self.assertEqual(payload["stream_index"], 0)
        self.assertEqual(payload["stream_total"], 2)
        self.assertNotIn("fraction", payload)

    def test_merge_progress_dict(self):
        tracker = PhaseTracker("video", expected_streams=2)
        tracker.note_line('[download] Destination: clip.f137.mp4')
        tracker.note_line('[download] Destination: clip.f140.m4a')
        tracker.note_line('[Merger] Merging formats into "clip.mp4"')
        payload = tracker.progress_dict(100.0, "", "", "")
        self.assertEqual(payload["phase"], PHASE_MERGE)
        self.assertEqual(payload["phase_label"], "Merging…")


if __name__ == "__main__":
    unittest.main()
