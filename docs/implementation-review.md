# Review Of The Supplied macOS Monitor

This is historical context for the first Windows replacement. For the current
application behavior, calibrated crops, and game mechanics, read
[Game And Build Context](GAME_AND_BUILD_CONTEXT.md).

The supplied CodeShare script was a useful behavioral prototype, but was not
portable as-is. The Windows application deliberately makes these substitutions:

| Original concern | Windows project decision |
| --- | --- |
| `ImageGrab` of a fixed `LOCAL_CROP_AREA` | `mss` captures a physical-pixel crop relative to the selected monitor. Users calibrate it from the desktop UI. |
| AppleScript and Apple Vision OCR | A local RapidOCR model runs through ONNX Runtime in a Python desktop app. |
| Monitor picker, alert checkboxes, status/log window, tray icon | Retained and expanded in the PyQt6 interface. |
| Image scaling, contrast, and sharpening | Retained as color-preserving RGB contrast/sharpening before a 3x upscale. |
| Regex event extraction and duplicate cooldown | Retained, extended for real OCR variations, and unit-tested. |
| Text history and debug images | Stored under `%APPDATA%\FortniteVision\runtime`. |
| Push notification | Replaced with opt-in Telegram. The token is stored in Windows Credential Manager and TLS validation remains enabled. |
| Anti-AFK keyboard simulation | Deliberately omitted. FortniteVision is read-only and does not generate game or cloud-session input. |

## Calibration Expectation

No fixed crop is reliable across resolutions, display scaling, windowed/full
screen mode, or game UI changes. Select the monitor containing the game and use
the diagnostic preview plus saved QA images before adjusting OCR behavior.

## Behavior Kept Intentionally Narrow

The app reads configured display pixels and sends an alert only after a local
recognition/template match. It does not inspect game memory, inject input,
select targets, click, move, buy, rebirth, or alter gameplay.
