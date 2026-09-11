"""On-disk evidence captures for reviewing emitted alerts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from PIL import Image

from .config import runtime_directory


_MAX_CAPTURES = 250
_UNSAFE_FILENAME = re.compile(r"[^a-z0-9]+")


def save_alert_capture(image: Image.Image, category: str, label: str) -> Path:
    """Save the raw alert crop and retain the most recent evidence captures."""

    directory = runtime_directory() / "qa_captures"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{timestamp}_{_slug(category)}_{_slug(label)}.png"
    path = directory / filename
    image.save(path)
    _trim_old_captures(directory)
    return path


def _slug(value: str) -> str:
    return _UNSAFE_FILENAME.sub("_", value.casefold()).strip("_") or "alert"


def _trim_old_captures(directory: Path) -> None:
    # Every filename starts with a sortable, microsecond-resolution timestamp.
    captures = sorted(directory.glob("*.png"), key=lambda path: path.name, reverse=True)
    for path in captures[_MAX_CAPTURES:]:
        path.unlink(missing_ok=True)
