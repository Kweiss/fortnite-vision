"""Windows screen capture with monitor-relative physical-pixel coordinates."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .config import CropRegion


@dataclass(frozen=True)
class MonitorInfo:
    index: int
    left: int
    top: int
    width: int
    height: int

    @property
    def label(self) -> str:
        return (
            f"Monitor {self.index} — {self.width}×{self.height} "
            f"at ({self.left}, {self.top})"
        )


class ScreenCapture:
    """Owns an MSS capture session; create it in the thread doing the capture."""

    def __init__(self) -> None:
        try:
            import mss
        except ImportError as exc:  # pragma: no cover - installation error
            raise RuntimeError("Screen capture is unavailable. Run the Windows setup steps.") from exc
        self._mss = mss.mss()

    def __enter__(self) -> "ScreenCapture":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._mss.close()

    def monitors(self) -> list[MonitorInfo]:
        # mss.monitors[0] describes the virtual desktop. Real displays start at 1.
        return [
            MonitorInfo(
                index=index,
                left=monitor["left"],
                top=monitor["top"],
                width=monitor["width"],
                height=monitor["height"],
            )
            for index, monitor in enumerate(self._mss.monitors[1:], start=1)
        ]

    def capture(self, monitor_index: int, crop: CropRegion) -> Image.Image:
        crop.validate()
        if monitor_index < 1 or monitor_index >= len(self._mss.monitors):
            raise ValueError("The selected monitor is no longer available.")

        monitor = self._mss.monitors[monitor_index]
        if crop.x + crop.width > monitor["width"] or crop.y + crop.height > monitor["height"]:
            raise ValueError(
                "The crop extends beyond the selected monitor. Adjust X, Y, width, or height."
            )

        screenshot = self._mss.grab(
            {
                "left": monitor["left"] + crop.x,
                "top": monitor["top"] + crop.y,
                "width": crop.width,
                "height": crop.height,
            }
        )
        return Image.frombytes("RGB", screenshot.size, screenshot.rgb)
