"""Image matching for the bottom-center Ready for Rebirth badge."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


_REFERENCE_IMAGE = Path(__file__).with_name("assets") / "rebirth_ready_reference.png"
_GREEN_LOWER = (35, 90, 120)
_GREEN_UPPER = (95, 255, 255)
_SCALES = (0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3)


class RebirthReadyDetector:
    """Match the green recycle mark and READY! wordmark as one badge."""

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
    return tuple(
        cv2.resize(mask, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        for scale in _SCALES
    )
