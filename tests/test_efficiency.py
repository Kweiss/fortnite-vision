import unittest

from PIL import Image, ImageDraw

from droid_monitor.efficiency import (
    OCR_MODE_ADAPTIVE,
    FeedPerformanceSummary,
    ShadowAdaptiveComparison,
    SpawnFeedChangeGate,
)


class SpawnFeedChangeGateTests(unittest.TestCase):
    def test_static_feed_is_skipped_until_the_safety_refresh(self) -> None:
        gate = SpawnFeedChangeGate(safety_interval_seconds=6.0)
        frame = Image.new("RGB", (780, 220), "black")

        first = gate.inspect(frame, now=0.0)
        gate.record_ocr(now=0.0)
        quiet = gate.inspect(frame, now=2.0)
        refresh = gate.inspect(frame, now=6.0)

        self.assertTrue(first.should_run_ocr)
        self.assertFalse(quiet.should_run_ocr)
        self.assertEqual(quiet.reason, "unchanged")
        self.assertTrue(refresh.should_run_ocr)
        self.assertEqual(refresh.reason, "safety refresh")

    def test_colored_announcement_change_requires_ocr(self) -> None:
        gate = SpawnFeedChangeGate()
        empty = Image.new("RGB", (780, 220), "black")
        announced = empty.copy()
        ImageDraw.Draw(announced).rectangle((20, 30, 360, 54), fill=(0, 210, 255))

        gate.inspect(empty, now=0.0)
        gate.record_ocr(now=0.0)
        decision = gate.inspect(announced, now=2.0)

        self.assertTrue(decision.should_run_ocr)
        self.assertEqual(decision.reason, "feed changed")
        self.assertGreater(decision.changed_ratio, 0.0005)


class FeedPerformanceSummaryTests(unittest.TestCase):
    def test_observe_report_distinguishes_theoretical_skips(self) -> None:
        summary = FeedPerformanceSummary()
        summary.record(
            ocr_ran=True,
            would_skip=True,
            capture_seconds=0.01,
            gate_seconds=0.001,
            preprocessing_seconds=0.05,
            ocr_seconds=0.5,
        )

        message = summary.take_message("observe")

        self.assertIsNotNone(message)
        self.assertIn("would skip 1/1", message)
        self.assertIn("OCR 500 ms", message)
        self.assertIsNone(summary.take_message(OCR_MODE_ADAPTIVE))


class ShadowAdaptiveComparisonTests(unittest.TestCase):
    def test_skipped_event_caught_by_safety_scan_is_recorded_as_delay(self) -> None:
        comparison = ShadowAdaptiveComparison()
        event = "Galactic Droid (Epic) spawned at the Sandcrawler"

        comparison.record_frame(
            "recognized",
            {event: "Galactic Epic"},
            adaptive_ran=True,
            cooldown_seconds=45.0,
            now=0.0,
        )
        skipped = comparison.record_frame(
            "recognized",
            {"Diamond Droid (Mythic) spawned at the Sandcrawler": "Diamond Mythic"},
            adaptive_ran=False,
            cooldown_seconds=45.0,
            now=2.0,
        )
        recovered = comparison.record_frame(
            "recognized",
            {"Diamond Droid (Mythic) spawned at the Sandcrawler": "Diamond Mythic"},
            adaptive_ran=True,
            cooldown_seconds=45.0,
            now=6.0,
        )

        self.assertEqual(skipped, [])
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].outcome, "delayed")
        self.assertEqual(recovered[0].elapsed_seconds, 4.0)
        message = comparison.take_message()
        self.assertIn("reference 2 recognized", message)
        self.assertIn("shadow 2 recognized", message)
        self.assertIn("delayed 1 (avg 4.0s)", message)
        self.assertIn("missed 0", message)

    def test_skipped_event_that_leaves_the_feed_is_recorded_as_missed(self) -> None:
        comparison = ShadowAdaptiveComparison()
        event = "Rainbow Droid (Epic) spawned at the Sandcrawler"

        comparison.record_frame(
            "selected alert",
            {event: "Rainbow Epic"},
            adaptive_ran=False,
            cooldown_seconds=45.0,
            now=2.0,
        )
        missed = comparison.record_frame(
            "selected alert",
            {},
            adaptive_ran=False,
            cooldown_seconds=45.0,
            now=4.0,
        )

        self.assertEqual(len(missed), 1)
        self.assertEqual(missed[0].outcome, "missed")
        self.assertEqual(missed[0].label, "Rainbow Epic")
        self.assertEqual(missed[0].elapsed_seconds, 2.0)
        message = comparison.take_message()
        self.assertIn("reference 0 recognized / 1 selected alerts", message)
        self.assertIn("shadow 0 recognized / 0 selected alerts", message)
        self.assertIn("missed 1", message)
