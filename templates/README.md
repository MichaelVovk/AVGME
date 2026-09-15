# Templates

Every PNG in here is a crop from **your own screen at your own resolution**.
They cannot be shipped with the repo - the game's UI scales with resolution and
varies with account level, language and active events, so a template captured
elsewhere will not match.

Create them with:

```
avgme capture --name home        # line the game up first
avgme crop captures/home-....png home/anchor_base
```

Templates are keyed by `subdir/filename`, so `templates/home/claim.png` is
referenced in code as `home/claim`.

## What each one is for

| Key | Purpose |
|---|---|
| `home/anchor_*` | Proves the game is on the base screen. Pick something always visible there and nowhere else - the shelter nameplate or a permanent HUD button. **Not** a resource counter: the numbers change. |
| `home/collect_*` | The floating production badges. One PNG per badge type; the collect task taps every `home/collect*` match, so adding a resource type is dropping in a PNG. |
| `home/scavenge_entry` | The button that opens the scavenge menu from home. |
| `scavenge/anchor` | Proves the scavenge screen is open - its title bar works well. |
| `scavenge/claim` | The claim/collect button on a finished run. |
| `scavenge/dispatch` | The start/dispatch button on an idle slot. |
| `scavenge/confirm` | The confirm button in the dispatch dialog, if the game shows one. |
| `common/close_*` | Popup close buttons. Capture several - the game uses more than one X style, and recovery leans on these. |

## Cropping well

- **Tight.** Include the button's artwork, exclude background. Background is
  what changes between screens.
- **Avoid text that changes** - timers, counts, player names.
- **Avoid animated parts** - glows and pulses tank the match score.
- If one template needs a different threshold, put it in the filename:
  `claim@0.92.png` matches at 0.92 instead of the config default.
