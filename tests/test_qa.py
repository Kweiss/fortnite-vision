from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from droid_monitor.qa import save_alert_capture


class QaCaptureTests(unittest.TestCase):
    def test_saves_a_timestamped_raw_alert_capture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory)
            image = Image.new("RGB", (4, 3), color=(12, 34, 56))

            with patch("droid_monitor.qa.runtime_directory", return_value=runtime):
                path = save_alert_capture(image, "spawn", "Diamond Mythic")

            self.assertEqual(path.parent, runtime / "qa_captures")
            self.assertIn("spawn_diamond_mythic", path.name)
            with Image.open(path) as saved:
                self.assertEqual(saved.size, image.size)
                self.assertEqual(saved.getpixel((0, 0)), (12, 34, 56))
