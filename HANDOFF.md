# Handoff — AVGME

Written at the end of a remote (cloud) session that had **no access to the
user's machine**. Everything below that is marked unverified is unverified for
that one reason: the game was never running anywhere this code could reach it.

If you are picking this up **with local machine access, you can finish it.**

---

## The goal

The user plays *Last Asylum: Plague* (37Games/Cloudwalker mobile 4X) on an
**Android emulator on Windows** and is spending too long on its repetitive loop.
They asked for a script to automate it. Scope agreed with them, in priority
order:

1. **Collect** — tap shelter production badges as they appear. *(built)*
2. **Scavenge** — claim finished runs, re-dispatch idle slots. *(built, see caveat)*
3. Later, explicitly deferred: resource marches, rally joining, dailies, gift codes.

They chose "build our own" over the paid bots (MuBots, Macro Automation Studio)
and over the emulator's built-in macro recorder.

### Scope boundary — do not widen this

This is a **UI-level macro on the user's own single account**: read the screen,
tap the screen. It does **not** touch the game's network protocol, its binaries,
or any integrity check, and it should not start to. The user was told plainly
that automation breaches 37Games' ToS and that accounts get actioned for it;
they accepted that risk. Don't re-litigate it, and don't build around it.

---

## State: code complete, never run against the game

Branch: `claude/hopeful-brahmagupta-2mwvqp` (pushed). The repo was empty before
this — everything is new. No PR has been opened.

```
src/avgme/
  adb.py       adb CLI wrapper: connect, screencap->ndarray, tap, swipe, back, resolution
  vision.py    template load/match/NMS/annotate
  state.py     at_home(), dismiss_popups(), recover_to_home()
  bot.py       what tasks are handed: screen in, jittered taps out; dry-run intercepts here
  humanize.py  tap jitter, gaussian delays, active/idle session cycling
  runner.py    interval scheduler; recovers to home *between* tasks
  config.py    yaml loader
  cli.py       doctor | capture | crop | list-templates | run
  tasks/
    base.py    Task ABC + TaskResult
    collect.py production badges
    scavenge.py claim + dispatch
config/tasks.yaml   policy only — intervals, thresholds, humanization. No coordinates.
templates/          EMPTY except READMEs. This is the blocker. See below.
tests/              28 tests, all passing, against a fake emulator
```

### Verified

- `pytest` — 28 passing. Covers task logic end to end via `tests/fake_adb.py`:
  collecting until clear, stopping when a popup swallows the home screen, the
  tap cap, scavenge claim/dispatch with and without a confirm step, recovery via
  close-button and via Back, and giving up cleanly.
- CLI runs; `doctor` exits 1 with a readable message when adb is missing.
- All modules import.

### NOT verified — the whole point of your session

- **Nothing has ever touched the real game.** Not one screenshot, not one tap.
- **No templates exist.** The bot is blind until they're created.
- **The scavenge flow is a guess.** It was modelled on genre convention
  (entry button → menu → `claim` on finished slots → `dispatch` on idle slots →
  optional `confirm`), not on the actual UI. If the real menu differs — paged
  slots, a different claim-all affordance, a slot detail screen — reshape
  `tasks/scavenge.py`. The state-driven structure should survive; the specific
  steps may not.
- Collect is much lower-risk: it's "tap every `home/collect*` match until none
  remain," which holds for almost any layout.

---

## Do this first

### 1. Environment

Python 3.10+, Android platform-tools on PATH, `pip install -e .`.
Emulator with ADB enabled, port in `config/tasks.yaml` (BlueStacks 5555,
LDPlayer 5555/5554, MuMu 7555).

**Lock the emulator resolution** to what's in `config/tasks.yaml`
(`expect_resolution`, currently `[1600, 900]`) and don't change it. Templates
match 1:1; a resize makes every one of them miss simultaneously. `doctor` checks
this and `run` refuses to start on a mismatch — that's deliberate, don't relax it.

```
avgme doctor
```

### 2. Create the templates — this is the real work

Nothing downstream functions until this exists. `templates/README.md` lists every
key, what it's for, and how to crop (tight; no timers, counts or animated parts).

```
avgme capture --name home        # game sitting on the base screen, badges showing
avgme crop captures\home-<stamp>.png home/anchor_base
avgme crop captures\home-<stamp>.png home/collect_food
avgme crop captures\home-<stamp>.png home/scavenge_entry
```

Then the same with the scavenge menu open, and with a popup open for
`common/close_x` (capture several close-button styles — recovery leans on them).

Required minimum: `home/anchor_*`, `home/collect_*`, `common/close_*`.
`doctor` names which are still missing.

Templates are keyed `subdir/stem`. A per-template threshold override goes in the
filename: `claim@0.92.png`.

### 3. Dry run — the safety gate

```
avgme run --dry-run
```

Taps nothing; logs every tap it *would* make and writes an annotated screenshot
to `debug/`. **Open it and confirm every green box sits on the intended button
before going live.** Recrop anything that's off.

### 4. Live, one task at a time, watched

```
avgme run --once --task collect
avgme run --once --task scavenge
avgme run                          # the loop
```

Watch ~30 min before leaving it unattended, checking the log for recovery events.

---

## Design decisions worth preserving

- **Template matching, never fixed coordinates.** This is the entire reason the
  project exists rather than using the emulator's macro recorder. Don't add
  hardcoded taps.
- **`recover_to_home()` runs before every task**, not just at startup. Unprompted
  popups (event ads, level-ups, daily login, alliance invites) are the #1 cause
  of macro failure; a popup during one task must not poison the next.
- **Re-screencap between taps** (see the comment in `tasks/collect.py`).
  Collecting shifts and spawns badges, so one `find_all()` followed by a burst of
  taps at stale coordinates is exactly the bug the design avoids.
- **Prefer a close button over Back.** Back can exit the game from the base
  screen. `dismiss_popups()` only falls back to Back when no X is visible.
- **Humanization is jitter, nothing more** — tap position within the matched box,
  gaussian delays, optional active/idle session cycling. Partly reliability
  (instant pixel-identical taps land mid-animation), partly not being an obvious
  metronome. It stops there, per the scope boundary above.
- **Tap caps and attempt limits everywhere.** A template that matches permanent
  scenery would otherwise loop forever; there's a test for this.

## Adding a task later

A module in `src/avgme/tasks/`, a line in `REGISTRY` in `tasks/__init__.py`, a
block in `tasks.yaml`. Nothing else changes. Marches and rallies need world-map
navigation and commit the user's troops, which is why they're behind the two
base-screen loops — get those solid first.

## Debugging

`debug/` first, always: every failed cycle dumps an annotated screenshot of what
the bot saw and matched. The README has a symptom→cause table. After any game
patch, `avgme doctor` is the fast check.
