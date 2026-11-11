# High-Level Architecture

One package, two modes. Everything that is not mode-specific lives in a shared
backend; each mode supplies a profile, its own window layout, goal type and
CLI flow.

```
cube/
  core/       shared backend (capture, input, OCR, window analysis, controller)
  models/     shared domain models (StatLine, Equipment, Goal, stat parser)
  modes/
    cube/     potential mode: goal config, combination goals, presenter, flow
    flame/    flame mode: scorer, goal config, presenter, flow
  interface/  mode menu, base presenter, application wiring
  data/       per-mode JSON (cube/, flame/)
  res/        per-mode templates (cube/, flame/)
```

## Stats

There are 4 primary stats: STR, DEX, INT and LUK. "All Stats" means those four,
nothing else. All possible stats are listed per mode in
`data/cube/stats.json` and `data/flame/stats.json`.

## Item category

An item's possible stats depend on its category. The categories are defined in
`data/<mode>/item_category.json`.

## Item level and potential rank

Potential stat values depend on item level and on the item's potential rank.
A line rolls at the item's rank or one rank below.

- Level 71~150: legendary 12/9, unique 9/6, epic 6/3
- Level 151+: legendary 13/10, unique 10/7, epic 7/4

Only the 71~150 and 151+ ranges are currently supported.
Rare rank is not supported.

"All Stats" rolls one rank below the stated rank: level 151+ legendary
10/7, unique 7/4, epic 4.

## Core modules

- `core/capture_interface.py`, `core/d3dshot_capture.py` - screenshot provider.
- `core/io_interface.py` - re-exports the USB-loopback `KeySender`/`MouseSender`
  contracts so there is a single definition.
- `core/mouse.py` - cursor tracking and absolute clicks.
- `core/ocr.py` - `TesseractOCR` and `PaddleOCR` engines.
- `core/ocr_processor.py` - `OCRProcessor` ABC plus engine-tuned subclasses;
  image in, `Equipment` out.
- `core/window_analyzer.py` - anchor-based region detection. Offsets, template
  filenames and the match threshold come from a `WindowOffsets` value supplied
  by the mode.
- `core/template_matcher.py`, `core/window_pos.py` - OpenCV and Win32 helpers.
- `core/config_loader.py` - JSON loading for a mode's data directory.
- `core/mode_profile.py` - `ModeProfile`, the complete set of mode differences.
- `core/controller.py` - `Controller`, the single state machine.

## Mode packages

A mode supplies:

- `window_analyzer.py` - `WindowOffsets` (offsets, templates, threshold).
- `goal_config.py` - a `Goal` implementation with `is_met`, optional
  `prepare` and `describe_state`.
- `presenter.py` - mode-specific menus and session messages.
- `flow.py` - the interactive configuration steps that produce a goal.
- `profile.py` - `build_profile()` combining the above.

## Cube mode

Goals are built from rank thresholds plus stat-combination goals
(`SumGoal`, `LineCountGoal`, `AndGoal`,
`OrGoal`, and the dump-all fallback). 

OCR reads the rank and the stats regions.

An item has a max of 3 cube-able stat lines.

## Flame mode

Flames have no rank. Each line contributes to a single weighted score
(configured in `data/flame/flame_conversion.json`):

| Stat | Rate |
|---|---|
| Main stat (flat) | x1 |
| Secondary stat (flat) | /12 |
| All Stats % | x10 |
| Attack Power / Magic ATT | x3 |
| Boss Damage % / Damage % | x15 |
| Everything else | 0 |

The goal is either an absolute score or "better than the current score",
in which case the baseline is captured on the first read.


