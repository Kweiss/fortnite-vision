from datetime import datetime
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from droid_monitor.rebirth_progress import (
    RebirthProgress,
    load_rebirth_progress,
    parse_hud_text,
    parse_requirements_screen,
    save_rebirth_progress,
)


class RebirthProgressTests(unittest.TestCase):
    def test_parses_lower_left_hud_values(self) -> None:
        hud = parse_hud_text(
            "4.60T\n93.96K\n54\n21\n69.3x\nXAERRAN",
            datetime(2026, 8, 1, 11, 0, 0),
        )

        self.assertIsNotNone(hud)
        self.assertEqual(hud.credits, "4.60T")  # type: ignore[union-attr]
        self.assertEqual(hud.upgrade_chips, "93.96K")  # type: ignore[union-attr]
        self.assertEqual(hud.nova_crystals, "54")  # type: ignore[union-attr]
        self.assertEqual(hud.rebirth_level, 21)  # type: ignore[union-attr]

    def test_parses_requirements_and_card_statuses(self) -> None:
        panel = Image.new("RGB", (1350, 600), "black")
        draw = ImageDraw.Draw(panel)
        slots = ((179, 147), (414, 147), (650, 147), (886, 147))
        for index, (x, y) in enumerate(slots):
            color = (255, 0, 0) if index in {0, 3} else (0, 255, 100)
            draw.rectangle((x, y, x + 218, y + 217), outline=color, width=5)

        requirements = parse_requirements_screen(
            panel,
            "\n".join(
                (
                    "NEED",
                    "13.50T",
                    "BESKAR",
                    "DEFAULT",
                    "STELLAR",
                    "Credits",
                    "Mono-WLKR",
                    "RIC-1200",
                    "TRI-TEK",
                )
            ),
            "Rank 25",
            "Path 2",
            datetime(2026, 8, 1, 11, 0, 0),
        )

        self.assertIsNotNone(requirements)
        self.assertEqual(requirements.path, 2)  # type: ignore[union-attr]
        self.assertEqual(requirements.target_rank, 25)  # type: ignore[union-attr]
        self.assertEqual(requirements.credit_requirement, "13.50T")  # type: ignore[union-attr]
        self.assertEqual(
            [(item.droid_name, item.variant, item.owned) for item in requirements.droids],  # type: ignore[union-attr]
            [
                ("Mono-WLKR", "Beskar", True),
                ("RIC-1200", "Default", True),
                ("TRI-TEK", "Stellar", False),
            ],
        )

    def test_persists_progress_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rebirth_progress.json"
            progress = RebirthProgress()

            save_rebirth_progress(progress, path)

            self.assertEqual(load_rebirth_progress(path), progress)
