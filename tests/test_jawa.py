from pathlib import Path
import unittest

from PIL import Image

from droid_monitor.jawa import JawaAnnouncementDetector


class JawaAnnouncementDetectorTests(unittest.TestCase):
    def test_matches_the_supplied_recycle_reference(self) -> None:
        reference_path = Path(__file__).parents[1] / "droid_monitor" / "assets" / "jawa_reference.png"
        with Image.open(reference_path) as image:
            score = JawaAnnouncementDetector().score(image)

        self.assertGreaterEqual(score, 0.95)

    def test_matches_the_recycle_reference_at_smaller_and_larger_scales(self) -> None:
        reference_path = Path(__file__).parents[1] / "droid_monitor" / "assets" / "jawa_reference.png"
        with Image.open(reference_path) as image:
            reference = image.convert("RGB")

        detector = JawaAnnouncementDetector()
        for scale in (0.5, 2.4):
            resized = reference.resize(
                (round(reference.width * scale), round(reference.height * scale)),
                Image.Resampling.LANCZOS,
            )
            self.assertGreaterEqual(detector.score(resized), 0.95)

    def test_does_not_match_an_empty_image(self) -> None:
        score = JawaAnnouncementDetector().score(Image.new("RGB", (900, 850), "black"))

        self.assertLess(score, 0.1)
