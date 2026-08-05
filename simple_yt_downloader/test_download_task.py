"""Tests for the phase-aware download status labels in download_task.py.

Runs with the stdlib test runner (no GTK, no pytest, no network):
    python3 -m unittest simple_yt_downloader.test_download_task
"""

import unittest

from simple_yt_downloader.download_task import (
    PHASE_AUDIO,
    PHASE_MERGE,
    PHASE_VIDEO,
    DownloadTask,
    PhaseTracker,
    _split_custom_quality,
    phase_for_stream,
    phase_label,
)


class SplitCustomQualityTests(unittest.TestCase):
    def test_preset_is_height_only(self):
        self.assertEqual(_split_custom_quality("720"), ("720", None))

    def test_custom_parses_width_and_height(self):
        self.assertEqual(_split_custom_quality("custom:1920x1080"), ("1080", "1920"))

    def test_custom_ignores_case(self):
        self.assertEqual(_split_custom_quality("custom:3840X2160"), ("2160", "3840"))

    def test_malformed_custom_falls_back_to_720(self):
        for bad in ("custom:junk", "custom:", "custom:-5x-10", "custom:0x0"):
            self.assertEqual(_split_custom_quality(bad), ("720", None))

    def test_missing_value_falls_back_to_720(self):
        self.assertEqual(_split_custom_quality(""), ("720", None))
        self.assertEqual(_split_custom_quality(None), ("720", None))


class BuildFormatStringTests(unittest.TestCase):
    def _task(self, **kw):
        task = DownloadTask("https://example.com/v", "/tmp")
        for key, value in kw.items():
            setattr(task, key, value)
        return task

    def test_audio_mode_ignores_video_settings(self):
        task = self._task(mode="audio", video_quality="2160", video_fps="90")
        self.assertEqual(task.build_format_string(), "bestaudio")

    def test_default_video_chain(self):
        task = self._task()
        self.assertEqual(
            task.build_format_string(),
            "bestvideo[height<=720][ext=mp4]+bestaudio/"
            "bestvideo[height<=720]+bestaudio/best[height<=720]",
        )

    def test_fps_adds_constraint_with_fallbacks(self):
        task = self._task(video_fps="60")
        chain = task.build_format_string().split("/")
        self.assertIn("bestvideo[height<=720][fps<=60][ext=mp4]+bestaudio", chain)
        self.assertIn("bestvideo[height<=720]+bestaudio", chain)
        self.assertEqual(chain[-1], "best[height<=720]")

    def test_custom_resolution_uses_width_and_height(self):
        task = self._task(video_quality="custom:1920x1080")
        chain = task.build_format_string().split("/")
        self.assertIn("bestvideo[height<=1080][width<=1920][ext=mp4]+bestaudio", chain)
        self.assertIn("best[height<=1080]", chain)

    def test_custom_plus_fps_chain_is_fully_qualified_first(self):
        task = self._task(video_quality="custom:3840x2160", video_fps="90", video_format="webm")
        chain = task.build_format_string().split("/")
        self.assertEqual(
            chain[0],
            "bestvideo[height<=2160][width<=3840][fps<=90][ext=webm]+bestaudio",
        )

    def test_ext_is_equality_filter_not_range(self):
        task = self._task(video_format="mkv")
        chain = task.build_format_string().split("/")
        self.assertIn("bestvideo[height<=720][ext=mkv]+bestaudio", chain)
        for part in chain:
            self.assertNotIn("ext<=", part)


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
