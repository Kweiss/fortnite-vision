"""Background worker that captures, OCRs, filters, and deduplicates events."""

from __future__ import annotations

from copy import deepcopy
import threading
import time
from uuid import uuid4

from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal

from .capture import ScreenCapture
from .config import AppConfig, CropRegion
from .domain import extract_spawn_events, match_alert, parse_spawn_event
from .efficiency import (
    OCR_MODE_ADAPTIVE,
    OCR_MODE_FULL,
    OCR_MODE_OBSERVE,
    FeedPerformanceSummary,
    ShadowAdaptiveComparison,
    ShadowAdaptiveFinding,
    SpawnFeedChangeGate,
)
from .jawa import JawaAnnouncementDetector
from .ocr import RapidOcrEngine, preprocess_for_ocr
from .qa import save_alert_capture
from .rebirth import RebirthReadyDetector
from .rebirth_progress import (
    RebirthHud,
    RebirthRequirements,
    parse_hud_text,
    parse_requirements_screen,
)


_JAWA_QA_SCORE = 0.35
_JAWA_QA_COOLDOWN_SECONDS = 120.0
_REBIRTH_RELEASE_OFFSET = 0.12
_REBIRTH_SCAN_INTERVAL_SECONDS = 4.0
_REBIRTH_HUD_SCAN_INTERVAL_SECONDS = 15.0
_PERFORMANCE_REPORT_SECONDS = 30.0
_REBIRTH_REQUIREMENTS_CROP = CropRegion(x=1250, y=1100, width=1350, height=600)
_REBIRTH_RANK_CROP = CropRegion(x=30, y=35, width=870, height=145)
_REBIRTH_PATH_CROP = CropRegion(x=3150, y=25, width=650, height=155)


class MonitorWorker(QThread):
    status = pyqtSignal(str)
    heartbeat = pyqtSignal()
    event_found = pyqtSignal(str)
    alert_found = pyqtSignal(str, str, str)
    evidence_ready = pyqtSignal(str, str)
    rebirth_hud_found = pyqtSignal(object)
    rebirth_requirements_found = pyqtSignal(object)
    rebirth_requirements_failed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = deepcopy(config)
        self._config_lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._recent_alerts: dict[str, float] = {}
        self._recent_test_events: dict[str, float] = {}
        self._jawa_visible = False
        self._rebirth_ready_visible = False
        self._last_rebirth_check_at: float | None = None
        self._last_rebirth_hud_scan_at: float | None = None
        self._rebirth_requirements_requested = threading.Event()

    def update_config(self, config: AppConfig) -> None:
        """Safely apply alert toggles and crop edits during a scan session."""

        config.validate()
        with self._config_lock:
            self._config = deepcopy(config)

    def stop(self) -> None:
        self._stop_requested.set()

    def request_rebirth_requirements_capture(self) -> None:
        """Capture the open Rebirth screen during the next safe worker cycle."""

        self._rebirth_requirements_requested.set()

    def _current_config(self) -> AppConfig:
        with self._config_lock:
            return deepcopy(self._config)

    def run(self) -> None:
        try:
            self.status.emit("Loading local OCR model…")
            engine = RapidOcrEngine()
            jawa_detector = JawaAnnouncementDetector()
            rebirth_detector = RebirthReadyDetector()
            spawn_gate = SpawnFeedChangeGate()
            feed_performance = FeedPerformanceSummary()
            shadow_adaptive = ShadowAdaptiveComparison()
            last_performance_report_at = time.monotonic()
            previous_ocr_mode: str | None = None
            with ScreenCapture() as capture:
                self.status.emit("Monitoring active")
                while not self._stop_requested.is_set():
                    config = self._current_config()
                    now = time.monotonic()
                    if config.spawn_ocr_mode != previous_ocr_mode:
                        spawn_gate = SpawnFeedChangeGate()
                        feed_performance = FeedPerformanceSummary()
                        shadow_adaptive = ShadowAdaptiveComparison()
                        last_performance_report_at = now
                        previous_ocr_mode = config.spawn_ocr_mode
                        if config.spawn_ocr_mode == OCR_MODE_OBSERVE:
                            self.event_found.emit(
                                "[SHADOW] Adaptive comparison started; full OCR remains active."
                            )
                    if self._rebirth_check_is_due(now):
                        self._check_rebirth_ready(capture, config, rebirth_detector)
                    if self._rebirth_hud_scan_is_due(now, config):
                        self._scan_rebirth_hud(capture, config, engine)
                    self._check_jawa_announcement(capture, config, jawa_detector)

                    scan_started_at = time.perf_counter()
                    frame = capture.capture(config.monitor_index, config.crop)
                    capture_seconds = time.perf_counter() - scan_started_at
                    change_started_at = time.perf_counter()
                    decision = spawn_gate.inspect(frame, now)
                    change_seconds = time.perf_counter() - change_started_at
                    adaptive_skip = config.spawn_ocr_mode == OCR_MODE_ADAPTIVE and not decision.should_run_ocr
                    observe_skip = config.spawn_ocr_mode == OCR_MODE_OBSERVE and not decision.should_run_ocr
                    preprocessing_seconds = 0.0
                    ocr_seconds = 0.0
                    text = ""
                    if not adaptive_skip:
                        preprocessing_started_at = time.perf_counter()
                        processed = preprocess_for_ocr(frame)
                        preprocessing_seconds = time.perf_counter() - preprocessing_started_at
                        ocr_started_at = time.perf_counter()
                        text = engine.recognize(processed)
                        ocr_seconds = time.perf_counter() - ocr_started_at

                    # Observe runs reference OCR every cycle. The gate must only
                    # advance when Adaptive itself would have run OCR, otherwise
                    # its six-second safety refresh would never be represented.
                    if decision.should_run_ocr:
                        spawn_gate.record_ocr(now)
                    feed_performance.record(
                        ocr_ran=not adaptive_skip,
                        would_skip=observe_skip or adaptive_skip,
                        capture_seconds=capture_seconds,
                        gate_seconds=change_seconds,
                        preprocessing_seconds=preprocessing_seconds,
                        ocr_seconds=ocr_seconds,
                    )
                    spawn_events = extract_spawn_events(text)
                    parsed_events = [
                        (event, parse_spawn_event(event), match_alert(event, config.enabled_rule_ids))
                        for event in spawn_events
                    ]
                    if config.spawn_ocr_mode == OCR_MODE_OBSERVE:
                        recognized_events = {
                            event: recognized.label
                            for event, recognized, _ in parsed_events
                            if recognized
                        }
                        selected_alerts = {
                            event: rule.label
                            for event, _, rule in parsed_events
                            if rule
                        }
                        self._emit_shadow_findings(
                            shadow_adaptive.record_frame(
                                "recognized",
                                recognized_events,
                                adaptive_ran=decision.should_run_ocr,
                                cooldown_seconds=config.alert_cooldown_seconds,
                                now=now,
                            ),
                            frame,
                        )
                        self._emit_shadow_findings(
                            shadow_adaptive.record_frame(
                                "selected alert",
                                selected_alerts,
                                adaptive_ran=decision.should_run_ocr,
                                cooldown_seconds=config.alert_cooldown_seconds,
                                now=now,
                            ),
                            frame,
                        )
                    for event, recognized, rule in parsed_events:
                        if (
                            config.test_mode
                            and recognized
                            and self._is_new_test_event(event, config.alert_cooldown_seconds)
                        ):
                            self.event_found.emit(f"[TEST] {recognized.label}: {event}")
                        if rule and self._is_new(event, config.alert_cooldown_seconds):
                            self._emit_alert(
                                frame,
                                "spawn",
                                rule.label,
                                f"{rule.emoji} {rule.label}!",
                                event,
                                "Spawn detection: "
                                f"capture {capture_seconds * 1_000:.0f} ms, "
                                f"change check {change_seconds * 1_000:.1f} ms, "
                                f"preprocess {preprocessing_seconds * 1_000:.0f} ms, "
                                f"OCR {ocr_seconds * 1_000:.0f} ms",
                            )
                    if (
                        config.spawn_ocr_mode != OCR_MODE_FULL
                        and now - last_performance_report_at >= _PERFORMANCE_REPORT_SECONDS
                    ):
                        performance_message = feed_performance.take_message(config.spawn_ocr_mode)
                        if performance_message:
                            self.event_found.emit(performance_message)
                        if config.spawn_ocr_mode == OCR_MODE_OBSERVE:
                            self.event_found.emit(shadow_adaptive.take_message())
                        last_performance_report_at = now
                    if self._rebirth_requirements_requested.is_set():
                        self._rebirth_requirements_requested.clear()
                        self._capture_rebirth_requirements(capture, config, engine)
                    self.heartbeat.emit()
                    self._stop_requested.wait(config.scan_interval_seconds)
        except Exception as exc:
            if not self._stop_requested.is_set():
                self.failed.emit(str(exc))
        finally:
            self.status.emit("Monitoring stopped")

    def _is_new(self, event: str, cooldown_seconds: float) -> bool:
        now = time.monotonic()
        key = event.casefold().strip()
        previous = self._recent_alerts.get(key, 0.0)
        if now - previous <= cooldown_seconds:
            return False
        self._recent_alerts[key] = now
        return True

    def _is_new_test_event(self, event: str, cooldown_seconds: float) -> bool:
        now = time.monotonic()
        key = event.casefold().strip()
        previous = self._recent_test_events.get(key, 0.0)
        if now - previous <= cooldown_seconds:
            return False
        self._recent_test_events[key] = now
        return True

    def _emit_shadow_findings(
        self,
        findings: list[ShadowAdaptiveFinding],
        frame: Image.Image,
    ) -> None:
        for finding in findings:
            if finding.outcome == "delayed":
                self.event_found.emit(
                    "[SHADOW] Adaptive delayed "
                    f"{finding.category}: {finding.label} by {finding.elapsed_seconds:.1f}s"
                )
                continue
            self.event_found.emit(
                "[SHADOW] Adaptive would miss "
                f"{finding.category}: {finding.label} after {finding.elapsed_seconds:.1f}s"
            )
            if finding.category == "selected alert":
                self._save_qa_capture_async(frame, "shadow_miss", finding.label)

    def _check_jawa_announcement(
        self,
        capture: ScreenCapture,
        config: AppConfig,
        detector: JawaAnnouncementDetector,
    ) -> None:
        if not config.jawa_enabled:
            self._jawa_visible = False
            return

        capture_started_at = time.perf_counter()
        jawa_frame = capture.capture(config.monitor_index, config.jawa_crop)
        capture_seconds = time.perf_counter() - capture_started_at
        matching_started_at = time.perf_counter()
        score = detector.score(jawa_frame)
        matching_seconds = time.perf_counter() - matching_started_at
        is_visible = score >= config.jawa_match_threshold
        if is_visible and not self._jawa_visible:
            event = "Jawa Droid Announcement detected"
            if self._is_new(event, config.alert_cooldown_seconds):
                self.event_found.emit(f"[JAWA] {event} ({score:.0%} recycle match)")
                self._emit_alert(
                    jawa_frame,
                    "jawa",
                    "Jawa Droid Announcement",
                    "Jawa Droid Announcement!",
                    event,
                    "Jawa detection: "
                    f"capture {capture_seconds * 1_000:.0f} ms, "
                    f"match {matching_seconds * 1_000:.0f} ms",
                )
        elif score >= _JAWA_QA_SCORE and self._is_new(
            "Jawa Droid Announcement near match",
            max(config.alert_cooldown_seconds, _JAWA_QA_COOLDOWN_SECONDS),
        ):
            self._save_qa_capture_async(jawa_frame, "jawa_candidate", "Jawa near match")
            self.event_found.emit(f"[JAWA QA] Near match saved for review ({score:.0%} recycle match)")
        self._jawa_visible = is_visible

    def _check_rebirth_ready(
        self,
        capture: ScreenCapture,
        config: AppConfig,
        detector: RebirthReadyDetector,
    ) -> None:
        if not config.rebirth_ready_enabled:
            self._rebirth_ready_visible = False
            return

        capture_started_at = time.perf_counter()
        rebirth_frame = capture.capture(config.monitor_index, config.rebirth_ready_crop)
        capture_seconds = time.perf_counter() - capture_started_at
        matching_started_at = time.perf_counter()
        score = detector.score(rebirth_frame)
        matching_seconds = time.perf_counter() - matching_started_at
        is_visible = score >= config.rebirth_ready_match_threshold
        if is_visible and not self._rebirth_ready_visible:
            event = "Ready for Rebirth detected"
            self.event_found.emit(f"[REBIRTH] {event} ({score:.0%} ready match)")
            self._emit_alert(
                rebirth_frame,
                "rebirth",
                "Ready for Rebirth",
                "Ready for Rebirth!",
                event,
                "Rebirth detection: "
                f"capture {capture_seconds * 1_000:.0f} ms, "
                f"match {matching_seconds * 1_000:.0f} ms",
            )

        if score < max(0.4, config.rebirth_ready_match_threshold - _REBIRTH_RELEASE_OFFSET):
            self._rebirth_ready_visible = False
        elif is_visible:
            self._rebirth_ready_visible = True

    def _rebirth_check_is_due(self, now: float) -> bool:
        if (
            self._last_rebirth_check_at is not None
            and now - self._last_rebirth_check_at < _REBIRTH_SCAN_INTERVAL_SECONDS
        ):
            return False
        self._last_rebirth_check_at = now
        return True

    def _rebirth_hud_scan_is_due(self, now: float, config: AppConfig) -> bool:
        if not config.rebirth_progress_enabled:
            return False
        if (
            self._last_rebirth_hud_scan_at is not None
            and now - self._last_rebirth_hud_scan_at < _REBIRTH_HUD_SCAN_INTERVAL_SECONDS
        ):
            return False
        self._last_rebirth_hud_scan_at = now
        return True

    def _scan_rebirth_hud(
        self,
        capture: ScreenCapture,
        config: AppConfig,
        engine: RapidOcrEngine,
    ) -> None:
        if not config.rebirth_progress_enabled:
            return
        frame = capture.capture(config.monitor_index, config.rebirth_hud_crop)
        text = engine.recognize(preprocess_for_ocr(frame))
        hud = parse_hud_text(text)
        if hud:
            self.rebirth_hud_found.emit(hud)

    def _capture_rebirth_requirements(
        self,
        capture: ScreenCapture,
        config: AppConfig,
        engine: RapidOcrEngine,
    ) -> None:
        try:
            panel = capture.capture(config.monitor_index, _REBIRTH_REQUIREMENTS_CROP)
            rank = capture.capture(config.monitor_index, _REBIRTH_RANK_CROP)
            path = capture.capture(config.monitor_index, _REBIRTH_PATH_CROP)
            requirements = parse_requirements_screen(
                panel,
                engine.recognize(preprocess_for_ocr(panel)),
                engine.recognize(preprocess_for_ocr(rank)),
                engine.recognize(preprocess_for_ocr(path)),
            )
            if not requirements:
                raise ValueError("Open the Rebirth screen fully, then try Sync Rebirth again.")
            self.rebirth_requirements_found.emit(requirements)
            self.event_found.emit(
                "[REBIRTH] Requirements synced: "
                f"Path {requirements.path or '?'} | Rank {requirements.target_rank or '?'}"
            )
        except Exception as exc:
            self.rebirth_requirements_failed.emit(str(exc))

    def _emit_alert(
        self,
        frame: Image.Image,
        category: str,
        label: str,
        alert_title: str,
        event: str,
        performance_detail: str,
    ) -> None:
        alert_key = uuid4().hex
        self.alert_found.emit(alert_title, event, alert_key)
        self._save_qa_capture_async(frame, category, label, alert_key)
        self.event_found.emit(f"[PERF] {performance_detail}")

    def _save_qa_capture_async(
        self,
        frame: Image.Image,
        category: str,
        label: str,
        alert_key: str = "",
    ) -> None:
        threading.Thread(
            target=self._save_qa_capture,
            args=(frame.copy(), category, label, alert_key),
            name="FortniteVision QA capture",
            daemon=True,
        ).start()

    def _save_qa_capture(
        self,
        frame: Image.Image,
        category: str,
        label: str,
        alert_key: str,
    ) -> None:
        try:
            path = save_alert_capture(frame, category, label)
            self.event_found.emit(f"[QA] Alert capture saved: {path}")
            if alert_key:
                self.evidence_ready.emit(alert_key, str(path))
        except OSError as exc:
            self.event_found.emit(f"[QA] Could not save alert capture: {exc}")
