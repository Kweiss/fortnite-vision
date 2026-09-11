"""Local OCR and image preparation; no game data leaves the computer here."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """Upscale and clarify small game-log text while retaining rarity colors."""

    color = image.convert("RGB")
    enlarged = color.resize((color.width * 3, color.height * 3), Image.Resampling.LANCZOS)
    clarified = ImageEnhance.Contrast(enlarged).enhance(1.1)
    return ImageEnhance.Sharpness(clarified).enhance(1.3).filter(ImageFilter.SHARPEN)


class RapidOcrEngine:
    """A small adapter around RapidOCR's ONNX Runtime implementation."""

    def __init__(self) -> None:
        try:
            from rapidocr import RapidOCR
        except ImportError as exc:  # pragma: no cover - installation error
            raise RuntimeError("OCR is unavailable. Run the Windows setup steps.") from exc
        self._engine = RapidOCR()

    def recognize(self, image: Image.Image) -> str:
        result = self._engine(np.asarray(image))
        return "\n".join(_read_text_lines(result))


def _read_text_lines(result: object) -> list[str]:
    """Support RapidOCR's current result object and older tuple/list results."""

    if result is None:
        return []
    text_values = getattr(result, "txts", None)
    if text_values is not None:
        return [str(text).strip() for text in text_values if str(text).strip()]
    if isinstance(result, dict) and result.get("txts") is not None:
        return [str(text).strip() for text in result["txts"] if str(text).strip()]

    # Older RapidOCR releases return (detections, elapsed_seconds). Each detection
    # is [bounding_box, text, confidence].
    entries: Iterable[object] = result[0] if isinstance(result, tuple) else result  # type: ignore[index]
    lines: list[str] = []
    if not isinstance(entries, Iterable) or isinstance(entries, (str, bytes)):
        return lines
    for entry in entries:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2 and isinstance(entry[1], str):
            text = entry[1].strip()
            if text:
                lines.append(text)
    return lines
