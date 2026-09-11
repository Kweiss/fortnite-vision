"""Read and persist the player's current Rebirth progress from local screenshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re

import cv2
import numpy as np
from PIL import Image

from .config import runtime_directory


_AMOUNT_PATTERN = re.compile(r"(?<![A-Z0-9])(\d+(?:\.\d+)?)\s*([KMBT])\b", re.IGNORECASE)
_NUMBER_PATTERN = re.compile(r"^\d+$")
_RANK_PATTERN = re.compile(r"\brank\s*(\d+)", re.IGNORECASE)
_PATH_PATTERN = re.compile(r"\bpath\s*(\d+)", re.IGNORECASE)
_VARIANTS = ("Default", "Gold", "Diamond", "Rainbow", "Beskar", "Galactic", "Stellar")
_PANEL_SLOT_BOUNDS = (
    (179, 147, 219, 218),
    (414, 147, 219, 218),
    (650, 147, 219, 218),
    (886, 147, 219, 218),
)


@dataclass(frozen=True)
class RebirthHud:
    credits: str = ""
    upgrade_chips: str = ""
    nova_crystals: str = ""
    rebirth_level: int | None = None
    updated_at: str = ""


@dataclass(frozen=True)
class RebirthRequirement:
    droid_name: str
    variant: str
    owned: bool


@dataclass(frozen=True)
class RebirthRequirements:
    path: int | None = None
    target_rank: int | None = None
    credit_requirement: str = ""
    droids: tuple[RebirthRequirement, ...] = ()
    updated_at: str = ""


@dataclass(frozen=True)
class RebirthProgress:
    hud: RebirthHud = field(default_factory=RebirthHud)
    requirements: RebirthRequirements = field(default_factory=RebirthRequirements)


def parse_hud_text(text: str, captured_at: datetime | None = None) -> RebirthHud | None:
    """Extract the four lower-left HUD values from OCR output in screen order."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    amounts = [_normalise_amount(match.group(0)) for line in lines for match in _AMOUNT_PATTERN.finditer(line)]
    plain_numbers = [int(line) for line in lines if _NUMBER_PATTERN.fullmatch(line)]
    if len(amounts) < 2 or len(plain_numbers) < 2:
        return None
    return RebirthHud(
        credits=amounts[0],
        upgrade_chips=amounts[1],
        nova_crystals=str(plain_numbers[0]),
        rebirth_level=plain_numbers[1],
        updated_at=_timestamp(captured_at),
    )


def parse_requirements_screen(
    panel: Image.Image,
    panel_text: str,
    rank_text: str,
    path_text: str,
    captured_at: datetime | None = None,
) -> RebirthRequirements | None:
    """Extract the target, droid list, and card status from an open Rebirth panel."""

    lines = [line.strip() for line in panel_text.splitlines() if line.strip()]
    variants = [line.title() for line in lines if line.casefold() in {item.casefold() for item in _VARIANTS}]
    droid_names = _read_droid_names(lines, variants)
    credit_matches = _AMOUNT_PATTERN.findall(panel_text)
    if len(variants) != 3 or len(droid_names) != 3 or not credit_matches:
        return None

    card_states = _read_card_states(panel)
    if len(card_states) != 4:
        return None
    target_rank = _find_number(_RANK_PATTERN, rank_text)
    path = _find_number(_PATH_PATTERN, path_text)
    return RebirthRequirements(
        path=path,
        target_rank=target_rank,
        credit_requirement=_normalise_amount("".join(credit_matches[0])),
        droids=tuple(
            RebirthRequirement(name, variant, owned)
            for name, variant, owned in zip(droid_names, variants, card_states[1:], strict=True)
        ),
        updated_at=_timestamp(captured_at),
    )


def compact_amount_value(value: str) -> float | None:
    """Convert a game-formatted compact amount such as ``13.50T`` into a number."""

    match = _AMOUNT_PATTERN.search(value)
    if not match:
        return None
    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}[match.group(2).upper()]
    return float(match.group(1)) * multiplier


def format_compact_amount(value: float) -> str:
    """Format a non-negative number using the game's compact amount notation."""

    for suffix, divisor in (("T", 1_000_000_000_000), ("B", 1_000_000_000), ("M", 1_000_000), ("K", 1_000)):
        if value >= divisor:
            return f"{value / divisor:.2f}".rstrip("0").rstrip(".") + suffix
    return str(round(value))


def load_rebirth_progress(path: Path | None = None) -> RebirthProgress:
    """Load the most recent local Rebirth snapshot without requiring the game to be open."""

    progress_path = path or _progress_path()
    if not progress_path.exists():
        return RebirthProgress()
    try:
        raw = json.loads(progress_path.read_text(encoding="utf-8"))
        hud_raw = raw.get("hud", {})
        requirements_raw = raw.get("requirements", {})
        droids = tuple(
            RebirthRequirement(
                droid_name=str(item["droid_name"]),
                variant=str(item["variant"]),
                owned=bool(item["owned"]),
            )
            for item in requirements_raw.get("droids", [])
        )
        return RebirthProgress(
            hud=RebirthHud(
                credits=str(hud_raw.get("credits", "")),
                upgrade_chips=str(hud_raw.get("upgrade_chips", "")),
                nova_crystals=str(hud_raw.get("nova_crystals", "")),
                rebirth_level=_optional_int(hud_raw.get("rebirth_level")),
                updated_at=str(hud_raw.get("updated_at", "")),
            ),
            requirements=RebirthRequirements(
                path=_optional_int(requirements_raw.get("path")),
                target_rank=_optional_int(requirements_raw.get("target_rank")),
                credit_requirement=str(requirements_raw.get("credit_requirement", "")),
                droids=droids,
                updated_at=str(requirements_raw.get("updated_at", "")),
            ),
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return RebirthProgress()


def save_rebirth_progress(progress: RebirthProgress, path: Path | None = None) -> Path:
    """Atomically persist the latest local Rebirth snapshot."""

    progress_path = path or _progress_path()
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = progress_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(progress), indent=2) + "\n", encoding="utf-8")
    temporary.replace(progress_path)
    return progress_path


def _read_droid_names(lines: list[str], variants: list[str]) -> list[str]:
    last_variant_index = max(index for index, line in enumerate(lines) if line.title() in variants)
    names: list[str] = []
    for line in lines[last_variant_index + 1 :]:
        lowered = line.casefold()
        if "credit" in lowered or lowered.startswith("your "):
            continue
        if line.title() in _VARIANTS or line.casefold() == "need":
            continue
        names.append(line)
        if len(names) == 3:
            break
    return names


def _read_card_states(panel: Image.Image) -> tuple[bool, ...]:
    rgb = np.asarray(panel.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    green = cv2.inRange(hsv, np.array((45, 120, 150)), np.array((90, 255, 255)))
    red = cv2.inRange(hsv, np.array((0, 130, 140)), np.array((10, 255, 255)))
    states: list[bool] = []
    for x, y, width, height in _PANEL_SLOT_BOUNDS:
        green_pixels = int(np.count_nonzero(green[y : y + height, x : x + width]))
        red_pixels = int(np.count_nonzero(red[y : y + height, x : x + width]))
        states.append(green_pixels > red_pixels)
    return tuple(states)


def _normalise_amount(value: str) -> str:
    match = _AMOUNT_PATTERN.search(value)
    if not match:
        return value.strip()
    return f"{match.group(1)}{match.group(2).upper()}"


def _find_number(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(text)
    return int(match.group(1)) if match else None


def _optional_int(value: object) -> int | None:
    return int(value) if value is not None and str(value).strip() else None


def _timestamp(captured_at: datetime | None) -> str:
    return (captured_at or datetime.now()).isoformat(timespec="seconds")


def _progress_path() -> Path:
    return runtime_directory() / "rebirth_progress.json"
