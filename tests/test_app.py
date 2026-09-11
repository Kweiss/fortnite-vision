import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt6.QtWidgets import QApplication, QLabel, QToolButton

from droid_monitor.app import DroidMonitorWindow
from droid_monitor.domain import ALERT_RULES


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @patch("droid_monitor.app._set_window_topmost", return_value=True)
    def test_always_on_top_uses_native_window_api(self, set_topmost: object) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = DroidMonitorWindow(Path(directory) / "config.json")
            window.show()
            self.app.processEvents()

            window.always_on_top.setChecked(True)

            self.assertTrue(window.always_on_top.isChecked())
            self.assertTrue(set_topmost.called)  # type: ignore[attr-defined]
            self.assertEqual(set_topmost.call_args.args[1], True)  # type: ignore[attr-defined]
            window.close()

    def test_live_dashboard_keeps_the_existing_alert_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = DroidMonitorWindow(Path(directory) / "config.json")

            self.assertEqual(window.pages.count(), 4)
            self.assertEqual(
                [checkbox.text() for checkbox in window._rule_checkboxes.values()],
                [f"{rule.emoji}  {rule.label}" for rule in ALERT_RULES],
            )
            self.assertTrue(all(checkbox.isChecked() for checkbox in window._rule_checkboxes.values()))
            self.assertTrue(window.rebirth_ready_enabled.isChecked())
            self.assertEqual(
                window._alert_source_label("Ready for Rebirth detected"),
                "Rebirth readiness",
            )
            window.close()

    def test_alerts_are_added_to_live_and_history_views(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = DroidMonitorWindow(Path(directory) / "config.json")

            window._on_alert(
                "Diamond Mythic!",
                "Diamond Droid (Mythic) spawned at the Sandcrawler",
                "alert-key",
            )

            self.assertEqual(len(window._live_alert_rows), 1)
            self.assertEqual(len(window._history_alert_rows), 1)
            self.assertIn("alert-key", window._alert_rows_by_key)
            self.assertFalse(window.live_alerts_empty.isVisible())
            self.assertFalse(window.history_alerts_empty.isVisible())

            path = Path(directory) / "evidence.png"
            Image.new("RGB", (8, 8), color=(20, 30, 40)).save(path)
            window._on_alert_evidence_ready("alert-key", str(path))

            self.assertNotIn("alert-key", window._alert_rows_by_key)
            for row in (*window._live_alert_rows, *window._history_alert_rows):
                metadata = row.findChild(QLabel, "alertMeta")
                timestamp = row.findChild(QLabel, "alertTime")
                button = next(
                    candidate
                    for candidate in row.findChildren(QToolButton)
                    if candidate.property("evidence_button")
                )
                self.assertIsNotNone(metadata)
                self.assertEqual(metadata.text(), "Droid spawn feed | QA capture ready")  # type: ignore[union-attr]
                self.assertIsNotNone(timestamp)
                self.assertRegex(
                    timestamp.text(),  # type: ignore[union-attr]
                    r"^[A-Z][a-z]{2} \d{1,2}, \d{4}\n\d{1,2}:\d{2}:\d{2} [AP]M$",
                )
                self.assertTrue(button.isEnabled())
            window.close()

    def test_alert_history_keeps_rows_readable_and_scrollable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = DroidMonitorWindow(Path(directory) / "config.json")
            window.resize(1_260, 820)
            window.show()
            window._show_page(2)
            for index in range(12):
                window._on_alert(
                    "Diamond Mythic!",
                    f"Diamond Droid (Mythic) spawned at the Sandcrawler {index}",
                    f"alert-{index}",
                )
            self.app.processEvents()

            rows = window._history_alert_rows[:3]
            self.assertTrue(all(row.height() >= 96 for row in rows))
            self.assertTrue(
                all(
                    rows[index].geometry().bottom() < rows[index + 1].geometry().top()
                    for index in range(len(rows) - 1)
                )
            )
            self.assertGreater(window.history_scroll.verticalScrollBar().maximum(), 0)
            window.close()
