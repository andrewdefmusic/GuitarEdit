# GuitarEdit

Learns how you edit guitar DIs in Pro Tools (tightening, fades, cleanup) so the
same style can be applied to other sessions.

This first milestone is a read-only **style report**: give it the raw DI, your
edited DI and the session's clip list, and it measures your habits. Nothing is
written back to Pro Tools yet.

## What it measures

| Habit | Measurement |
| --- | --- |
| Cuts | How far before the pick attack each clip starts |
| Fades | Fade-in and fade-out length at phrase edges, and their shape (linear vs equal power) |
| Crossfades | Length and position of crossfades on butted edits |
| Tightening | How far clips were moved, how strongly toward the grid, and how far off a note can be before you move it |
| Cleanup | Gaps cut between phrases, the loudest noise you removed, and how quiet the DI is where you cut a phrase off |

## Exporting from Pro Tools

Pick a range that both exports will share, for example from a marker at the
start of the song to the end. Note its start position in **Samples**.

1. **Raw DI.** On the unedited playlist of the DI track, select the range and
   consolidate it (Edit > Consolidate Clip), then export the clip as a mono WAV
   (Clip List > Export Clips as Files).
2. **Edited DI.** Duplicate the edited playlist, select the same range,
   consolidate (this renders your fades), and export it the same way.
3. **Clip list.** Undo the consolidate on the edited playlist (or switch back
   to it), then File > Export > Session Info as Text with "Include Track EDLs"
   ticked and Time Format set to **Samples**.

## Running it

```
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/guitaredit analyze \
  --raw raw.wav --edited edited.wav \
  --session session.txt --track "Gtr DI L" \
  --start 0 --bpm 120 --grid 16 --json profile.json
```

`--start` is the session position (samples or M:SS.sss) where both exports
begin. `--bpm` and `--grid` are optional; without them the report still shows
how far clips were moved but not how strongly they were pulled to the grid.
The song must be at one tempo for the grid numbers to be meaningful.

## Tests

```
.venv/bin/pytest
```

The tests build a synthetic DI, edit it with known settings (cut 12 ms before
the pick, 3 ms fade-ins, 25 ms fade-outs, 4 ms crossfades, 80% tightening) and
check the analyzer recovers them.

## Limits of this version

- Elastic Audio or warp edits are not detected; only clip moves are.
- Clip gain is not measured yet.
- Onset detection is accurate to about 3 ms on the synthetic audio; real DIs
  have sharper attacks, but this needs checking on your sessions.

## Plan

See the planning doc for the full roadmap: capture via PTSL, a multi-session
style profile, and applying the profile to new sessions.
