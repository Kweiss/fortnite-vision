# FortniteVision Game And Build Context

Read this document before changing FortniteVision. It records the game knowledge,
calibrated screen regions, user priorities, and architecture accumulated during
the Windows build. Last consolidated: 2026-08-01.

## Purpose And Boundaries

FortniteVision is a local, read-only Windows companion for the Fortnite Creative
game Star Wars: Droid Tycoon. It captures selected display pixels, performs local
OCR/template matching, saves local evidence, and sends optional notifications.

Do not add keyboard, mouse, controller, anti-idle, menu automation, memory reads,
packet interception, process inspection, targeting, or cloud-session keepalive
behavior without an explicit new scope decision. The app does not buy droids or
perform Rebirths.

## Active User Setup

The current game layout is 3840x2160 on monitor index 1. Coordinates are physical
pixels relative to the selected monitor, as used by `mss`; they are not virtual
desktop coordinates or PyQt logical pixels.

| Feature | Current calibration / timing | Notes |
| --- | --- | --- |
| Droid feed | `(20, 640, 780, 220)`, 2.0 s scan | Six scrolling spawn lines on the left. Default is `(40, 640, 780, 220)`. |
| Jawa toast | `(3240, 600, 600, 600)` | Tuned to the recycle icon farther right than the original default. |
| Ready badge | `(1650, 1760, 750, 220)`, max every 4 s | Bottom-center green recycle icon and `READY!`. |
| Rebirth HUD | `(40, 1760, 1110, 210)`, every 15 s | Credits, Upgrade Chips, Nova Crystals, Rebirth level. |
| Rebirth panel | `(1250, 1100, 1350, 600)`, on demand | Parsed only after the user presses Sync with the panel open. |
| Rebirth Rank | `(30, 35, 870, 145)`, on demand | Parses `Rank N`. |
| Rebirth Path | `(3150, 25, 650, 155)`, on demand | Parses `Path N`; Path and Cycle are synonyms for this user. |

The active non-secret configuration is `%APPDATA%\FortniteVision\config.json`.
Do not put its Telegram chat ID, or any Telegram bot token, in source, docs, test
fixtures, or commits.

## Game Mechanics Captured By The Build

### Droid Spawn Feed

- Up to six lines can appear and scroll upward as newer entries replace older
  ones.
- The expected form is similar to `Rainbow Droid (Common) spawned at the
  Sandcrawler`.
- Parser `droid_monitor/domain.py` accepts only the Sandcrawler spawn wording,
  avoiding ordinary chat/UI text.
- OCR can read `Galactic` as `Galatic` and can lose part of `Rainbow`; those
  known variations are tolerated.
- Keep the feed OCR color-aware. Earlier black-and-white preprocessing risked
  misses because material and rarity colors are useful signal.

### Alert Rules

Keep this requested UI order and current emojis intact:

1. Stellar Mythic
2. Stellar Legendary
3. Stellar Epic
4. Galactic Mythic
5. Galactic Legendary
6. Galactic Epic
7. Beskar Mythic
8. Beskar Legendary
9. Beskar Epic
10. Rainbow Mythic
11. Rainbow Legendary
12. Rainbow Epic
13. Diamond Mythic
14. Diamond Legendary

The legacy internal IDs use `galatic_*`, while labels correctly say `Galactic`.
Stellar uses `stellar_*` IDs and is recognized by Test Mode at every rarity; its
alert rules cover Epic, Legendary, and Mythic. Existing saved profiles are
upgraded once to enable all three Stellar alert rules without changing their
other selections. The Rebirth OCR vocabulary recognizes Stellar requirement
cards, but the Roller Planner has no Stellar requirements until an authoritative
Path/Cycle sheet is supplied.
Do not rename those IDs without migrating the persisted user config.

Test Mode logs every successfully recognized material/rarity spawn, including
unselected rules. It is a calibration aid, not a raw OCR trace.

### Jawa Droid Announcement

The Jawa announcement is a visual toast. The recycle logo is a more reliable
cue than OCR text, so `droid_monitor/jawa.py` uses multi-scale template matching
against `droid_monitor/assets/jawa_reference.png`.

- Alert threshold: `0.62`.
- Near-match QA threshold: `0.35`; at most one near-match image every 120 s.
- The detector is edge-triggered: a long-lived toast alerts once, then must
  disappear before a later toast can alert.
- Review QA crops before lowering its threshold after a miss or false positive.

### Ready For Rebirth

`droid_monitor/rebirth.py` template-matches the bottom-center green recycle and
`READY!` badge using `assets/rebirth_ready_reference.png`.

- Current threshold: `0.70`.
- Checks no more than once every four seconds to protect CPU.
- It is edge-triggered and releases only after the score falls sufficiently.
- The gold active `REBIRTH` button on the open menu confirms readiness, but is
  not a separate continuous detector yet.

### Rebirth Screen, HUD, And Storage

The `NEED` section of the open Rebirth screen has four cards: Credits plus three
droid requirements. Green borders/checks mean satisfied; red borders/crosses
mean missing. `rebirth_progress.py` reads card colors through HSV pixel counts,
then maps cards two through four to droids.

The lower-left HUD reader expects, in display order:

1. Credits, for example `4.60T`.
2. Upgrade Chips, for example `93.96K`.
3. Nova Crystals, for example `54`.
4. Rebirth level, for example `21`.

It scans every 15 seconds only while monitoring. A successful parse persists in
`%APPDATA%\FortniteVision\runtime\rebirth_progress.json`. The UI now displays
the last successful HUD timestamp; a manual panel sync does not stop this timer.

The parser was validated using `Rebirth Requirements..png`:

- Path 2, Rank 25, `13.50T`;
- Mono-WLKR Beskar ready;
- RIC-1200 Default ready;
- TRI-TEK Gold missing.

`rebirth ready screen.png` validates the all-green state and the active gold
Rebirth button.

Planning assumptions, cross-checked against community documentation:

- Required droids must be active on the base; the lounge/storage area counts.
- A higher-quality version of a named droid can satisfy a lower-quality
  requirement.
- Credits reset after Rebirth.
- Paths/Cycles rotate in order 1, 2, 3, 4, then 1 again.

The live Rebirth screen always wins if it disagrees with static planner data.
Sources are community references, not a game API:

- [Rebirth mechanics](https://star-wars-droid-tycoon.fandom.com/wiki/Rebirths)
- [Cycle guide](https://www.reddit.com/r/StarWarsDroidTycoon/comments/1ukoece/super_rebirth_full_requirement_guide_with/)
- [Path 3/4 patch note](https://www.reddit.com/r/StarWarsDroidTycoon/comments/1ugy4z3/star_wars_droid_tycoon_v119_patch_notes/)

## Rebirth Roller Planner

`droid_monitor/rebirth_roadmap.py` is a curated static roadmap for ranks 21-30
in all four Paths. It was transcribed and OCR-checked from user-provided
`RBC1.png`, `RBC2.png`, `RBC3.png`, and `RBC4.png` sheets (4688x6473 each).

After a live panel sync, the planner:

1. Lists the next four Rebirth targets after the current target for proactive
   roller buys.
2. Searches the remaining ranks in the current Path for each current required
   droid. It tells the user to Store or Upgrade a droid that returns later.
3. Says a droid has no later requirement in the current Path when it does not
   return. This is deliberately not an unconditional global sell claim.

Quality order used for future requirements:

`Default < Gold < Diamond < Rainbow < Beskar < Galactic`

`Common < Rare < Epic < Legendary < Mythic`

### Current Path 2 Example

The persisted test snapshot is Path 2, target Rank 26:

| Rank | Credits | Droids |
| --- | --- | --- |
| 26 | 21T | KX Gold Mythic; DRFT-R Diamond Mythic; IG Rainbow Mythic |
| 27 | 32T | LEP Diamond Mythic; Loadlifter Rainbow Mythic; MO-TRAK Beskar Mythic |
| 28 | 45T | Snow Mouse Rainbow Mythic; TRI-TEK Beskar Mythic; Mecha-Droid Galactic Legendary |
| 29 | 68T | RIC Beskar Mythic; Cyclo-Grav Galactic Legendary; R7 Galactic Legendary |
| 30 | 100T | KX Beskar Mythic; OPTI-STRK Galactic Legendary; DRFT-R Galactic Mythic |

So Rank 26 advice is:

- Upgrade and retain KX for Beskar Mythic at Rank 30.
- Upgrade and retain DRFT-R for Galactic Mythic at Rank 30.
- IG Rainbow Mythic has no later Path 2 requirement after Rank 26.

The static roadmap deliberately starts at rank 21. It does not scan player
inventory and cannot claim that any droid is safe after a later reset or path.

## Architecture

| Area | File | Responsibility |
| --- | --- | --- |
| UI | `droid_monitor/app.py` | PyQt6 navigation, Live/Rebirth/Alerts/Setup, tray, config controls, Telegram UI. |
| Worker | `droid_monitor/monitor.py` | Background capture/OCR/template loop, cooldowns, QA saves, manual Rebirth capture. |
| Capture | `droid_monitor/capture.py` | `mss` monitor listing and physical-pixel crops. |
| OCR | `droid_monitor/ocr.py` | Local RapidOCR/ONNX Runtime plus RGB 3x preprocessing. |
| Spawn rules | `droid_monitor/domain.py` | Sandcrawler extraction, material/rarity parsing, ordered alert rules. |
| CPU gating | `droid_monitor/efficiency.py` | Observe/shadow-adaptive/adaptive/full feed modes and performance summaries. |
| Visual detectors | `jawa.py`, `rebirth.py` | Multi-scale template matching for Jawa and Ready badge. |
| Rebirth data | `rebirth_progress.py`, `rebirth_roadmap.py` | HUD/panel parsing, snapshots, roadmap and hold advice. |
| Notifications | `notifications.py` | Telegram queue, connection reuse, secure token storage, chat discovery. |
| QA | `qa.py` | Timestamped raw evidence images, newest 250 retained. |
| Settings | `config.py` | Typed settings, defaults, validation, JSON persistence. |

### Worker Loop And Costs

One shared `RapidOcrEngine` runs in `MonitorWorker`. Each cycle:

1. Checks Ready badge if due.
2. Checks Rebirth HUD if due.
3. Checks Jawa toast when enabled.
4. Captures the spawn feed and runs the configured OCR mode.
5. Parses, deduplicates, alerts, and saves evidence asynchronously.
6. Processes an explicit open-Rebirth-screen capture request.
7. Waits for the feed interval.

Spawn feed CPU modes:

- `Observe + Shadow Adaptive` is the recommended/default mode. It performs full
  OCR every scan while simulating Adaptive's actual gate and safety-refresh schedule.
  It reports reference versus shadow recognized spawns/selected alerts, delays, and
  misses without sending duplicate notifications. A selected-alert shadow miss saves
  a QA image for review.
- `Adaptive` skips unchanged OCR but has a six-second full-OCR safety refresh.
- `Full OCR every scan` bypasses gating.

Do not lower the user scan interval by default. A lower-scan experiment created
unnecessary CPU load and was intentionally reverted.

## Alerts, Evidence, And Telegram

- Normalized event cooldown: 45 seconds.
- Tray notification duration: 10 seconds.
- QA captures: `%APPDATA%\FortniteVision\runtime\qa_captures`, newest 250 kept.
- Activity log: `%APPDATA%\FortniteVision\runtime\droid_history.txt`.
- Live view retains three rows; Alerts history retains 40 readable rows with
  source, timestamp, event, and an evidence button.

Telegram uses a background queue and reuses a healthy HTTPS connection for up to
60 seconds, helping avoid the old multi-second send delay. The request timeout is
eight seconds and queue/request durations are logged separately.

The token is stored only in Windows Credential Manager under:

`FortniteVision` / `telegram_bot_token`

The non-secret config stores only the enabled flag and chat ID. Private-chat
discovery requires the user to send the bot `/start`, then use `Find recent chat`.
HTTP 400 usually means an invalid destination/token or a bot that cannot message
that chat. Never expose the token in logs, docs, tests, or source control.

## UI Decisions

Navigation order: Live, Rebirth, Alerts, Setup.

The app should feel like a compact consumer companion, not an operator console.
Preserve the dark neutral palette, dense readability, modest 6-8 px radii, and
clear visual hierarchy.

- The `Watching for` selector is intentionally compact and vertically scrollable.
- Alert history is intentionally roomy enough for date, source, event text, and
  evidence without overlapping rows.
- Always on top uses native Windows `SetWindowPos`. Do not return to Qt window
  flag recreation; it previously crashed the app.
- The Rebirth page is vertically scrollable only. Current requirements come
  first, then roller planning, then the three status cards.
- Existing alert emojis are requested UI choices; retain them.

## Files And Launch

| Location | Contents |
| --- | --- |
| `%APPDATA%\FortniteVision\config.json` | Crops, modes, selected rules, Telegram flag/chat ID. |
| `%APPDATA%\FortniteVision\runtime\rebirth_progress.json` | Last HUD and requirement snapshots. |
| `%APPDATA%\FortniteVision\runtime\droid_history.txt` | Local activity history. |
| `%APPDATA%\FortniteVision\runtime\qa_captures` | Evidence and near-match images. |
| Windows Credential Manager | Telegram token only. |

The everyday launcher is the `FortniteVision` desktop shortcut, which calls
`scripts\Launch-FortniteVision.cmd`. Use `scripts\Start-FortniteVision.ps1` only
to create or repair `.venv` and reinstall editable dependencies.

On this machine, bare `python` may resolve to the Microsoft Store stub. Use the
project interpreter for development:

```powershell
.\.venv\Scripts\python.exe -m compileall droid_monitor tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

At the time of this document, 43 tests pass. They cover config, parsing, rules,
CPU gating, visual detectors, Telegram transport, QA saves, Rebirth snapshots,
and the Path 2 planner example. They do not prove that a future game patch still
matches stored crops or visual templates.

## Reference Images

User-provided Desktop images established the current implementation:

| File | Use |
| --- | --- |
| `Screenshot 2026-07-18 160144.png` | Spawn feed and original Jawa placement. |
| `Jawa.png` | Recycle-symbol reference. |
| `rebirth ready.png` | Lower-left HUD and Ready badge placement. |
| `Rebirth Requirements..png` | Rebirth red/green card parser validation. |
| `rebirth ready screen.png` | All-green requirement and gold button state. |
| `RBC1.png` through `RBC4.png` | Four Path/Cycle requirement sheets. |

The Desktop copies are documentation/calibration sources, not application assets.
Runtime visual references live in `droid_monitor/assets`.

## Known Limitations And Future Work

1. The static roadmap covers ranks 21-30 only. Add ranks 1-20 only after a
   source-validation pass against the current game.
2. Planner guidance is Path-scoped and does not know the complete player
   inventory. It must not make blanket sell claims across a reset or another Path.
3. The active gold button could become a panel-sync-only confirmation state;
   avoid turning it into a continuous large-crop monitor.
4. Rebirth crops assume this 3840x2160 layout. Recalibrate after resolution,
   display-scaling, HUD-placement, or game UI changes.
5. Jawa misses/false positives should be investigated through saved QA evidence,
   not threshold changes by guesswork.
6. No standalone `.exe` package is maintained. The shortcut and `.venv` are the
   supported launch path.

## Future Session Rules

- Read this document, the live config, and recent QA images before retuning.
- Preserve the read-only game boundary and existing user settings.
- Reuse the worker's OCR engine; do not create extra model sessions casually.
- Keep independent monitors independently throttled.
- Prefer snapshots/on-demand OCR for larger panels rather than continuous scans.
- Add focused tests for parser, threshold, roadmap, or persisted-config changes.
- Treat the open live Rebirth panel as the final authority after a game update.
