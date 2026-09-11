"""PyQt desktop interface for configuring and running the read-only OCR monitor."""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import sys
import threading

from PyQt6.QtCore import QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .capture import MonitorInfo, ScreenCapture
from .config import AppConfig, CropRegion, load_config, runtime_directory, save_config
from .domain import ALERT_RULES
from .efficiency import OCR_MODE_ADAPTIVE, OCR_MODE_FULL, OCR_MODE_OBSERVE
from .monitor import MonitorWorker
from .notifications import (
    TelegramAlertDispatcher,
    TelegramDeliveryResult,
    clear_telegram_bot_token,
    find_recent_telegram_chat_id,
    get_telegram_bot_token,
    save_telegram_bot_token,
)
from .ocr import preprocess_for_ocr
from .rebirth_progress import (
    RebirthHud,
    RebirthProgress,
    RebirthRequirements,
    compact_amount_value,
    format_compact_amount,
    load_rebirth_progress,
    save_rebirth_progress,
)
from .rebirth_roadmap import DroidHoldAdvice, hold_advice, upcoming_requirements


_APP_STYLESHEET = """
QMainWindow, QWidget#appRoot {
    background: #171a1c;
    color: #edf2f3;
    font-family: "Segoe UI";
    font-size: 13px;
}
QFrame#sidebar {
    background: #101314;
    border-right: 1px solid #303638;
}
QLabel#brandMark { color: #67b8ff; font-size: 18px; font-weight: 700; }
QLabel#brandName { font-size: 17px; font-weight: 700; }
QToolButton#navButton {
    color: #aeb8ba;
    border: 0;
    border-radius: 6px;
    padding: 11px 12px;
    text-align: left;
    font-size: 14px;
}
QToolButton#navButton:hover { background: #22292b; color: #ffffff; }
QToolButton#navButton:checked { background: #1c5b89; color: #ffffff; }
QWidget#pageSurface { background: #171a1c; }
QLabel#pageTitle { font-size: 26px; font-weight: 700; }
QLabel#pageSubtitle, QLabel#mutedText { color: #9eaaad; }
QLabel#liveState { color: #6fe07d; font-size: 16px; font-weight: 700; }
QLabel#healthValue { color: #6fe07d; font-weight: 600; }
QFrame#healthBand, QFrame#watchingPanel, QFrame#historySurface {
    background: #22282a;
    border: 1px solid #394244;
    border-radius: 8px;
}
QLabel#sectionTitle { font-size: 17px; font-weight: 700; }
QLabel#statusTitle { font-size: 16px; font-weight: 700; }
QFrame#alertRow {
    background: #202628;
    border: 1px solid #354043;
    border-radius: 6px;
}
QLabel#alertTitle { font-size: 14px; font-weight: 700; }
QLabel#alertMeta { color: #8fb5c0; font-size: 11px; font-weight: 600; }
QLabel#alertTime { color: #aab4b6; font-size: 11px; }
QPushButton, QToolButton#compactAction {
    background: #2c3638;
    color: #edf2f3;
    border: 1px solid #455255;
    border-radius: 5px;
    padding: 7px 10px;
}
QPushButton:hover, QToolButton#compactAction:hover { background: #374548; }
QPushButton#primaryAction {
    background: #4c9f6a;
    border-color: #67bc83;
    color: #0f1711;
    font-weight: 700;
    padding: 9px 14px;
}
QPushButton#pauseAction {
    background: #c98247;
    border-color: #e4a260;
    color: #20150b;
    font-weight: 700;
}
QPushButton:disabled {
    color: #7f8a8c;
    background: #252b2d;
    border-color: #343c3e;
}
QGroupBox {
    color: #edf2f3;
    font-size: 15px;
    font-weight: 700;
    border: 1px solid #394244;
    border-radius: 8px;
    margin-top: 10px;
    padding: 14px 12px 10px 12px;
    background: #22282a;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
    background: #151a1b;
    color: #edf2f3;
    border: 1px solid #455255;
    border-radius: 5px;
    padding: 6px;
    selection-background-color: #2872a8;
}
QComboBox QAbstractItemView {
    background: #202628;
    color: #edf2f3;
    selection-background-color: #2872a8;
}
QCheckBox { spacing: 7px; color: #d8e0e2; }
QCheckBox::indicator { width: 16px; height: 16px; }
QCheckBox::indicator:unchecked {
    border: 1px solid #687578;
    background: #151a1b;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    border: 1px solid #75cc8c;
    background: #58ad70;
    border-radius: 3px;
}
QScrollArea { border: 0; background: transparent; }
QFrame#rebirthMetric, QFrame#rebirthRequirement {
    background: #202628;
    border: 1px solid #3c494c;
    border-radius: 6px;
}
QLabel#rebirthMetricLabel { color: #9eaaad; font-size: 11px; }
QLabel#rebirthMetricValue { color: #f3f6f5; font-size: 22px; font-weight: 700; }
QLabel#rebirthGoalTitle { color: #f3f6f5; font-size: 19px; font-weight: 700; }
QLabel#rebirthGoalDetail { color: #aebcbe; font-size: 12px; }
QLabel#rebirthRequirementTitle { color: #f3f6f5; font-size: 15px; font-weight: 700; }
QLabel#rebirthRequirementDetail { color: #aebcbe; font-size: 12px; }
QLabel#rebirthStatusGood { color: #74d58a; font-size: 12px; font-weight: 700; }
QLabel#rebirthStatusMissing { color: #ef8c78; font-size: 12px; font-weight: 700; }
QProgressBar#rebirthCreditProgress {
    border: 1px solid #475558;
    border-radius: 5px;
    background: #121718;
    min-height: 12px;
    max-height: 12px;
}
QProgressBar#rebirthCreditProgress::chunk { background: #62c78b; border-radius: 4px; }
QFrame#rebirthPlannerInsight, QFrame#rebirthRoadmapRow {
    background: #202628;
    border: 1px solid #3c494c;
    border-radius: 6px;
}
QLabel#rebirthPlannerLabel { color: #9eaaad; font-size: 11px; font-weight: 700; }
QLabel#rebirthPlannerValue { color: #e7edef; font-size: 13px; font-weight: 600; }
QLabel#rebirthRoadmapRank { color: #73bdf4; font-size: 15px; font-weight: 700; }
QLabel#rebirthRoadmapDroids { color: #dbe4e6; font-size: 13px; }
QWidget#rulesContent { background: #22282a; }
QScrollBar:vertical { background: #151a1b; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #556164; border-radius: 5px; min-height: 30px; }
QPlainTextEdit#activityLog { font-family: "Segoe UI"; font-size: 12px; }
"""


def _set_window_topmost(window_handle: int, enabled: bool) -> bool:
    """Use the native Windows API so toggling topmost never recreates the Qt window."""

    if sys.platform != "win32":
        return True
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetWindowPos.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    user32.SetWindowPos.restype = ctypes.c_bool
    flags = 0x0001 | 0x0002 | 0x0010  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
    insert_after = -1 if enabled else -2  # HWND_TOPMOST | HWND_NOTOPMOST
    return bool(
        user32.SetWindowPos(
            ctypes.c_void_p(window_handle),
            ctypes.c_void_p(insert_after),
            0,
            0,
            0,
            0,
            flags,
        )
    )


class DroidMonitorWindow(QMainWindow):
    """The main application window and owner of the capture worker."""

    background_log = pyqtSignal(str)
    telegram_chat_found = pyqtSignal(str)

    def __init__(self, config_path: Path | None = None) -> None:
        super().__init__()
        self._config_path = config_path
        self._config = load_config(config_path)
        self._worker: MonitorWorker | None = None
        self._rule_checkboxes: dict[str, QCheckBox] = {}
        self._monitors: list[MonitorInfo] = []
        self._health_values: dict[str, QLabel] = {}
        self._live_alert_rows: list[QWidget] = []
        self._history_alert_rows: list[QWidget] = []
        self._alert_rows_by_key: dict[str, list[QFrame]] = {}
        self._telegram_alert_token = ""
        self._telegram_dispatcher = TelegramAlertDispatcher(self._on_telegram_delivery)
        self._worker_has_error = False
        self._rebirth_progress = load_rebirth_progress()
        self._rebirth_syncing = False

        self.setWindowTitle("FortniteVision - Droid Monitor")
        self.setMinimumSize(1_030, 720)
        self.resize(1_260, 820)
        self._build_ui()
        self.background_log.connect(self._append_log)
        self.telegram_chat_found.connect(self._set_detected_telegram_chat)
        self._create_tray_icon()
        self._refresh_monitors()
        self._set_controls_from_config(self._config)
        self._render_rebirth_progress()
        self._append_log("Ready to monitor. Review Setup when you want to calibrate a capture.")

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        self.setStyleSheet(_APP_STYLESHEET)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_navigation())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_live_page())
        self.pages.addWidget(self._build_rebirth_page())
        self.pages.addWidget(self._build_alerts_page())
        self.pages.addWidget(self._build_setup_page())
        layout.addWidget(self.pages, stretch=1)

    def _build_navigation(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(188)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 22, 14, 16)
        layout.setSpacing(8)

        brand_mark = QLabel("[ FV ]")
        brand_mark.setObjectName("brandMark")
        brand_name = QLabel("FortniteVision")
        brand_name.setObjectName("brandName")
        layout.addWidget(brand_mark)
        layout.addWidget(brand_name)
        layout.addSpacing(26)

        self._navigation = QButtonGroup(self)
        for index, label, icon in (
            (0, "Live", QStyle.StandardPixmap.SP_ComputerIcon),
            (1, "Rebirth", QStyle.StandardPixmap.SP_BrowserReload),
            (2, "Alerts", QStyle.StandardPixmap.SP_MessageBoxInformation),
            (3, "Setup", QStyle.StandardPixmap.SP_FileDialogDetailedView),
        ):
            button = QToolButton()
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setIcon(self.style().standardIcon(icon))
            button.setText(label)
            button.clicked.connect(lambda _checked=False, page=index: self._show_page(page))
            self._navigation.addButton(button, index)
            layout.addWidget(button)
            if index == 0:
                button.setChecked(True)

        layout.addStretch()
        version = QLabel("Droid monitor")
        version.setObjectName("mutedText")
        layout.addWidget(version)
        return sidebar

    def _show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        button = self._navigation.button(index)
        if button:
            button.setChecked(True)

    def _build_live_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("pageSurface")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(18)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Live Monitor")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Watching your game and surfacing the moments that matter.")
        subtitle.setObjectName("pageSubtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addLayout(title_block)
        header.addStretch()

        status_block = QVBoxLayout()
        status_block.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.status = QLabel("Paused")
        self.status.setObjectName("liveState")
        self.last_scan_label = QLabel("Not scanning")
        self.last_scan_label.setObjectName("mutedText")
        status_block.addWidget(self.status, alignment=Qt.AlignmentFlag.AlignRight)
        status_block.addWidget(self.last_scan_label, alignment=Qt.AlignmentFlag.AlignRight)
        header.addLayout(status_block)

        self.start_button = QPushButton("Start monitoring")
        self.start_button.setObjectName("primaryAction")
        self.start_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.start_button.clicked.connect(self._start_monitoring)
        self.stop_button = QPushButton("Pause")
        self.stop_button.setObjectName("pauseAction")
        self.stop_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.stop_button.setEnabled(False)
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self._stop_monitoring)
        header.addWidget(self.start_button)
        header.addWidget(self.stop_button)
        layout.addLayout(header)

        health = QFrame()
        health.setObjectName("healthBand")
        health_layout = QHBoxLayout(health)
        health_layout.setContentsMargins(16, 14, 16, 14)
        health_layout.setSpacing(22)

        self.live_preview = QLabel("Capture preview")
        self.live_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.live_preview.setFixedSize(156, 92)
        self.live_preview.setStyleSheet(
            "background: #111617; border: 1px solid #455255; border-radius: 5px; color: #95a1a3;"
        )
        health_layout.addWidget(self.live_preview)

        health_title = QVBoxLayout()
        heading = QLabel("All monitors ready")
        heading.setObjectName("statusTitle")
        detail = QLabel("Live health updates appear while monitoring.")
        detail.setObjectName("mutedText")
        health_title.addWidget(heading)
        health_title.addWidget(detail)
        health_layout.addLayout(health_title)
        health_layout.addStretch()

        for key, label in (
            ("ocr", "OCR feed"),
            ("jawa", "Jawa watch"),
            ("telegram", "Telegram"),
            ("qa", "QA captures"),
        ):
            health_layout.addWidget(self._health_item(key, label))
        layout.addWidget(health)

        body = QHBoxLayout()
        body.setSpacing(20)
        feed = QWidget()
        feed_layout = QVBoxLayout(feed)
        feed_layout.setContentsMargins(0, 0, 0, 0)
        feed_layout.setSpacing(16)

        feed_layout.addLayout(self._section_header("Recent Alerts"))
        self.live_alerts_content = QWidget()
        self.live_alerts_layout = QVBoxLayout(self.live_alerts_content)
        self.live_alerts_layout.setContentsMargins(0, 0, 0, 0)
        self.live_alerts_layout.setSpacing(7)
        self.live_alerts_empty = QLabel("No alerts yet this session.")
        self.live_alerts_empty.setObjectName("mutedText")
        self.live_alerts_layout.addWidget(self.live_alerts_empty)
        feed_layout.addWidget(self.live_alerts_content)

        activity_header = self._section_header("Activity")
        open_captures = QToolButton()
        open_captures.setObjectName("compactAction")
        open_captures.setText("Open QA captures")
        open_captures.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        open_captures.clicked.connect(self._open_qa_captures)
        activity_header.addWidget(open_captures)
        feed_layout.addLayout(activity_header)
        self.log = QPlainTextEdit()
        self.log.setObjectName("activityLog")
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(220)
        self.log.setPlaceholderText("Monitoring activity will appear here.")
        feed_layout.addWidget(self.log, stretch=1)
        body.addWidget(feed, stretch=3)
        body.addWidget(self._build_watching_panel(), stretch=1)
        layout.addLayout(body, stretch=1)
        return page

    def _health_item(self, key: str, label: str) -> QWidget:
        item = QWidget()
        layout = QVBoxLayout(item)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        name = QLabel(label)
        value = QLabel("Ready")
        value.setObjectName("healthValue")
        self._health_values[key] = value
        layout.addWidget(name)
        layout.addWidget(value)
        return item

    def _set_health_value(self, key: str, value: str, healthy: bool = True) -> None:
        label = self._health_values[key]
        label.setText(value)
        label.setStyleSheet("color: #6fe07d;" if healthy else "color: #e7b05b;")

    def _section_header(self, title: str) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        layout.addStretch()
        return layout

    def _build_watching_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("watchingPanel")
        panel.setMinimumWidth(280)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(10)

        header = self._section_header("Watching for")
        self.rule_count_label = QLabel("0 enabled")
        self.rule_count_label.setObjectName("mutedText")
        header.addWidget(self.rule_count_label)
        layout.addLayout(header)

        rules_actions = QHBoxLayout()
        select_all = QPushButton("All")
        select_all.clicked.connect(lambda: self._set_all_rules(True))
        select_none = QPushButton("None")
        select_none.clicked.connect(lambda: self._set_all_rules(False))
        rules_actions.addWidget(select_all)
        rules_actions.addWidget(select_none)
        rules_actions.addStretch()
        layout.addLayout(rules_actions)

        self.rule_scroll = QScrollArea()
        self.rule_scroll.setWidgetResizable(True)
        self.rule_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.rule_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rule_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.rule_scroll.setMinimumHeight(265)
        rule_content = QWidget()
        rule_content.setObjectName("rulesContent")
        rule_content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        rules_layout = QVBoxLayout(rule_content)
        rules_layout.setContentsMargins(0, 0, 0, 0)
        rules_layout.setSpacing(6)
        for rule in ALERT_RULES:
            checkbox = QCheckBox(f"{rule.emoji}  {rule.label}")
            checkbox.toggled.connect(self._controls_changed)
            self._rule_checkboxes[rule.id] = checkbox
            rules_layout.addWidget(checkbox)
        self.rule_scroll.setWidget(rule_content)
        self.rule_scroll.viewport().setStyleSheet("background: #22282a;")
        layout.addWidget(self.rule_scroll, stretch=1)

        self.jawa_watch_summary = QLabel("Jawa Droid announcement: ready")
        self.jawa_watch_summary.setWordWrap(True)
        self.jawa_watch_summary.setObjectName("mutedText")
        layout.addWidget(self.jawa_watch_summary)
        tune_jawa = QToolButton()
        tune_jawa.setObjectName("compactAction")
        tune_jawa.setText("Tune Jawa watch")
        tune_jawa.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        tune_jawa.clicked.connect(lambda: self._show_page(3))
        layout.addWidget(tune_jawa, alignment=Qt.AlignmentFlag.AlignLeft)
        return panel

    def _build_rebirth_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("pageSurface")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page = QWidget()
        page.setObjectName("pageSurface")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(18)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Rebirth Progress")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Live resources refresh every 15 seconds while monitoring.")
        subtitle.setObjectName("pageSubtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addLayout(title_block)
        header.addStretch()
        self.rebirth_sync_button = QPushButton("Sync open Rebirth screen")
        self.rebirth_sync_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.rebirth_sync_button.clicked.connect(self._sync_rebirth_requirements)
        header.addWidget(self.rebirth_sync_button)
        layout.addLayout(header)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)
        self._rebirth_metric_values: dict[str, QLabel] = {}
        for key, label_text in (
            ("credits", "Credits"),
            ("chips", "Upgrade chips"),
            ("nova", "Nova crystals"),
            ("level", "Rebirth level"),
        ):
            metric = QFrame()
            metric.setObjectName("rebirthMetric")
            metric_layout = QVBoxLayout(metric)
            metric_layout.setContentsMargins(14, 12, 14, 12)
            metric_layout.setSpacing(4)
            metric_label = QLabel(label_text)
            metric_label.setObjectName("rebirthMetricLabel")
            metric_value = QLabel("--")
            metric_value.setObjectName("rebirthMetricValue")
            metric_layout.addWidget(metric_label)
            metric_layout.addWidget(metric_value)
            metrics.addWidget(metric, stretch=1)
            self._rebirth_metric_values[key] = metric_value
        layout.addLayout(metrics)
        self.rebirth_hud_status = QLabel("HUD: awaiting first read")
        self.rebirth_hud_status.setObjectName("mutedText")
        layout.addWidget(self.rebirth_hud_status)

        goal_header = self._section_header("Next Rebirth")
        self.rebirth_path_label = QLabel("Open the Rebirth screen to sync requirements")
        self.rebirth_path_label.setObjectName("mutedText")
        goal_header.addWidget(self.rebirth_path_label)
        layout.addLayout(goal_header)

        goal = QWidget()
        goal_layout = QVBoxLayout(goal)
        goal_layout.setContentsMargins(0, 0, 0, 0)
        goal_layout.setSpacing(6)
        self.rebirth_goal_title = QLabel("Requirements awaiting sync")
        self.rebirth_goal_title.setObjectName("rebirthGoalTitle")
        self.rebirth_goal_detail = QLabel(
            "Open Rebirth in-game, then use Sync open Rebirth screen."
        )
        self.rebirth_goal_detail.setObjectName("rebirthGoalDetail")
        self.rebirth_credit_progress = QProgressBar()
        self.rebirth_credit_progress.setObjectName("rebirthCreditProgress")
        self.rebirth_credit_progress.setRange(0, 1000)
        self.rebirth_credit_progress.setValue(0)
        self.rebirth_credit_progress.setTextVisible(False)
        goal_layout.addWidget(self.rebirth_goal_title)
        goal_layout.addWidget(self.rebirth_goal_detail)
        goal_layout.addWidget(self.rebirth_credit_progress)
        layout.addWidget(goal)

        planner_header = self._section_header("Roller Planner")
        self.rebirth_planner_path_label = QLabel("Sync a Rebirth screen to plan ahead")
        self.rebirth_planner_path_label.setObjectName("mutedText")
        planner_header.addWidget(self.rebirth_planner_path_label)
        layout.addLayout(planner_header)

        planner_insights = QHBoxLayout()
        planner_insights.setSpacing(10)
        self.rebirth_hold_insight, self.rebirth_hold_insight_value = self._build_rebirth_planner_insight(
            "Hold / upgrade"
        )
        self.rebirth_sell_insight, self.rebirth_sell_insight_value = self._build_rebirth_planner_insight(
            "After this Rebirth"
        )
        planner_insights.addWidget(self.rebirth_hold_insight, stretch=1)
        planner_insights.addWidget(self.rebirth_sell_insight, stretch=1)
        layout.addLayout(planner_insights)

        roadmap_header = self._section_header("Coming Up")
        self.rebirth_roadmap_summary = QLabel("Future roller targets will appear here.")
        self.rebirth_roadmap_summary.setObjectName("mutedText")
        roadmap_header.addWidget(self.rebirth_roadmap_summary)
        layout.addLayout(roadmap_header)
        self._rebirth_roadmap_rows: list[tuple[QFrame, QLabel, QLabel]] = []
        roadmap_layout = QVBoxLayout()
        roadmap_layout.setSpacing(7)
        for _ in range(4):
            row = QFrame()
            row.setObjectName("rebirthRoadmapRow")
            row.setMinimumHeight(54)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(13, 8, 13, 8)
            row_layout.setSpacing(12)
            rank = QLabel("--")
            rank.setObjectName("rebirthRoadmapRank")
            rank.setMinimumWidth(80)
            details = QLabel("Awaiting Rebirth sync")
            details.setObjectName("rebirthRoadmapDroids")
            details.setWordWrap(True)
            row_layout.addWidget(rank)
            row_layout.addWidget(details, stretch=1)
            roadmap_layout.addWidget(row)
            self._rebirth_roadmap_rows.append((row, rank, details))
        layout.addLayout(roadmap_layout)

        requirements_header = self._section_header("Required Droids")
        self.rebirth_droid_summary = QLabel("No current Rebirth requirements have been synced.")
        self.rebirth_droid_summary.setObjectName("mutedText")
        requirements_header.addWidget(self.rebirth_droid_summary)
        layout.addLayout(requirements_header)

        requirements_layout = QHBoxLayout()
        requirements_layout.setSpacing(10)
        self._rebirth_requirement_rows: list[tuple[QFrame, QLabel, QLabel, QLabel]] = []
        for _ in range(3):
            requirement = QFrame()
            requirement.setObjectName("rebirthRequirement")
            requirement_layout = QVBoxLayout(requirement)
            requirement_layout.setContentsMargins(14, 12, 14, 12)
            requirement_layout.setSpacing(3)
            status = QLabel("Awaiting sync")
            status.setObjectName("rebirthStatusMissing")
            name = QLabel("Droid requirement")
            name.setObjectName("rebirthRequirementTitle")
            variant = QLabel("Variant unknown")
            variant.setObjectName("rebirthRequirementDetail")
            requirement_layout.addWidget(status)
            requirement_layout.addWidget(name)
            requirement_layout.addWidget(variant)
            requirements_layout.addWidget(requirement, stretch=1)
            self._rebirth_requirement_rows.append((requirement, status, name, variant))
        layout.addLayout(requirements_layout)

        self.rebirth_sync_status = QLabel("HUD data is retained locally between sessions.")
        self.rebirth_sync_status.setObjectName("mutedText")
        layout.addWidget(self.rebirth_sync_status)
        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _build_rebirth_planner_insight(self, label_text: str) -> tuple[QFrame, QLabel]:
        insight = QFrame()
        insight.setObjectName("rebirthPlannerInsight")
        insight_layout = QVBoxLayout(insight)
        insight_layout.setContentsMargins(14, 11, 14, 11)
        insight_layout.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("rebirthPlannerLabel")
        value = QLabel("Awaiting Rebirth sync")
        value.setObjectName("rebirthPlannerValue")
        value.setWordWrap(True)
        insight_layout.addWidget(label)
        insight_layout.addWidget(value)
        return insight, value

    def _build_alerts_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("pageSurface")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(18)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Alerts & Evidence")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Review this session's detections and the raw crop behind each one.")
        subtitle.setObjectName("pageSubtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addLayout(title_block)
        header.addStretch()
        open_captures = QPushButton("Open QA captures")
        open_captures.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        open_captures.clicked.connect(self._open_qa_captures)
        header.addWidget(open_captures)
        layout.addLayout(header)

        history = QFrame()
        history.setObjectName("historySurface")
        history_layout = QVBoxLayout(history)
        history_layout.setContentsMargins(18, 18, 18, 18)
        history_layout.setSpacing(0)
        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.history_alerts_content = QWidget()
        self.history_alerts_content.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum,
        )
        self.history_alerts_layout = QVBoxLayout(self.history_alerts_content)
        self.history_alerts_layout.setContentsMargins(0, 0, 0, 0)
        self.history_alerts_layout.setSpacing(8)
        self.history_alerts_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.history_alerts_empty = QLabel("New alerts will appear here with their QA capture.")
        self.history_alerts_empty.setObjectName("mutedText")
        self.history_alerts_layout.addWidget(self.history_alerts_empty)
        self.history_alerts_layout.addStretch()
        self.history_scroll.setWidget(self.history_alerts_content)
        history_layout.addWidget(self.history_scroll, stretch=1)
        layout.addWidget(history, stretch=1)
        return page

    def _build_setup_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("pageSurface")
        canvas = QWidget()
        canvas.setObjectName("pageSurface")
        layout = QVBoxLayout(canvas)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(16)

        title = QLabel("Setup")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Calibration and notification preferences.")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        capture_group = QGroupBox("Capture area")
        capture_form = QFormLayout(capture_group)
        self.monitor_combo = QComboBox()
        self.monitor_combo.currentIndexChanged.connect(self._controls_changed)
        capture_form.addRow("Monitor", self.monitor_combo)

        crop_row = QHBoxLayout()
        self.crop_x = self._pixel_spinbox()
        self.crop_y = self._pixel_spinbox()
        self.crop_width = self._pixel_spinbox(minimum=1)
        self.crop_height = self._pixel_spinbox(minimum=1)
        for label, control in (("X", self.crop_x), ("Y", self.crop_y), ("W", self.crop_width), ("H", self.crop_height)):
            crop_row.addWidget(QLabel(label))
            crop_row.addWidget(control)
        capture_form.addRow("Crop (pixels)", crop_row)

        self.interval = QDoubleSpinBox()
        self.interval.setRange(0.25, 60.0)
        self.interval.setSingleStep(0.25)
        self.interval.setSuffix(" seconds")
        capture_form.addRow("Scan every", self.interval)

        self.preview_button = QPushButton("Save diagnostic preview")
        self.preview_button.clicked.connect(self._save_diagnostic_preview)
        capture_form.addRow("", self.preview_button)
        layout.addWidget(capture_group)

        self.preview = QLabel("No preview captured yet")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(180)
        self.preview.setStyleSheet(
            "background: #111617; border: 1px solid #455255; border-radius: 6px; color: #95a1a3;"
        )
        layout.addWidget(self.preview)

        jawa_group = QGroupBox("Jawa Droid announcement")
        jawa_form = QFormLayout(jawa_group)
        self.jawa_enabled = QCheckBox("Monitor recycle toast")
        self.jawa_enabled.toggled.connect(self._controls_changed)
        jawa_form.addRow("Jawa monitor", self.jawa_enabled)

        jawa_crop_row = QHBoxLayout()
        self.jawa_crop_x = self._pixel_spinbox()
        self.jawa_crop_y = self._pixel_spinbox()
        self.jawa_crop_width = self._pixel_spinbox(minimum=1)
        self.jawa_crop_height = self._pixel_spinbox(minimum=1)
        for label, control in (
            ("X", self.jawa_crop_x),
            ("Y", self.jawa_crop_y),
            ("W", self.jawa_crop_width),
            ("H", self.jawa_crop_height),
        ):
            control.valueChanged.connect(self._controls_changed)
            jawa_crop_row.addWidget(QLabel(label))
            jawa_crop_row.addWidget(control)
        jawa_form.addRow("Toast crop (pixels)", jawa_crop_row)

        self.jawa_match_threshold = QDoubleSpinBox()
        self.jawa_match_threshold.setRange(0.4, 0.95)
        self.jawa_match_threshold.setDecimals(2)
        self.jawa_match_threshold.setSingleStep(0.05)
        self.jawa_match_threshold.setSuffix(" match")
        self.jawa_match_threshold.valueChanged.connect(self._controls_changed)
        jawa_form.addRow("Recycle threshold", self.jawa_match_threshold)

        self.jawa_preview_button = QPushButton("Save Jawa diagnostic preview")
        self.jawa_preview_button.clicked.connect(self._save_jawa_diagnostic_preview)
        jawa_form.addRow("", self.jawa_preview_button)
        layout.addWidget(jawa_group)

        rebirth_group = QGroupBox("Ready for Rebirth")
        rebirth_form = QFormLayout(rebirth_group)
        self.rebirth_ready_enabled = QCheckBox("Monitor the bottom-center ready badge")
        self.rebirth_ready_enabled.toggled.connect(self._controls_changed)
        rebirth_form.addRow("Rebirth monitor", self.rebirth_ready_enabled)

        rebirth_crop_row = QHBoxLayout()
        self.rebirth_ready_crop_x = self._pixel_spinbox()
        self.rebirth_ready_crop_y = self._pixel_spinbox()
        self.rebirth_ready_crop_width = self._pixel_spinbox(minimum=1)
        self.rebirth_ready_crop_height = self._pixel_spinbox(minimum=1)
        for label, control in (
            ("X", self.rebirth_ready_crop_x),
            ("Y", self.rebirth_ready_crop_y),
            ("W", self.rebirth_ready_crop_width),
            ("H", self.rebirth_ready_crop_height),
        ):
            control.valueChanged.connect(self._controls_changed)
            rebirth_crop_row.addWidget(QLabel(label))
            rebirth_crop_row.addWidget(control)
        rebirth_form.addRow("Ready badge crop (pixels)", rebirth_crop_row)

        self.rebirth_ready_match_threshold = QDoubleSpinBox()
        self.rebirth_ready_match_threshold.setRange(0.4, 0.95)
        self.rebirth_ready_match_threshold.setDecimals(2)
        self.rebirth_ready_match_threshold.setSingleStep(0.05)
        self.rebirth_ready_match_threshold.setSuffix(" match")
        self.rebirth_ready_match_threshold.valueChanged.connect(self._controls_changed)
        rebirth_form.addRow("Ready threshold", self.rebirth_ready_match_threshold)

        self.rebirth_preview_button = QPushButton("Save Rebirth diagnostic preview")
        self.rebirth_preview_button.clicked.connect(self._save_rebirth_diagnostic_preview)
        rebirth_form.addRow("", self.rebirth_preview_button)
        layout.addWidget(rebirth_group)

        preferences_group = QGroupBox("Monitoring preferences")
        preferences_layout = QVBoxLayout(preferences_group)
        self.test_mode = QCheckBox("Test mode: log every recognized item")
        self.test_mode.setToolTip(
            "Logs recognized material and rarity calls, including items not selected for alerts."
        )
        self.test_mode.toggled.connect(self._controls_changed)
        preferences_layout.addWidget(self.test_mode)
        self.rebirth_progress_enabled = QCheckBox("Track Rebirth resources from HUD")
        self.rebirth_progress_enabled.setToolTip(
            "Reads the lower-left HUD every 15 seconds while monitoring. "
            "Rebirth requirements are only read when you sync the open Rebirth screen."
        )
        self.rebirth_progress_enabled.toggled.connect(self._controls_changed)
        preferences_layout.addWidget(self.rebirth_progress_enabled)
        self.spawn_ocr_mode = QComboBox()
        self.spawn_ocr_mode.addItem("Observe + Shadow Adaptive (recommended)", OCR_MODE_OBSERVE)
        self.spawn_ocr_mode.addItem("Adaptive: reduce OCR during quiet feeds", OCR_MODE_ADAPTIVE)
        self.spawn_ocr_mode.addItem("Full OCR every scan", OCR_MODE_FULL)
        self.spawn_ocr_mode.setToolTip(
            "Observe keeps full OCR active and compares its findings against a simulated "
            "Adaptive detector. Adaptive retains a full safety OCR scan at least every six seconds."
        )
        self.spawn_ocr_mode.currentIndexChanged.connect(self._controls_changed)
        preferences_layout.addWidget(QLabel("Droid feed CPU"))
        preferences_layout.addWidget(self.spawn_ocr_mode)
        self.always_on_top = QCheckBox("Always on top")
        self.always_on_top.setToolTip("Keep FortniteVision above other application windows.")
        self.always_on_top.toggled.connect(self._apply_always_on_top)
        self.always_on_top.toggled.connect(self._controls_changed)
        preferences_layout.addWidget(self.always_on_top)
        layout.addWidget(preferences_group)

        delivery_group = QGroupBox("Telegram notifications")
        delivery_form = QFormLayout(delivery_group)
        self.telegram_enabled = QCheckBox("Enable Telegram alerts")
        self.telegram_enabled.toggled.connect(self._controls_changed)
        delivery_form.addRow("Telegram", self.telegram_enabled)

        self.telegram_chat_id = QLineEdit()
        self.telegram_chat_id.setPlaceholderText("Chat ID or @channel username")
        self.telegram_chat_id.setToolTip(
            "For private messages, send the bot /start, then use Find recent chat."
        )
        self.telegram_chat_id.textChanged.connect(self._controls_changed)
        delivery_form.addRow("Telegram chat", self.telegram_chat_id)

        self.telegram_bot_token = QLineEdit()
        self.telegram_bot_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.telegram_bot_token.setPlaceholderText("Stored in Windows Credential Manager after use")
        delivery_form.addRow("Bot token", self.telegram_bot_token)

        telegram_actions = QHBoxLayout()
        self.find_telegram_chat_button = QPushButton("Find recent chat")
        self.find_telegram_chat_button.clicked.connect(self._find_telegram_chat)
        self.test_telegram_button = QPushButton("Send Telegram test")
        self.test_telegram_button.clicked.connect(self._test_telegram)
        self.clear_telegram_token_button = QPushButton("Clear stored token")
        self.clear_telegram_token_button.clicked.connect(self._clear_telegram_token)
        telegram_actions.addWidget(self.find_telegram_chat_button)
        telegram_actions.addWidget(self.test_telegram_button)
        telegram_actions.addWidget(self.clear_telegram_token_button)
        delivery_form.addRow("", telegram_actions)
        layout.addWidget(delivery_group)

        layout.addStretch()
        scroll.setWidget(canvas)
        return scroll

    @staticmethod
    def _pixel_spinbox(minimum: int = 0) -> QSpinBox:
        control = QSpinBox()
        control.setRange(minimum, 20_000)
        control.setSingleStep(5)
        return control

    def _create_tray_icon(self) -> None:
        self._tray = QSystemTrayIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), self
        )
        self._tray.setToolTip("FortniteVision Droid Monitor")
        self._tray.show()

    def _refresh_monitors(self) -> None:
        try:
            with ScreenCapture() as capture:
                self._monitors = capture.monitors()
        except Exception as exc:
            self._monitors = []
            self._append_log(f"Could not list monitors: {exc}")

        self.monitor_combo.blockSignals(True)
        self.monitor_combo.clear()
        for monitor in self._monitors:
            self.monitor_combo.addItem(monitor.label, monitor.index)
        self.monitor_combo.blockSignals(False)

    def _set_controls_from_config(self, config: AppConfig) -> None:
        selection = self.monitor_combo.findData(config.monitor_index)
        self.monitor_combo.setCurrentIndex(selection if selection >= 0 else 0)
        self.crop_x.setValue(config.crop.x)
        self.crop_y.setValue(config.crop.y)
        self.crop_width.setValue(config.crop.width)
        self.crop_height.setValue(config.crop.height)
        self.interval.setValue(config.scan_interval_seconds)
        efficiency_selection = self.spawn_ocr_mode.findData(config.spawn_ocr_mode)
        self.spawn_ocr_mode.setCurrentIndex(efficiency_selection if efficiency_selection >= 0 else 0)
        self.test_mode.setChecked(config.test_mode)
        self.rebirth_progress_enabled.setChecked(config.rebirth_progress_enabled)
        self.always_on_top.setChecked(config.always_on_top)
        self.jawa_enabled.setChecked(config.jawa_enabled)
        self.jawa_crop_x.setValue(config.jawa_crop.x)
        self.jawa_crop_y.setValue(config.jawa_crop.y)
        self.jawa_crop_width.setValue(config.jawa_crop.width)
        self.jawa_crop_height.setValue(config.jawa_crop.height)
        self.jawa_match_threshold.setValue(config.jawa_match_threshold)
        self.rebirth_ready_enabled.setChecked(config.rebirth_ready_enabled)
        self.rebirth_ready_crop_x.setValue(config.rebirth_ready_crop.x)
        self.rebirth_ready_crop_y.setValue(config.rebirth_ready_crop.y)
        self.rebirth_ready_crop_width.setValue(config.rebirth_ready_crop.width)
        self.rebirth_ready_crop_height.setValue(config.rebirth_ready_crop.height)
        self.rebirth_ready_match_threshold.setValue(config.rebirth_ready_match_threshold)
        self.telegram_enabled.setChecked(config.telegram_enabled)
        self.telegram_chat_id.setText(config.telegram_chat_id)
        for rule_id, checkbox in self._rule_checkboxes.items():
            checkbox.setChecked(rule_id in config.enabled_rule_ids)
        self._refresh_health_summary()

    def _config_from_controls(self) -> AppConfig:
        monitor_index = self.monitor_combo.currentData()
        if monitor_index is None:
            raise ValueError("No monitor is available. Connect a display and retry.")
        config = AppConfig(
            monitor_index=int(monitor_index),
            crop=CropRegion(
                x=self.crop_x.value(),
                y=self.crop_y.value(),
                width=self.crop_width.value(),
                height=self.crop_height.value(),
            ),
            scan_interval_seconds=self.interval.value(),
            spawn_ocr_mode=str(self.spawn_ocr_mode.currentData()),
            alert_cooldown_seconds=self._config.alert_cooldown_seconds,
            test_mode=self.test_mode.isChecked(),
            always_on_top=self.always_on_top.isChecked(),
            jawa_enabled=self.jawa_enabled.isChecked(),
            jawa_crop=CropRegion(
                x=self.jawa_crop_x.value(),
                y=self.jawa_crop_y.value(),
                width=self.jawa_crop_width.value(),
                height=self.jawa_crop_height.value(),
            ),
            jawa_match_threshold=self.jawa_match_threshold.value(),
            rebirth_ready_enabled=self.rebirth_ready_enabled.isChecked(),
            rebirth_ready_crop=CropRegion(
                x=self.rebirth_ready_crop_x.value(),
                y=self.rebirth_ready_crop_y.value(),
                width=self.rebirth_ready_crop_width.value(),
                height=self.rebirth_ready_crop_height.value(),
            ),
            rebirth_ready_match_threshold=self.rebirth_ready_match_threshold.value(),
            rebirth_progress_enabled=self.rebirth_progress_enabled.isChecked(),
            rebirth_hud_crop=self._config.rebirth_hud_crop,
            telegram_enabled=self.telegram_enabled.isChecked(),
            telegram_chat_id=self.telegram_chat_id.text().strip(),
            enabled_rule_ids=frozenset(
                rule_id for rule_id, checkbox in self._rule_checkboxes.items() if checkbox.isChecked()
            ),
        )
        config.validate()
        return config

    def _controls_changed(self, *_: object) -> None:
        self._refresh_health_summary()
        if self._worker and self._worker.isRunning():
            try:
                self._worker.update_config(self._config_from_controls())
            except ValueError:
                return

    def _set_all_rules(self, checked: bool) -> None:
        for checkbox in self._rule_checkboxes.values():
            checkbox.setChecked(checked)
        self._refresh_health_summary()

    def _refresh_health_summary(self) -> None:
        running = bool(self._worker and self._worker.isRunning())
        ocr_mode = str(self.spawn_ocr_mode.currentData())
        ocr_state = {
            OCR_MODE_OBSERVE: "Observe + shadow",
            OCR_MODE_ADAPTIVE: "Adaptive",
            OCR_MODE_FULL: "Full scan",
        }[ocr_mode]
        self._set_health_value("ocr", ocr_state if running else "Ready")
        jawa_enabled = self.jawa_enabled.isChecked()
        self._set_health_value("jawa", "Online" if jawa_enabled and running else ("Ready" if jawa_enabled else "Off"), jawa_enabled)
        rebirth_enabled = self.rebirth_ready_enabled.isChecked()
        rebirth_progress_enabled = self.rebirth_progress_enabled.isChecked()
        telegram_enabled = self.telegram_enabled.isChecked()
        self._set_health_value(
            "telegram",
            "Connected" if telegram_enabled else "Off",
            telegram_enabled,
        )
        self._set_health_value("qa", "On")
        enabled_count = sum(checkbox.isChecked() for checkbox in self._rule_checkboxes.values())
        self.rule_count_label.setText(f"{enabled_count} enabled")
        jawa_status = "monitoring" if jawa_enabled else "off"
        rebirth_status = "monitoring" if rebirth_enabled else "off"
        rebirth_progress_status = "monitoring" if rebirth_progress_enabled else "off"
        self.jawa_watch_summary.setText(
            f"Jawa Droid announcement: {jawa_status}\n"
            f"Ready for Rebirth: {rebirth_status}\n"
            f"Rebirth dashboard HUD: {rebirth_progress_status}"
        )

    def _apply_always_on_top(self, enabled: bool) -> None:
        if self.isVisible() and not _set_window_topmost(int(self.winId()), enabled):
            self._append_log("Could not change the Always on top setting.")

    def _save_diagnostic_preview(self) -> None:
        try:
            config = self._config_from_controls()
            with ScreenCapture() as capture:
                raw = capture.capture(config.monitor_index, config.crop)
            processed = preprocess_for_ocr(raw)
            directory = runtime_directory()
            directory.mkdir(parents=True, exist_ok=True)
            raw_path = directory / "crop_raw.png"
            processed_path = directory / "crop_processed.png"
            raw.save(raw_path)
            processed.save(processed_path)
            self._show_preview(QPixmap(str(processed_path)))
            self._append_log(f"Preview saved: {processed_path}")
        except Exception as exc:
            self._show_error("Could not capture preview", str(exc))

    def _save_jawa_diagnostic_preview(self) -> None:
        try:
            config = self._config_from_controls()
            with ScreenCapture() as capture:
                raw = capture.capture(config.monitor_index, config.jawa_crop)
            directory = runtime_directory()
            directory.mkdir(parents=True, exist_ok=True)
            preview_path = directory / "jawa_crop.png"
            raw.save(preview_path)
            self._show_preview(QPixmap(str(preview_path)))
            self._append_log(f"Jawa preview saved: {preview_path}")
        except Exception as exc:
            self._show_error("Could not capture Jawa preview", str(exc))

    def _save_rebirth_diagnostic_preview(self) -> None:
        try:
            config = self._config_from_controls()
            with ScreenCapture() as capture:
                raw = capture.capture(config.monitor_index, config.rebirth_ready_crop)
            directory = runtime_directory()
            directory.mkdir(parents=True, exist_ok=True)
            preview_path = directory / "rebirth_ready_crop.png"
            raw.save(preview_path)
            self._show_preview(QPixmap(str(preview_path)))
            self._append_log(f"Rebirth preview saved: {preview_path}")
        except Exception as exc:
            self._show_error("Could not capture Rebirth preview", str(exc))

    def _show_preview(self, pixmap: QPixmap) -> None:
        for preview in (self.preview, self.live_preview):
            preview.setPixmap(
                pixmap.scaled(
                    max(1, preview.width() - 12),
                    max(1, preview.height() - 12),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def _start_monitoring(self) -> None:
        try:
            self._store_telegram_token_if_entered()
            self._config = self._config_from_controls()
            if self._config.telegram_enabled:
                self._telegram_alert_token = get_telegram_bot_token()
            saved_path = save_config(self._config, self._config_path)
        except Exception as exc:
            self._show_error("Cannot start monitoring", str(exc))
            return

        self._worker_has_error = False
        self._worker = MonitorWorker(self._config)
        self._worker.status.connect(self._set_worker_status)
        self._worker.heartbeat.connect(self._on_worker_heartbeat)
        self._worker.event_found.connect(self._on_event)
        self._worker.alert_found.connect(self._on_alert)
        self._worker.evidence_ready.connect(self._on_alert_evidence_ready)
        self._worker.rebirth_hud_found.connect(self._on_rebirth_hud)
        self._worker.rebirth_requirements_found.connect(self._on_rebirth_requirements)
        self._worker.rebirth_requirements_failed.connect(self._on_rebirth_requirements_failed)
        self._worker.failed.connect(self._on_worker_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()
        self._set_monitor_presentation("Starting", running=True)
        self._append_log(f"Monitoring settings saved to {saved_path}")

    def _stop_monitoring(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self.stop_button.setEnabled(False)
            self._set_monitor_presentation("Pausing", running=True)

    def _set_worker_status(self, status: str) -> None:
        if status == "Monitoring active":
            self._set_monitor_presentation("Running", running=True)
        elif status.startswith("Loading"):
            self._set_monitor_presentation("Starting", running=True)
        elif status == "Monitoring stopped" and not self._worker_has_error:
            self._set_monitor_presentation("Paused", running=False)

    def _on_worker_heartbeat(self) -> None:
        self.last_scan_label.setText(f"Last scan {datetime.now().strftime('%I:%M:%S %p').lstrip('0')}")

    def _set_monitor_presentation(self, state: str, running: bool) -> None:
        self.status.setText(state)
        healthy = state in {"Running", "Starting"}
        self.status.setStyleSheet("color: #6fe07d;" if healthy else "color: #e7b05b;")
        if not running:
            self.last_scan_label.setText("Not scanning" if state == "Paused" else "Attention required")
        self.start_button.setVisible(not running)
        self.start_button.setEnabled(not running)
        self.stop_button.setVisible(running)
        self.stop_button.setEnabled(running and state != "Pausing")
        self._refresh_health_summary()

    def _on_event(self, event: str) -> None:
        self._append_log(event)

    def _sync_rebirth_requirements(self) -> None:
        if self._rebirth_syncing:
            return
        if not self._worker or not self._worker.isRunning():
            self.rebirth_sync_status.setText("Start monitoring, open Rebirth in-game, then sync it here.")
            return
        self._rebirth_syncing = True
        self.rebirth_sync_button.setEnabled(False)
        self.rebirth_sync_status.setText("Capturing the open Rebirth screen...")
        self.hide()
        QTimer.singleShot(350, self._request_rebirth_requirements_capture)

    def _request_rebirth_requirements_capture(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.request_rebirth_requirements_capture()
            return
        self._on_rebirth_requirements_failed("Monitoring stopped before the Rebirth screen could be read.")

    def _on_rebirth_hud(self, hud: object) -> None:
        if not isinstance(hud, RebirthHud):
            return
        self._rebirth_progress = replace(self._rebirth_progress, hud=hud)
        self._save_and_render_rebirth_progress()

    def _on_rebirth_requirements(self, requirements: object) -> None:
        if not isinstance(requirements, RebirthRequirements):
            self._on_rebirth_requirements_failed("Could not understand the open Rebirth screen.")
            return
        self._rebirth_syncing = False
        self.rebirth_sync_button.setEnabled(True)
        self._rebirth_progress = replace(self._rebirth_progress, requirements=requirements)
        self._save_and_render_rebirth_progress()
        self.rebirth_sync_status.setText(
            f"Requirements synced {self._format_rebirth_timestamp(requirements.updated_at)}."
        )
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _on_rebirth_requirements_failed(self, message: str) -> None:
        self._rebirth_syncing = False
        self.rebirth_sync_button.setEnabled(True)
        self.rebirth_sync_status.setText(f"Sync failed: {message}")
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _save_and_render_rebirth_progress(self) -> None:
        try:
            save_rebirth_progress(self._rebirth_progress)
        except OSError as exc:
            self._append_log(f"Could not save Rebirth progress: {exc}")
        self._render_rebirth_progress()

    def _render_rebirth_progress(self) -> None:
        hud = self._rebirth_progress.hud
        requirements = self._rebirth_progress.requirements
        self._rebirth_metric_values["credits"].setText(hud.credits or "--")
        self._rebirth_metric_values["chips"].setText(hud.upgrade_chips or "--")
        self._rebirth_metric_values["nova"].setText(hud.nova_crystals or "--")
        self._rebirth_metric_values["level"].setText(
            str(hud.rebirth_level) if hud.rebirth_level is not None else "--"
        )
        if hud.updated_at:
            self.rebirth_hud_status.setText(
                f"HUD updated {self._format_rebirth_timestamp(hud.updated_at)} | refreshing every 15 seconds"
            )
        else:
            self.rebirth_hud_status.setText("HUD: awaiting first read")

        if not requirements.droids:
            self.rebirth_path_label.setText("Open the Rebirth screen to sync requirements")
            self.rebirth_goal_title.setText("Requirements awaiting sync")
            self.rebirth_goal_detail.setText(
                "Open Rebirth in-game, then use Sync open Rebirth screen."
            )
            self.rebirth_credit_progress.setValue(0)
            self.rebirth_droid_summary.setText("No current Rebirth requirements have been synced.")
            self._render_rebirth_planner(None, None)
            for _frame, status, name, variant in self._rebirth_requirement_rows:
                self._set_rebirth_requirement_status(status, False, "Awaiting sync")
                name.setText("Droid requirement")
                variant.setText("Variant unknown")
            return

        path_text = str(requirements.path) if requirements.path is not None else "?"
        self.rebirth_path_label.setText(f"Path {path_text} / Cycle {path_text}")
        target = requirements.credit_requirement or "unknown credits"
        if requirements.target_rank is not None:
            self.rebirth_goal_title.setText(f"Rank {requirements.target_rank} requires {target}")
        else:
            self.rebirth_goal_title.setText(f"Next Rebirth requires {target}")

        current_credits = compact_amount_value(hud.credits)
        target_credits = compact_amount_value(requirements.credit_requirement)
        if current_credits is not None and target_credits is not None:
            ratio = min(current_credits / target_credits, 1.0)
            self.rebirth_credit_progress.setValue(round(ratio * 1000))
            if current_credits >= target_credits:
                self.rebirth_goal_detail.setText(
                    f"Credits ready: {hud.credits} of {requirements.credit_requirement}"
                )
            else:
                remaining = format_compact_amount(target_credits - current_credits)
                self.rebirth_goal_detail.setText(
                    f"Credits: {hud.credits} of {requirements.credit_requirement} | {remaining} remaining"
                )
        else:
            self.rebirth_credit_progress.setValue(0)
            self.rebirth_goal_detail.setText(f"Credits required: {requirements.credit_requirement}")

        ready_count = sum(requirement.owned for requirement in requirements.droids)
        self.rebirth_droid_summary.setText(
            f"{ready_count} of {len(requirements.droids)} required droids ready"
        )
        self._render_rebirth_planner(requirements.path, requirements.target_rank)
        for index, (_frame, status, name, variant) in enumerate(self._rebirth_requirement_rows):
            if index < len(requirements.droids):
                requirement = requirements.droids[index]
                self._set_rebirth_requirement_status(
                    status, requirement.owned, "Ready" if requirement.owned else "Needed"
                )
                name.setText(requirement.droid_name)
                variant.setText(requirement.variant)
            else:
                self._set_rebirth_requirement_status(status, False, "Not required")
                name.setText("Droid requirement")
                variant.setText("Variant unknown")

    def _render_rebirth_planner(self, path: int | None, rank: int | None) -> None:
        advice = hold_advice(path, rank)
        if not advice:
            self.rebirth_planner_path_label.setText("Sync a Rebirth screen to plan ahead")
            self.rebirth_hold_insight_value.setText("No current droid guidance yet.")
            self.rebirth_sell_insight_value.setText("No current droid guidance yet.")
            self.rebirth_roadmap_summary.setText("Future roller targets will appear here.")
            for row, rank_label, details in self._rebirth_roadmap_rows:
                row.setVisible(False)
                rank_label.setText("--")
                details.setText("Awaiting Rebirth sync")
            return

        self.rebirth_planner_path_label.setText(f"Path {path} | through Rank 30")
        holds = [item for item in advice if item.later_requirement is not None]
        sells = [item for item in advice if item.later_requirement is None]
        if holds:
            self.rebirth_hold_insight_value.setText(
                "\n".join(
                    self._format_rebirth_hold_advice(item) for item in holds
                )
            )
        else:
            self.rebirth_hold_insight_value.setText(
                f"No current droid repeats later in Path {path}."
            )
        if sells:
            self.rebirth_sell_insight_value.setText(
                "\n".join(
                    f"{item.droid.label}: no later Path {path} requirement"
                    for item in sells
                )
            )
        else:
            self.rebirth_sell_insight_value.setText(
                "All current droids return later in this Path."
            )

        upcoming = upcoming_requirements(path, rank)
        self.rebirth_roadmap_summary.setText(
            "Next roller targets after the current Rebirth"
            if upcoming
            else "This is the final tracked Rebirth in the current Path."
        )
        for index, (row, rank_label, details) in enumerate(self._rebirth_roadmap_rows):
            if index >= len(upcoming):
                row.setVisible(False)
                continue
            target = upcoming[index]
            rank_label.setText(f"R{target.rank} | {target.credits}")
            details.setText("   |   ".join(droid.label for droid in target.droids))
            row.setVisible(True)

    @staticmethod
    def _format_rebirth_hold_advice(advice: DroidHoldAdvice) -> str:
        if advice.later_requirement is None or advice.later_droid is None:
            return ""
        action = "Upgrade" if advice.needs_upgrade else "Store"
        return (
            f"{action} {advice.droid.name}: R{advice.later_requirement.rank} needs "
            f"{advice.later_droid.material} {advice.later_droid.rarity}"
        )

    @staticmethod
    def _format_rebirth_timestamp(value: str) -> str:
        try:
            return datetime.fromisoformat(value).strftime("%b %d at %I:%M %p").replace(" 0", " ")
        except ValueError:
            return value.replace("T", " ") if value else "not yet"

    @staticmethod
    def _set_rebirth_requirement_status(status: QLabel, ready: bool, text: str) -> None:
        status.setObjectName("rebirthStatusGood" if ready else "rebirthStatusMissing")
        status.setText(text)
        status.style().unpolish(status)
        status.style().polish(status)

    def _on_alert(self, alert_title: str, event: str, alert_key: str = "") -> None:
        self._append_log(f"ALERT - {alert_title} {event}")
        self._add_alert_row(
            self.live_alerts_layout,
            self._live_alert_rows,
            self.live_alerts_empty,
            alert_title,
            event,
            alert_key,
            limit=3,
        )
        self._add_alert_row(
            self.history_alerts_layout,
            self._history_alert_rows,
            self.history_alerts_empty,
            alert_title,
            event,
            alert_key,
            limit=40,
        )
        self._tray.showMessage(
            "Droid alert", f"{alert_title}\n{event}", QSystemTrayIcon.MessageIcon.Information, 10_000
        )
        if self.telegram_enabled.isChecked():
            self._queue_telegram_alert(self.telegram_chat_id.text().strip(), alert_title, event)

    def _add_alert_row(
        self,
        layout: QVBoxLayout,
        rows: list[QWidget],
        empty_label: QLabel,
        alert_title: str,
        event: str,
        alert_key: str,
        limit: int,
    ) -> None:
        empty_label.setVisible(False)
        row = QFrame()
        row.setObjectName("alertRow")
        row.setProperty("alert_key", alert_key)
        row.setMinimumHeight(96)
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 10, 12, 10)
        row_layout.setSpacing(10)

        thumbnail = QLabel("QA")
        thumbnail.setObjectName("alertThumbnail")
        thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumbnail.setFixedSize(58, 40)
        thumbnail.setStyleSheet("background: #151a1b; color: #9eaaad; border-radius: 4px;")
        row_layout.addWidget(thumbnail)

        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel(alert_title)
        title.setObjectName("alertTitle")
        source = self._alert_source_label(event)
        metadata = QLabel(f"{source} | QA capture pending")
        metadata.setObjectName("alertMeta")
        metadata.setProperty("alert_source", source)
        event_label = QLabel(event)
        event_label.setObjectName("mutedText")
        event_label.setWordWrap(True)
        event_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text.addWidget(title)
        text.addWidget(metadata)
        text.addWidget(event_label)
        row_layout.addLayout(text, stretch=1)

        alert_time = datetime.now()
        timestamp = QLabel(
            f"{alert_time.strftime('%b')} {alert_time.day}, {alert_time.year}\n"
            f"{alert_time.strftime('%I:%M:%S %p').lstrip('0')}"
        )
        timestamp.setObjectName("alertTime")
        timestamp.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        timestamp.setMinimumWidth(118)
        row_layout.addWidget(timestamp)

        open_capture = QToolButton()
        open_capture.setObjectName("compactAction")
        open_capture.setProperty("evidence_button", True)
        open_capture.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        open_capture.setToolTip("Open alert evidence")
        open_capture.setEnabled(False)
        open_capture.clicked.connect(
            lambda _checked=False, button=open_capture: self._open_alert_evidence(button)
        )
        row_layout.addWidget(open_capture)

        layout.insertWidget(0, row)
        rows.insert(0, row)
        if alert_key:
            self._alert_rows_by_key.setdefault(alert_key, []).append(row)
        while len(rows) > limit:
            old = rows.pop()
            self._remove_alert_row_reference(old)
            layout.removeWidget(old)
            old.deleteLater()

    def _on_alert_evidence_ready(self, alert_key: str, evidence_path: str) -> None:
        path = Path(evidence_path)
        for row in self._alert_rows_by_key.pop(alert_key, []):
            if path.exists():
                self._set_alert_evidence(row, path)

    def _set_alert_evidence(self, row: QFrame, path: Path) -> None:
        thumbnail = row.findChild(QLabel, "alertThumbnail")
        metadata = row.findChild(QLabel, "alertMeta")
        button = next(
            (
                candidate
                for candidate in row.findChildren(QToolButton)
                if candidate.property("evidence_button")
            ),
            None,
        )
        if thumbnail is not None:
            pixmap = QPixmap(str(path))
            thumbnail.setPixmap(
                pixmap.scaled(
                    thumbnail.width(),
                    thumbnail.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        if button is not None:
            button.setProperty("evidence_path", str(path))
            button.setEnabled(True)
        if metadata is not None:
            source = metadata.property("alert_source")
            if isinstance(source, str):
                metadata.setText(f"{source} | QA capture ready")

    @staticmethod
    def _alert_source_label(event: str) -> str:
        if "jawa droid announcement" in event.casefold():
            return "Jawa recycle toast"
        if "ready for rebirth" in event.casefold():
            return "Rebirth readiness"
        return "Droid spawn feed"

    def _remove_alert_row_reference(self, row: QWidget) -> None:
        alert_key = row.property("alert_key")
        if not isinstance(alert_key, str) or not alert_key:
            return
        active_rows = [candidate for candidate in self._alert_rows_by_key.get(alert_key, []) if candidate is not row]
        if active_rows:
            self._alert_rows_by_key[alert_key] = active_rows
        else:
            self._alert_rows_by_key.pop(alert_key, None)

    def _open_qa_captures(self) -> None:
        directory = runtime_directory() / "qa_captures"
        directory.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def _open_evidence(self, path: Path) -> None:
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_alert_evidence(self, button: QToolButton) -> None:
        stored_path = button.property("evidence_path")
        if isinstance(stored_path, str):
            self._open_evidence(Path(stored_path))

    def _store_telegram_token_if_entered(self) -> None:
        token = self.telegram_bot_token.text().strip()
        if token:
            save_telegram_bot_token(token)
            self._telegram_alert_token = token
            self.telegram_bot_token.clear()

    def _test_telegram(self) -> None:
        try:
            self._store_telegram_token_if_entered()
            token = get_telegram_bot_token()
            self._telegram_alert_token = token
            chat_id = self.telegram_chat_id.text().strip()
            if not chat_id:
                raise ValueError("Enter a Telegram chat ID or use Find recent chat first.")
            self._telegram_dispatcher.enqueue(
                token,
                chat_id,
                "FortniteVision Telegram test",
                "Telegram notifications are configured correctly.",
            )
            self._append_log("Telegram test message queued")
        except Exception as exc:
            self._show_error("Could not send Telegram test", str(exc))

    def _find_telegram_chat(self) -> None:
        try:
            self._store_telegram_token_if_entered()
            token = get_telegram_bot_token()
        except Exception as exc:
            self._show_error("Could not find Telegram chat", str(exc))
            return

        threading.Thread(target=self._find_recent_telegram_chat, args=(token,), daemon=True).start()

    def _find_recent_telegram_chat(self, token: str) -> None:
        try:
            chat_id = find_recent_telegram_chat_id(token)
            self.telegram_chat_found.emit(chat_id)
            self._append_log_threadsafe(f"Telegram chat found: {chat_id}")
        except Exception as exc:
            self._append_log_threadsafe(f"Telegram chat lookup failed: {exc}")

    def _set_detected_telegram_chat(self, chat_id: str) -> None:
        self.telegram_chat_id.setText(chat_id)

    def _clear_telegram_token(self) -> None:
        try:
            clear_telegram_bot_token()
            self._telegram_alert_token = ""
            self.telegram_bot_token.clear()
            self._append_log("Stored Telegram bot token cleared")
        except Exception as exc:
            self._show_error("Could not clear Telegram token", str(exc))

    def _queue_telegram_alert(self, chat_id: str, alert_title: str, event: str) -> None:
        try:
            if not self._telegram_alert_token:
                self._telegram_alert_token = get_telegram_bot_token()
            self._telegram_dispatcher.enqueue(
                self._telegram_alert_token,
                chat_id,
                alert_title,
                event,
            )
            self._append_log("Telegram notification queued")
        except Exception as exc:
            self._append_log(f"Telegram notification could not be queued: {exc}")

    def _on_telegram_delivery(self, result: TelegramDeliveryResult) -> None:
        queue_milliseconds = result.queue_seconds * 1_000
        request_milliseconds = result.request_seconds * 1_000
        if result.error:
            self._append_log_threadsafe(
                f"Telegram notification failed after {request_milliseconds:.0f} ms: {result.error}"
            )
            return
        self._append_log_threadsafe(
            "Telegram notification sent "
            f"in {request_milliseconds:.0f} ms (queue {queue_milliseconds:.0f} ms)"
        )

    def _append_log_threadsafe(self, message: str) -> None:
        self.background_log.emit(message)

    def _on_worker_error(self, message: str) -> None:
        self._worker_has_error = True
        if self._rebirth_syncing:
            self._on_rebirth_requirements_failed("Monitoring stopped while the Rebirth screen was syncing.")
        self._append_log(f"ERROR - {message}")
        self._set_monitor_presentation("Needs attention", running=False)

    def _on_worker_finished(self) -> None:
        if self._rebirth_syncing:
            self._on_rebirth_requirements_failed("Monitoring stopped while the Rebirth screen was syncing.")
        if not self._worker_has_error:
            self._set_monitor_presentation("Paused", running=False)

    def _append_log(self, message: str) -> None:
        stamped = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        self.log.appendPlainText(stamped)
        directory = runtime_directory()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / "droid_history.txt").open("a", encoding="utf-8") as handle:
                handle.write(stamped + "\n")
        except OSError:
            pass

    def _show_error(self, title: str, message: str) -> None:
        self._append_log(f"ERROR - {message}")
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event: object) -> None:  # type: ignore[override]
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(4_000)
        self._telegram_dispatcher.close()
        self._tray.hide()
        event.accept()  # type: ignore[union-attr]

    def showEvent(self, event: object) -> None:  # type: ignore[override]
        super().showEvent(event)  # type: ignore[arg-type]
        self._apply_always_on_top(self.always_on_top.isChecked())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the FortniteVision OCR monitor.")
    parser.add_argument("--config", type=Path, help="Use this JSON config instead of the default per-user config.")
    args = parser.parse_args()
    app = QApplication(sys.argv)
    window = DroidMonitorWindow(args.config)
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
