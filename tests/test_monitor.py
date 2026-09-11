import unittest
from unittest.mock import patch

from PIL import Image

from droid_monitor.config import AppConfig, CropRegion
from droid_monitor.monitor import MonitorWorker


class _Capture:
    def capture(self, *_: object) -> Image.Image:
        return Image.new("RGB", (20, 20), "black")


class _Scores:
    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)

    def score(self, _: Image.Image) -> float:
        return next(self._values)


class MonitorWorkerTests(unittest.TestCase):
    def test_rebirth_alerts_once_until_the_ready_badge_clears(self) -> None:
        worker = MonitorWorker(
            AppConfig(
                rebirth_ready_enabled=True,
                rebirth_ready_crop=CropRegion(x=0, y=0, width=20, height=20),
                rebirth_ready_match_threshold=0.7,
            )
        )
        detector = _Scores([0.8, 0.65, 0.5, 0.8])
        emitted_alerts: list[tuple[object, ...]] = []

        with patch.object(worker, "_emit_alert", side_effect=lambda *args: emitted_alerts.append(args)):
            for _ in range(4):
                worker._check_rebirth_ready(_Capture(), worker._current_config(), detector)  # type: ignore[arg-type]

        self.assertEqual(len(emitted_alerts), 2)
        self.assertEqual(emitted_alerts[0][3], "Ready for Rebirth!")
        self.assertEqual(emitted_alerts[1][3], "Ready for Rebirth!")
