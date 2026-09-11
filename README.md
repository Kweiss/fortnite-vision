# FortniteVision

A Windows 11 desktop monitor that reads a user-selected screen region, OCRs the visible Droid Tycoon log, and sends alerts for selected droid spawns. It is a local, read-only companion: it does not send keyboard or mouse input, manipulate Fortnite, or keep cloud-gaming sessions active.

## What is built

- Windows multi-monitor selector and monitor-relative crop controls
- 3× image preprocessing plus local RapidOCR/ONNX Runtime recognition
- Conservative feed-efficiency modes: observe OCR skip opportunities first, then optionally skip unchanged frames with a six-second full-OCR safety refresh
- Spawn-event matching, configurable droid/rarity rules, Test Mode for all recognized item calls, and a 45-second duplicate cooldown
- Optional Always on top window mode, a compact scrollable alert-rule picker, and a larger live event log
- Optional image-based Jawa Droid Announcement detection with its own crop preview and match threshold
- Rebirth dashboard with a low-frequency lower-left HUD read and on-demand Rebirth requirement sync
- Windows tray notifications, optional Telegram push, timestamped history, debug crop images, and alert evidence captures
- Optional Telegram alerts using the official Bot API, with bot tokens stored in Windows Credential Manager
- Persisted per-user settings at `%APPDATA%\FortniteVision\config.json`
- Tests for the event parsing, alert selection, and config format

The [Windows OCR research](docs/windows-ocr-research.md) documents why the first build uses a local Python OCR engine rather than the package-identity-only Windows OCR API. The [implementation review](docs/implementation-review.md) maps the supplied macOS script to this Windows implementation.

Opening this folder in Codex on the Windows computer? Start with the [Codex handoff](docs/CODEX_HANDOFF.md) and the detailed [game and build context](docs/GAME_AND_BUILD_CONTEXT.md).

## Windows 11 setup

Install 64-bit Python 3.11, then open PowerShell in this project directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python -m droid_monitor
```

Alternatively, run `scripts\Start-FortniteVision.ps1`; it creates the Python environment, installs the project, and opens the monitor.

The OCR model may take longer to initialize on the first launch. It runs locally once available.

## Everyday launch

Double-click the `FortniteVision` shortcut on your Desktop. It uses `scripts\Launch-FortniteVision.cmd` to open the already installed application without reinstalling dependencies. Use `scripts\Start-FortniteVision.ps1` only when the environment is missing or needs to be repaired.

## First use

1. Select the monitor showing the game.
2. Set the crop to the on-screen log. Coordinates are **X, Y, width, height**, relative to the selected monitor. The default is calibrated to the six-row feed shown in the 3840x2160 reference setup: `(40, 640, 780, 220)`.
3. Click **Save diagnostic preview** and verify that the preview contains the complete spawn line. The raw and processed images are saved under `%APPDATA%\FortniteVision\runtime`.
4. Choose alert rules. Enable Test Mode to log every recognized material/rarity call, including unselected items, while you tune the crop. Enable Telegram only if you want phone push notifications.
5. Start monitoring.

If OCR misses entries, make the crop a little taller/wider, confirm the correct display is selected, and use the processed diagnostic image to refine the rectangle. Test Mode logs only successfully recognized material/rarity spawn calls, rather than every raw OCR attempt.

Whenever an alert fires, FortniteVision saves the exact raw crop that caused it under `%APPDATA%\FortniteVision\runtime\qa_captures` and writes the file path to the activity log. It keeps the 250 newest alert captures for later QA.

For the Jawa monitor, a recycle-icon near-match that falls short of the alert threshold is also saved there. Look for a `[JAWA QA]` log entry when investigating a missed toast.

## Lower CPU Use Safely

Under **Setup > Monitoring preferences**, leave **Droid feed CPU** on **Observe + Shadow Adaptive** for a play session first. It continues to OCR every scan and compares the full-OCR result with an in-process Adaptive simulation, so it cannot miss a droid announcement or send duplicate alerts. The log records predicted OCR skips plus any Adaptive delay or miss; selected-alert misses also save a QA image.

When that looks healthy, select **Adaptive: reduce OCR during quiet feeds**. It preserves the color OCR pipeline, performs OCR whenever bright announcement text changes, and forces a full OCR pass at least every six seconds. **Full OCR every scan** restores the original behavior immediately.

The Jawa Droid announcement monitor is independent of the OCR feed. Enable it, use **Save Jawa diagnostic preview** to frame the lower-right toast area, then adjust the recycle threshold only if the preview shows the toast but no alert is emitted.

## Rebirth Progress

While monitoring is running, the **Rebirth** page reads the lower-left HUD every 15 seconds for Credits, Upgrade Chips, Nova Crystals, and Rebirth level. This is intentionally a small, separate crop so it has a negligible effect on the droid-feed monitoring.

To update the next Rebirth requirements, open the Rebirth screen in-game and click **Sync open Rebirth screen**. FortniteVision briefly hides itself, reads the Rank, Path/Cycle, credit target, and the three green/red droid requirement cards, then returns to the dashboard. The latest successful snapshot is retained between launches.

The Roller Planner uses the supplied Path 1-4 sheets for Rebirths 21-30. It lists the next four Rebirth targets after the current one, highlights droids that return later in the current Path so they can be stored or upgraded, and identifies current droids with no later requirement in that Path. Its sell guidance is deliberately limited to the remaining current Path; it does not assume what will survive a later reset.

## Configuration

On first run the app writes `%APPDATA%\FortniteVision\config.json`. `config.example.json` shows the complete format. `--config path\to\config.json` runs against a separate file, which is useful when keeping profiles for different resolutions.

## Telegram notifications

Create a bot with [@BotFather](https://t.me/BotFather), then open a private chat with that bot and send `/start`. In FortniteVision, enter the bot token, click **Find recent chat**, then click **Send Telegram test**. The bot token is stored in Windows Credential Manager, not in the project or `%APPDATA%` configuration file. Enable Telegram alerts and start monitoring to send matched alerts to that chat.

## Verification

The pure-Python tests do not require a Windows display or the OCR model:

```powershell
python -m unittest discover -s tests
```
