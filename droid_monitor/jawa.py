"""Image matching for the Jawa Droid announcement recycle icon."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


_REFERENCE_IMAGE = Path(__file__).with_name("assets") / "jawa_reference.png"
_GREEN_LOWER = (35, 90, 120)
_GREEN_UPPER = (95, 255, 255)
_SCALES = (0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0, 2.25, 2.4, 2.5)


class JawaAnnouncementDetector:
    """Match the characteristic green recycle mark in a cropped toast region."""

    def score(self, image: Image.Image) -> float:
        search = _green_mask(image)
        best_score = 0.0
        for template in _reference_templates():
            template_height, template_width = template.shape
            if search.shape[0] < template_height or search.shape[1] < template_width:
                continue
            result = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
            if result.size:
                best_score = max(best_score, float(np.nanmax(result)))
        return best_score


def _green_mask(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"))
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    return cv2.inRange(hsv, _GREEN_LOWER, _GREEN_UPPER)


@lru_cache(maxsize=1)
def _reference_templates() -> tuple[np.ndarray, ...]:
    with Image.open(_REFERENCE_IMAGE) as image:
        mask = _green_mask(image)
    x, y, width, height = _reference_icon_bounds(mask)
    icon = mask[y : y + height, x : x + width]
    return tuple(
        cv2.resize(icon, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        for scale in _SCALES
    )


def _reference_icon_bounds(mask: np.ndarray) -> tuple[int, int, int, int]:
    _, _, statistics, _ = cv2.connectedComponentsWithStats(mask)
    components = sorted(statistics[1:], key=lambda component: int(component[4]), reverse=True)
    if len(components) < 2:
        raise RuntimeError("The Jawa recycle reference image does not contain the expected icon.")

    largest_area = int(components[0][4])
    icon_components = [component for component in components if int(component[4]) >= largest_area * 0.4]
    left = min(int(component[0]) for component in icon_components)
    top = min(int(component[1]) for component in icon_components)
    right = max(int(component[0] + component[2]) for component in icon_components)
    bottom = max(int(component[1] + component[3]) for component in icon_components)
    padding = 14
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(mask.shape[1], right + padding)
    bottom = min(mask.shape[0], bottom + padding)
    return left, top, right - left, bottom - top
