from pathlib import Path
import tempfile
import unittest
import json

from droid_monitor.config import AppConfig, CropRegion, load_config, save_config
from droid_monitor.domain import DEFAULT_ENABLED_RULE_IDS, STELLAR_RULE_IDS
from droid_monitor.efficiency import OCR_MODE_ADAPTIVE


class ConfigTests(unittest.TestCase):
    def test_default_scan_interval_prioritizes_alert_latency(self) -> None:
        self.assertEqual(AppConfig().scan_interval_seconds, 0.75)

    def test_default_crop_matches_the_six_row_feed(self) -> None:
        self.assertEqual(CropRegion(), CropRegion(x=40, y=640, width=780, height=220))

    def test_default_jawa_crop_focuses_on_the_recycle_toast_area(self) -> None:
        self.assertEqual(
            AppConfig().jawa_crop,
            CropRegion(x=2900, y=750, width=600, height=600),
        )

    def test_default_rebirth_crop_covers_the_bottom_center_ready_badge(self) -> None:
        self.assertTrue(AppConfig().rebirth_ready_enabled)
        self.assertEqual(
            AppConfig().rebirth_ready_crop,
            CropRegion(x=1650, y=1760, width=750, height=220),
        )

    def test_default_rebirth_progress_crop_covers_the_lower_left_hud(self) -> None:
        self.assertTrue(AppConfig().rebirth_progress_enabled)
        self.assertEqual(
            AppConfig().rebirth_hud_crop,
            CropRegion(x=40, y=1760, width=1110, height=210),
        )

    def test_config_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            original = AppConfig(
                monitor_index=2,
                crop=CropRegion(x=12, y=34, width=500, height=90),
                scan_interval_seconds=1.5,
                spawn_ocr_mode=OCR_MODE_ADAPTIVE,
                test_mode=True,
                always_on_top=True,
                jawa_enabled=True,
                jawa_crop=CropRegion(x=2100, y=1000, width=800, height=700),
                jawa_match_threshold=0.7,
                rebirth_ready_enabled=False,
                rebirth_ready_crop=CropRegion(x=1700, y=1800, width=700, height=200),
                rebirth_ready_match_threshold=0.75,
                rebirth_progress_enabled=False,
                rebirth_hud_crop=CropRegion(x=20, y=1700, width=1000, height=180),
                telegram_enabled=True,
                telegram_chat_id="123456789",
                enabled_rule_ids=frozenset({"rainbow_legendary"}),
            )

            save_config(original, path)

            self.assertEqual(load_config(path), original)

    def test_invalid_crop_is_rejected(self) -> None:
        config = AppConfig(crop=CropRegion(width=0, height=50))

        with self.assertRaisesRegex(ValueError, "width"):
            config.validate()

    def test_invalid_ocr_mode_is_rejected(self) -> None:
        config = AppConfig(spawn_ocr_mode="fastest")

        with self.assertRaisesRegex(ValueError, "OCR mode"):
            config.validate()

    def test_all_selected_legacy_rules_gain_the_new_diamond_alerts(self) -> None:
        legacy_rule_ids = [
            "galatic_mythic",
            "galatic_legendary",
            "galatic_epic",
            "beskar_mythic",
            "beskar_legendary",
            "beskar_epic",
            "rainbow_mythic",
            "rainbow_legendary",
            "rainbow_epic",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"enabled_rule_ids": legacy_rule_ids}), encoding="utf-8")

            self.assertEqual(load_config(path).enabled_rule_ids, DEFAULT_ENABLED_RULE_IDS)

    def test_existing_rule_selection_gains_enabled_stellar_alerts_once(self) -> None:
        existing_selection = ["galatic_epic", "beskar_mythic"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"enabled_rule_ids": existing_selection}), encoding="utf-8")

            config = load_config(path)

            self.assertEqual(
                config.enabled_rule_ids,
                frozenset(existing_selection) | STELLAR_RULE_IDS,
            )
            self.assertEqual(config.alert_rule_version, 2)
