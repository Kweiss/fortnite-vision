"""Persistent settings stored outside the source checkout on Windows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path

from .domain import DEFAULT_ENABLED_RULE_IDS, STELLAR_RULE_IDS
from .efficiency import OCR_MODE_OBSERVE, OCR_MODES


_ALERT_RULE_VERSION = 2
_PRE_DIAMOND_RULE_IDS = frozenset(
    {
        "galatic_mythic",
        "galatic_legendary",
        "galatic_epic",
        "beskar_mythic",
        "beskar_legendary",
        "beskar_epic",
        "rainbow_mythic",
        "rainbow_legendary",
        "rainbow_epic",
    }
)


@dataclass(frozen=True)
class CropRegion:
    """A rectangle in physical pixels, relative to the chosen monitor."""

    x: int = 40
    y: int = 640
    width: int = 780
    height: int = 220

    def validate(self) -> None:
        if self.x < 0 or self.y < 0:
            raise ValueError("Crop X and Y must be zero or greater.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Crop width and height must be greater than zero.")


@dataclass(frozen=True)
class AppConfig:
    """All settings required by the capture worker."""

    monitor_index: int = 1
    crop: CropRegion = field(default_factory=CropRegion)
    scan_interval_seconds: float = 0.75
    spawn_ocr_mode: str = OCR_MODE_OBSERVE
    alert_cooldown_seconds: float = 45.0
    test_mode: bool = False
    always_on_top: bool = False
    jawa_enabled: bool = False
    jawa_crop: CropRegion = field(
        default_factory=lambda: CropRegion(x=2900, y=750, width=600, height=600)
    )
    jawa_match_threshold: float = 0.62
    rebirth_ready_enabled: bool = True
    rebirth_ready_crop: CropRegion = field(
        default_factory=lambda: CropRegion(x=1650, y=1760, width=750, height=220)
    )
    rebirth_ready_match_threshold: float = 0.7
    rebirth_progress_enabled: bool = True
    rebirth_hud_crop: CropRegion = field(
        default_factory=lambda: CropRegion(x=40, y=1760, width=1110, height=210)
    )
    telegram_enabled: bool = False
    telegram_chat_id: str = ""
    enabled_rule_ids: frozenset[str] = field(
        default_factory=lambda: DEFAULT_ENABLED_RULE_IDS
    )
    alert_rule_version: int = _ALERT_RULE_VERSION

    def validate(self) -> None:
        if self.monitor_index < 1:
            raise ValueError("Monitor index must be at least 1.")
        self.crop.validate()
        if not 0.25 <= self.scan_interval_seconds <= 60:
            raise ValueError("Scan interval must be between 0.25 and 60 seconds.")
        if self.spawn_ocr_mode not in OCR_MODES:
            raise ValueError("Droid feed OCR mode is not supported.")
        if not 1 <= self.alert_cooldown_seconds <= 3600:
            raise ValueError("Alert cooldown must be between 1 and 3600 seconds.")
        if not isinstance(self.test_mode, bool):
            raise ValueError("Test mode must be enabled or disabled.")
        if not isinstance(self.always_on_top, bool):
            raise ValueError("Always on top must be enabled or disabled.")
        if not isinstance(self.jawa_enabled, bool):
            raise ValueError("Jawa monitoring must be enabled or disabled.")
        self.jawa_crop.validate()
        if not 0.4 <= self.jawa_match_threshold <= 0.95:
            raise ValueError("Jawa match threshold must be between 0.40 and 0.95.")
        if not isinstance(self.rebirth_ready_enabled, bool):
            raise ValueError("Ready for Rebirth monitoring must be enabled or disabled.")
        self.rebirth_ready_crop.validate()
        if not 0.4 <= self.rebirth_ready_match_threshold <= 0.95:
            raise ValueError("Ready for Rebirth threshold must be between 0.40 and 0.95.")
        if not isinstance(self.rebirth_progress_enabled, bool):
            raise ValueError("Rebirth progress monitoring must be enabled or disabled.")
        self.rebirth_hud_crop.validate()
        if not isinstance(self.telegram_enabled, bool):
            raise ValueError("Telegram alerts must be enabled or disabled.")
        if self.telegram_enabled and not self.telegram_chat_id.strip():
            raise ValueError("Enter a Telegram chat ID before enabling Telegram alerts.")
        if self.alert_rule_version < 1:
            raise ValueError("Alert rule version must be positive.")


def application_directory() -> Path:
    """Return the per-user Windows data directory without touching the repo."""

    app_data = os.environ.get("APPDATA")
    root = Path(app_data) if app_data else Path.home() / ".fortnite-vision"
    return root / "FortniteVision"


def default_config_path() -> Path:
    return application_directory() / "config.json"


def runtime_directory() -> Path:
    return application_directory() / "runtime"


def load_config(path: Path | None = None) -> AppConfig:
    """Load a config file, creating a usable default config on first run."""

    config_path = path or default_config_path()
    if not config_path.exists():
        config = AppConfig()
        save_config(config, config_path)
        return config

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        crop_raw = raw.get("crop", {})
        jawa_crop_raw = raw.get("jawa_crop", {})
        rebirth_ready_crop_raw = raw.get("rebirth_ready_crop", {})
        rebirth_hud_crop_raw = raw.get("rebirth_hud_crop", {})
        enabled_rule_ids = frozenset(
            str(rule_id) for rule_id in raw.get("enabled_rule_ids", DEFAULT_ENABLED_RULE_IDS)
        )
        if enabled_rule_ids == _PRE_DIAMOND_RULE_IDS:
            enabled_rule_ids = DEFAULT_ENABLED_RULE_IDS
        alert_rule_version = int(raw.get("alert_rule_version", 0))
        if alert_rule_version < _ALERT_RULE_VERSION:
            enabled_rule_ids |= STELLAR_RULE_IDS
            alert_rule_version = _ALERT_RULE_VERSION

        config = AppConfig(
            monitor_index=int(raw.get("monitor_index", 1)),
            crop=CropRegion(
                x=int(crop_raw.get("x", 40)),
                y=int(crop_raw.get("y", 640)),
                width=int(crop_raw.get("width", 780)),
                height=int(crop_raw.get("height", 220)),
            ),
            scan_interval_seconds=float(raw.get("scan_interval_seconds", 0.75)),
            spawn_ocr_mode=str(raw.get("spawn_ocr_mode", OCR_MODE_OBSERVE)),
            alert_cooldown_seconds=float(raw.get("alert_cooldown_seconds", 45.0)),
            test_mode=raw.get("test_mode", False),
            always_on_top=raw.get("always_on_top", False),
            jawa_enabled=raw.get("jawa_enabled", False),
            jawa_crop=CropRegion(
                x=int(jawa_crop_raw.get("x", 2900)),
                y=int(jawa_crop_raw.get("y", 750)),
                width=int(jawa_crop_raw.get("width", 600)),
                height=int(jawa_crop_raw.get("height", 600)),
            ),
            jawa_match_threshold=float(raw.get("jawa_match_threshold", 0.62)),
            rebirth_ready_enabled=raw.get("rebirth_ready_enabled", True),
            rebirth_ready_crop=CropRegion(
                x=int(rebirth_ready_crop_raw.get("x", 1650)),
                y=int(rebirth_ready_crop_raw.get("y", 1760)),
                width=int(rebirth_ready_crop_raw.get("width", 750)),
                height=int(rebirth_ready_crop_raw.get("height", 220)),
            ),
            rebirth_ready_match_threshold=float(raw.get("rebirth_ready_match_threshold", 0.7)),
            rebirth_progress_enabled=raw.get("rebirth_progress_enabled", True),
            rebirth_hud_crop=CropRegion(
                x=int(rebirth_hud_crop_raw.get("x", 40)),
                y=int(rebirth_hud_crop_raw.get("y", 1760)),
                width=int(rebirth_hud_crop_raw.get("width", 1110)),
                height=int(rebirth_hud_crop_raw.get("height", 210)),
            ),
            telegram_enabled=raw.get("telegram_enabled", False),
            telegram_chat_id=str(raw.get("telegram_chat_id", "")).strip(),
            enabled_rule_ids=enabled_rule_ids,
            alert_rule_version=alert_rule_version,
        )
        config.validate()
        return config
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not load settings from {config_path}: {exc}") from exc


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    """Validate and atomically write settings for the next launch."""

    config.validate()
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(config)
    payload["enabled_rule_ids"] = sorted(config.enabled_rule_ids)
    temporary = config_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(config_path)
    return config_path
