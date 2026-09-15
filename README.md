# AVGME

A personal automation bot for **Last Asylum: Plague**, running against an Android
emulator on Windows. It takes over the two chores that cost the most time for the
least thought:

- **Collect** — tapping production badges as they pop over shelter buildings.
- **Scavenge** — claiming finished runs and sending the empty slots back out.

It drives the game's UI the way a finger would: screenshot in, tap out. It does
not touch the game's network protocol, its binaries, or any integrity check.

> **Read this before you run it.** Automation breaches 37Games' terms of service,
> and accounts do get actioned for it. That risk is yours to take. If you have an
> alt account, prove the setup out there first.

---

## How it works

```
adb screencap  ->  OpenCV template match  ->  adb input tap
```

The important part is the middle. Recorded macros (BlueStacks' built-in
recorder, and most of the paid bots) replay **fixed coordinates**, so the first
event popup that shifts the layout sends them tapping into whatever happens to
be underneath. This bot finds each button *by its appearance*, and every task
begins by proving the game is on the base screen — closing anything that isn't.
That's the difference between a script that runs for five minutes and one that
runs overnight.

---

## Setup (Windows)

**1. Python 3.10+** — from [python.org](https://www.python.org/downloads/),
ticking "Add Python to PATH".

**2. Android platform-tools** — download
[platform-tools for Windows](https://developer.android.com/tools/releases/platform-tools),
unzip it somewhere permanent (e.g. `C:\platform-tools`), and add that folder to
your PATH. Reopen your terminal, then check:

```
adb version
```

**3. The bot:**

```
git clone <this repo>
cd AVGME
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

**4. Your emulator** — enable ADB and lock the resolution.

| Emulator | Enable ADB | Default port |
|---|---|---|
| BlueStacks 5 | Settings → Advanced → Android Debug Bridge (it shows the port) | 5555 |
| LDPlayer | Settings → Other → ADB Debugging → Open local connection | 5555 / 5554 |
| MuMu Player | Settings → Other → ADB debugging | 7555 |

Set the emulator's display to **1600×900** (or 1920×1080 — just pick one and
never change it) and put the port in `config/tasks.yaml` under `adb:`.

Resolution matters more than it looks: templates are captured at one size and
matched 1:1. Resize the emulator and every template misses at once. `doctor`
checks this, and `run` refuses to start on a mismatch.

**5. Check everything:**

```
avgme doctor
```

---

## Teaching it to see

**This is the one step nobody can do for you.** Templates are crops from *your*
screen at *your* resolution, account level and language — they can't ship with
the repo. Budget twenty minutes for it once.

Get the game onto the home screen with some production badges showing, then:

```
avgme capture --name home
```

That writes a PNG into `captures/`. Cut templates out of it:

```
avgme crop captures\home-20260915-143022-00.png home/anchor_base
avgme crop captures\home-20260915-143022-00.png home/collect_food
avgme crop captures\home-20260915-143022-00.png home/scavenge_entry
```

Each opens a window: drag a box around the element, press ENTER.

Repeat with the scavenge menu open (`avgme capture --name scavenge`) for
`scavenge/anchor`, `scavenge/claim`, `scavenge/dispatch`, `scavenge/confirm`,
and with a popup open for `common/close_x`.

`templates/README.md` lists what each key is for and how to crop well. The short
version: **crop tight, avoid anything that animates or counts**.

Check what you've got:

```
avgme list-templates
avgme doctor
```

---

## Running it

**Always dry-run first.** It taps nothing, logs every tap it *would* make, and
writes an annotated screenshot to `debug/`:

```
avgme run --dry-run
```

Open that screenshot. Every green box must sit on the button you expect. If one
is on the wrong thing, recrop that template before going live — this is the
whole safety gate.

Then, watched, one task at a time:

```
avgme run --once --task collect
avgme run --once --task scavenge
```

Then let it loop:

```
avgme run
```

Ctrl-C stops it.

### Useful flags

| Command | Does |
|---|---|
| `avgme doctor` | Check adb, connection, resolution, templates |
| `avgme run --dry-run` | Taps nothing; annotates what it matched |
| `avgme run --once` | One pass of each task, then exit |
| `avgme run --task collect` | Just one task, ignoring its `enabled` flag |
| `avgme run -v` | Debug logging |

---

## Configuration

`config/tasks.yaml` holds policy — what runs, how often, how human it looks. No
coordinates: those all come from template matching.

Worth knowing about:

- `vision.default_threshold` (0.87) — raise it if a template matches the wrong
  button, lower it if a correct button isn't being found. A single template can
  override it via its filename: `claim@0.92.png`.
- `humanize.session` — alternates active and idle stretches so the bot isn't a
  24/7 metronome. Set `enabled: false` to run continuously.
- `tasks.*.interval_seconds` — jittered by `humanize.interval_jitter` so the
  same cycle never repeats to the second.

---

## When something breaks

**Look at `debug/` first.** Every failed cycle dumps an annotated screenshot of
exactly what the bot saw. It's almost always one of:

| Symptom | Cause | Fix |
|---|---|---|
| Everything stops matching at once | Emulator resized | Restore the resolution, or recapture |
| One button stopped matching | Game update restyled it | Recrop that one template |
| Bot taps something wrong | Template too loose or too much background | Recrop tighter, or raise its threshold |
| "could not get back to the home screen" | A popup with an unfamiliar close button | Capture it as another `common/close_*` |

After any game patch, `avgme doctor` is the fast check.

---

## Adding tasks

Resource marches, rally joining, dailies and gift codes all fit the same shape.
A new task is a module in `src/avgme/tasks/`, a line in the registry in
`tasks/__init__.py`, and a block in `tasks.yaml` — no changes anywhere else.

Marches and rallies need world-map navigation and commit your troops, which is
why they're deliberately behind the two base-screen loops.

## Tests

```
pip install pytest
pytest
```

The suite runs the full task logic — taps, re-screencapping, popup recovery,
giving up — against a fake emulator, so the game doesn't need to be running.
