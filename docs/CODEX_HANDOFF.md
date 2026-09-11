# Codex Handoff - FortniteVision

Start with [Game And Build Context](GAME_AND_BUILD_CONTEXT.md). It is the
authoritative current handoff for this Windows application, including game
mechanics, calibrated crops, alert behavior, Rebirth planning, architecture,
security, launch steps, and known limitations.

Quick orientation:

- FortniteVision is a read-only local companion for Star Wars: Droid Tycoon.
- The stack is PyQt6, `mss`, RapidOCR/ONNX Runtime, OpenCV, and local files.
- User settings are in `%APPDATA%\FortniteVision`; do not overwrite them or
  expose the Telegram token.
- The daily launch path is the `FortniteVision` desktop shortcut, backed by
  `scripts\Launch-FortniteVision.cmd`.
- For development, use `.\.venv\Scripts\python.exe`, not bare `python`.

The early macOS reference was reviewed but intentionally not ported line for
line. See [implementation review](implementation-review.md) and
[Windows OCR research](windows-ocr-research.md) for the historical rationale.
