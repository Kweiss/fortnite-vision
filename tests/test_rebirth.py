from pathlib import Path
import unittest

from PIL import Image

from droid_monitor.rebirth import RebirthReadyDetector


class RebirthReadyDetectorTests(unittest.TestCase):
    def test_matches_the_packaged_ready_badge_reference(self) -> None:
        reference_path = Path(__file__).parents[1] / "droid_monitor" / "assets" / "rebirth_ready_reference.png"
        with Image.open(reference_path) as image:
            score = RebirthReadyDetector().score(image)

        self.assertGreaterEqual(score, 0.95)

    def test_matches_the_ready_badge_at_nearby_scales(self) -> None:
        reference_path = Path(__file__).parents[1] / "droid_monitor" / "assets" / "rebirth_ready_reference.png"
        with Image.open(reference_path) as image:
            reference = image.convert("RGB")

        detector = RebirthReadyDetector()
        for scale in (0.8, 1.2):
            resized = reference.resize(
                (round(reference.width * scale), round(reference.height * scale)),
                Image.Resampling.LANCZOS,
            )
            self.assertGreaterEqual(detector.score(resized), 0.9)

    def test_does_not_match_an_empty_image(self) -> None:
        score = RebirthReadyDetector().score(Image.new("RGB", (750, 220), "black"))

        self.assertLess(score, 0.1)
