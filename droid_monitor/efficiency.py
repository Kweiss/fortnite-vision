"""Conservative change detection and timing summaries for the spawn feed."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Mapping

import numpy as np
from PIL import Image


OCR_MODE_FULL = "full"
OCR_MODE_OBSERVE = "observe"
OCR_MODE_ADAPTIVE = "adaptive"
OCR_MODES = frozenset({OCR_MODE_FULL, OCR_MODE_OBSERVE, OCR_MODE_ADAPTIVE})


@dataclass(frozen=True)
class SpawnOcrDecision:
    """Whether an adaptive scan should pay the cost of a full OCR pass."""

    should_run_ocr: bool
    reason: str
    changed_ratio: float


class SpawnFeedChangeGate:
    """Detect meaningful colored-text changes without replacing OCR validation."""

    def __init__(
        self,
        safety_interval_seconds: float = 6.0,
        changed_ratio_threshold: float = 0.0005,
    ) -> None:
        self._safety_interval_seconds = safety_interval_seconds
        self._changed_ratio_threshold = changed_ratio_threshold
        self._previous_signature: np.ndarray | None = None
        self._last_ocr_at: float | None = None

    def inspect(self, frame: Image.Image, now: float | None = None) -> SpawnOcrDecision:
        """Return a conservative OCR decision and retain the latest feed signature."""

        scanned_at = time.monotonic() if now is None else now
        signature = _text_signature(frame)
        previous = self._previous_signature
        self._previous_signature = signature

        if previous is None or previous.shape != signature.shape:
            return SpawnOcrDecision(True, "initial", 1.0)

        changed_ratio = float(np.count_nonzero(signature != previous)) / signature.size
        if changed_ratio >= self._changed_ratio_threshold:
            return SpawnOcrDecision(True, "feed changed", changed_ratio)
        if self._last_ocr_at is None or scanned_at - self._last_ocr_at >= self._safety_interval_seconds:
            return SpawnOcrDecision(True, "safety refresh", changed_ratio)
        return SpawnOcrDecision(False, "unchanged", changed_ratio)

    def record_ocr(self, now: float | None = None) -> None:
        self._last_ocr_at = time.monotonic() if now is None else now


@dataclass
class FeedPerformanceSummary:
    """Accumulate low-volume monitoring telemetry for a short reporting window."""

    scans: int = 0
    ocr_runs: int = 0
    would_skip: int = 0
    capture_seconds: float = 0.0
    gate_seconds: float = 0.0
    preprocessing_seconds: float = 0.0
    ocr_seconds: float = 0.0

    def record(
        self,
        *,
        ocr_ran: bool,
        would_skip: bool,
        capture_seconds: float,
        gate_seconds: float,
        preprocessing_seconds: float = 0.0,
        ocr_seconds: float = 0.0,
    ) -> None:
        self.scans += 1
        self.ocr_runs += int(ocr_ran)
        self.would_skip += int(would_skip)
        self.capture_seconds += capture_seconds
        self.gate_seconds += gate_seconds
        self.preprocessing_seconds += preprocessing_seconds
        self.ocr_seconds += ocr_seconds

    def take_message(self, mode: str) -> str | None:
        if not self.scans:
            return None
        scan_count = self.scans
        ocr_count = self.ocr_runs
        would_skip = self.would_skip
        average_capture = self.capture_seconds / scan_count * 1_000
        average_gate = self.gate_seconds / scan_count * 1_000
        average_ocr = self.ocr_seconds / ocr_count * 1_000 if ocr_count else 0.0
        self.scans = 0
        self.ocr_runs = 0
        self.would_skip = 0
        self.capture_seconds = 0.0
        self.gate_seconds = 0.0
        self.preprocessing_seconds = 0.0
        self.ocr_seconds = 0.0
        if mode == OCR_MODE_OBSERVE:
            return (
                "[PERF] Feed OCR observe: would skip "
                f"{would_skip}/{scan_count} scans; capture {average_capture:.0f} ms, "
                f"change check {average_gate:.1f} ms, OCR {average_ocr:.0f} ms"
            )
        return (
            "[PERF] Feed OCR adaptive: ran "
            f"{ocr_count}/{scan_count} scans; capture {average_capture:.0f} ms, "
            f"change check {average_gate:.1f} ms, OCR {average_ocr:.0f} ms"
        )


@dataclass(frozen=True)
class ShadowAdaptiveFinding:
    """A delayed or missed event from the simulated Adaptive detector."""

    category: str
    label: str
    event: str
    outcome: str
    elapsed_seconds: float


@dataclass(frozen=True)
class _PendingShadowEvent:
    label: str
    event: str
    first_seen_at: float


class ShadowAdaptiveComparison:
    """Compare full OCR against an in-process Adaptive simulation.

    Observe mode still OCRs every frame. This class only simulates the events
    Adaptive would have emitted from frames that its change gate selected.
    """

    def __init__(self) -> None:
        self._reference_recent: dict[tuple[str, str], float] = {}
        self._adaptive_recent: dict[tuple[str, str], float] = {}
        self._pending: dict[tuple[str, str], _PendingShadowEvent] = {}
        self._reference_recognized = 0
        self._reference_alerts = 0
        self._adaptive_recognized = 0
        self._adaptive_alerts = 0
        self._delayed = 0
        self._delay_seconds = 0.0
        self._missed = 0

    def record_frame(
        self,
        category: str,
        events: Mapping[str, str],
        *,
        adaptive_ran: bool,
        cooldown_seconds: float,
        now: float,
    ) -> list[ShadowAdaptiveFinding]:
        """Record one full-OCR frame and return completed shadow outcomes."""

        current_events = {
            _event_key(event): (label, event)
            for event, label in events.items()
        }
        for key, (label, event) in current_events.items():
            state_key = (category, key)
            if self._is_new(self._reference_recent, state_key, cooldown_seconds, now):
                self._record_reference(category)
                if not adaptive_ran and not self._is_recent(
                    self._adaptive_recent,
                    state_key,
                    cooldown_seconds,
                    now,
                ):
                    self._pending.setdefault(
                        state_key,
                        _PendingShadowEvent(label=label, event=event, first_seen_at=now),
                    )

        findings: list[ShadowAdaptiveFinding] = []
        if adaptive_ran:
            for key, (label, event) in current_events.items():
                state_key = (category, key)
                shadow_new = self._is_new(
                    self._adaptive_recent,
                    state_key,
                    cooldown_seconds,
                    now,
                )
                pending = self._pending.pop(state_key, None)
                if shadow_new:
                    self._record_adaptive(category)
                if pending and shadow_new:
                    delay = now - pending.first_seen_at
                    self._delayed += 1
                    self._delay_seconds += delay
                    findings.append(
                        ShadowAdaptiveFinding(
                            category=category,
                            label=pending.label,
                            event=pending.event,
                            outcome="delayed",
                            elapsed_seconds=delay,
                        )
                    )

        for state_key, pending in tuple(self._pending.items()):
            pending_category, pending_event = state_key
            if pending_category != category or pending_event in current_events:
                continue
            self._pending.pop(state_key)
            self._missed += 1
            findings.append(
                ShadowAdaptiveFinding(
                    category=category,
                    label=pending.label,
                    event=pending.event,
                    outcome="missed",
                    elapsed_seconds=now - pending.first_seen_at,
                )
            )
        return findings

    def take_message(self) -> str:
        """Return and reset the reporting-window totals without losing state."""

        delay_detail = "0"
        if self._delayed:
            delay_detail = f"{self._delayed} (avg {self._delay_seconds / self._delayed:.1f}s)"
        message = (
            "[SHADOW] Adaptive compare: reference "
            f"{self._reference_recognized} recognized / {self._reference_alerts} selected alerts; "
            f"shadow {self._adaptive_recognized} recognized / {self._adaptive_alerts} selected alerts; "
            f"delayed {delay_detail}; missed {self._missed}; pending {len(self._pending)}"
        )
        self._reference_recognized = 0
        self._reference_alerts = 0
        self._adaptive_recognized = 0
        self._adaptive_alerts = 0
        self._delayed = 0
        self._delay_seconds = 0.0
        self._missed = 0
        return message

    @staticmethod
    def _is_new(
        recent: dict[tuple[str, str], float],
        key: tuple[str, str],
        cooldown_seconds: float,
        now: float,
    ) -> bool:
        if ShadowAdaptiveComparison._is_recent(recent, key, cooldown_seconds, now):
            return False
        recent[key] = now
        return True

    @staticmethod
    def _is_recent(
        recent: dict[tuple[str, str], float],
        key: tuple[str, str],
        cooldown_seconds: float,
        now: float,
    ) -> bool:
        previous = recent.get(key)
        return previous is not None and now - previous <= cooldown_seconds

    def _record_reference(self, category: str) -> None:
        if category == "recognized":
            self._reference_recognized += 1
        else:
            self._reference_alerts += 1

    def _record_adaptive(self, category: str) -> None:
        if category == "recognized":
            self._adaptive_recognized += 1
        else:
            self._adaptive_alerts += 1


def _text_signature(frame: Image.Image) -> np.ndarray:
    """Return a tiny color-aware mask that emphasizes the bright announcement text."""

    reduced = frame.convert("RGB").resize((195, 55), Image.Resampling.BOX)
    pixels = np.asarray(reduced, dtype=np.int16)
    brightness = pixels.max(axis=2)
    chroma = pixels.max(axis=2) - pixels.min(axis=2)
    return ((brightness >= 145) & (chroma >= 25)) | (brightness >= 220)


def _event_key(event: str) -> str:
    return " ".join(event.casefold().split())
