"""Compare a raw guitar DI with its edited version and measure the editing style.

Inputs, all lined up to the same start position:
  * raw:    the unedited DI, exported from the original playlist
  * edited: the edited DI, consolidated or bounced from the same start
  * clips:  the edited track's clip list (from the session text export)

For each clip we estimate how far it was moved (tightening), where its cut
sits relative to the pick attack, the fades at its edges, and what was
removed in the gaps between clips (cleanup).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .audio import db, detect_onsets, rms_frames
from .session_text import Clip

BUTT_TOLERANCE_MS = 1.0


@dataclass
class Options:
    max_shift_ms: float = 60.0
    bpm: float | None = None
    grid: int = 16  # grid subdivision per whole note, e.g. 16 = sixteenth notes
    fade_window_ms: float = 150.0
    xfade_window_ms: float = 40.0
    hop: int = 32


def stats(values) -> dict:
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    if len(v) == 0:
        return {"n": 0}
    return {
        "n": int(len(v)),
        "p10": round(float(np.percentile(v, 10)), 2),
        "median": round(float(np.median(v)), 2),
        "p90": round(float(np.percentile(v, 90)), 2),
    }


def estimate_shift(raw, edited, start, end, max_shift, sr) -> int:
    """Samples the clip content was moved: edited[t] ~= raw[t - shift]."""
    margin = int(0.005 * sr)
    a = start + margin
    b = min(end - margin, a + int(1.5 * sr), len(edited))
    if b - a < int(0.01 * sr):
        return 0
    seg = edited[a:b]
    lo = a - max_shift
    ref = _slice(raw, lo, b + max_shift)
    n = len(ref) + len(seg)
    size = 1 << (n - 1).bit_length()
    corr = np.fft.irfft(np.fft.rfft(ref, size) * np.conj(np.fft.rfft(seg, size)), size)
    corr = corr[: 2 * max_shift + 1]
    k = int(np.argmax(corr))
    return max_shift - k


def _slice(x, a, b):
    """x[a:b] with zero padding outside the signal."""
    out = np.zeros(b - a)
    lo, hi = max(a, 0), min(b, len(x))
    if hi > lo:
        out[lo - a : hi - a] = x[lo:hi]
    return out


def _shifted(raw, shift, a, b):
    return _slice(raw, a - shift, b - shift)


def measure_fade(raw, edited, shift, edge, direction, window, hop):
    """Fade length (samples) and gain at its midpoint at a clip edge next to a gap.

    direction=+1 measures a fade-in starting at `edge`, -1 a fade-out ending there.
    """
    if direction > 0:
        a, b = edge, edge + window
    else:
        a, b = edge - window, edge
    e = rms_frames(_slice(edited, a, b), hop)
    r = rms_frames(_shifted(raw, shift, a, b), hop)
    ratio = np.where(r > 1e-7, e / np.maximum(r, 1e-12), np.nan)
    if direction < 0:
        ratio = ratio[::-1]
    full = np.nonzero(ratio >= 0.9)[0]
    if len(full) == 0:
        return None, None
    frames = int(full[0])
    # the 0.9 threshold catches ~90% of a fade's length
    length = frames * hop / 0.9
    mid = ratio[frames // 2] if frames >= 2 else None
    return length, (float(mid) if mid is not None and np.isfinite(mid) else None)


def measure_crossfade(raw, edited, shift_out, shift_in, boundary, window, hop):
    """Length and centre (relative to the edit point) of a crossfade, in samples.

    Within each short frame the edited audio is fitted as
    a * outgoing + b * incoming, where each is the raw DI at that clip's
    alignment. The crossfade spans the frames where neither gain is ~0 or ~1.
    """
    if shift_out == shift_in:
        return None, None
    a, b = boundary - window, boundary + window
    y = _slice(edited, a, b)
    x1 = _shifted(raw, shift_out, a, b)
    x2 = _shifted(raw, shift_in, a, b)
    n = len(y) // hop
    gains = []
    for i in range(n):
        s = slice(i * hop, (i + 1) * hop)
        m = np.stack([x1[s], x2[s]], axis=1)
        if np.linalg.cond(m) > 1e3 or np.abs(y[s]).max() < 1e-6:
            gains.append((np.nan, np.nan))
            continue
        w, *_ = np.linalg.lstsq(m, y[s], rcond=None)
        gains.append((w[0], w[1]))
    g = np.array(gains)
    mixing = np.nonzero((g[:, 1] > 0.1) & (g[:, 0] > 0.1))[0]
    if len(mixing) == 0:
        return 0, 0
    first, last = int(mixing[0]), int(mixing[-1]) + 1
    # both gains above 0.1 covers ~80% of a crossfade's length
    length = (last - first) * hop / 0.8
    centre = a + (first + last) * hop // 2 - boundary
    return length, centre


def analyze(raw, edited, sr, clips: list[Clip], opts: Options | None = None) -> dict:
    opts = opts or Options()
    clips = sorted((c for c in clips if not c.muted), key=lambda c: c.start)
    ms = 1000.0 / sr
    max_shift = int(opts.max_shift_ms / 1000 * sr)
    fade_window = int(opts.fade_window_ms / 1000 * sr)
    xfade_window = int(opts.xfade_window_ms / 1000 * sr)
    butt = BUTT_TOLERANCE_MS / 1000 * sr
    onsets = detect_onsets(raw, sr)

    shifts = [estimate_shift(raw, edited, c.start, c.end, max_shift, sr) for c in clips]

    pre_attack, fade_in, fade_in_mid, fade_out, fade_out_mid = [], [], [], [], []
    xfade_len, xfade_centre = [], []
    abs_shift, strength, unmoved_dev = [], [], []
    grid = 60.0 / opts.bpm * 4 / opts.grid * sr if opts.bpm else None

    for i, (clip, shift) in enumerate(zip(clips, shifts)):
        # where the cut sits relative to the nearest pick attack, in source time
        src = clip.start - shift
        near = onsets[np.abs(onsets - src) <= 0.1 * sr]
        onset = int(near[np.argmin(np.abs(near - src))]) if len(near) else None
        if onset is not None:
            pre_attack.append((onset - src) * ms)

        abs_shift.append(abs(shift) * ms)
        if grid and onset is not None:
            before = _grid_error(onset, grid)
            after = _grid_error(onset + shift, grid)
            if abs(shift) * ms < 0.5:
                unmoved_dev.append(abs(before) * ms)
            elif abs(before) > 0:
                strength.append(1 - abs(after) / abs(before))

        prev_end = clips[i - 1].end if i > 0 else None
        if prev_end is None or clip.start - prev_end > butt:
            length, mid = measure_fade(raw, edited, shift, clip.start, +1, fade_window, opts.hop)
            fade_in.append(None if length is None else length * ms)
            fade_in_mid.append(mid)
        else:
            length, centre = measure_crossfade(
                raw, edited, shifts[i - 1], shift, clip.start, xfade_window, opts.hop
            )
            if length is not None:
                xfade_len.append(length * ms)
                xfade_centre.append(centre * ms)

        next_start = clips[i + 1].start if i + 1 < len(clips) else None
        if next_start is None or next_start - clip.end > butt:
            length, mid = measure_fade(raw, edited, shift, clip.end, -1, fade_window, opts.hop)
            fade_out.append(None if length is None else length * ms)
            fade_out_mid.append(mid)

    cleanup = _cleanup(raw, sr, clips, shifts)

    timing = {"moved_clips": int(sum(1 for s in abs_shift if s >= 0.5)), "shift_ms": stats(abs_shift)}
    if grid:
        timing["bpm"] = opts.bpm
        timing["grid"] = f"1/{opts.grid}"
        timing["strength"] = stats(strength)
        timing["left_alone_within_ms"] = round(max(unmoved_dev), 2) if unmoved_dev else None

    return {
        "clips": len(clips),
        "onsets_detected": int(len(onsets)),
        "cuts": {"pre_attack_ms": stats(pre_attack)},
        "fade_in": {"length_ms": stats(fade_in), "mid_gain": stats(fade_in_mid)},
        "fade_out": {"length_ms": stats(fade_out), "mid_gain": stats(fade_out_mid)},
        "crossfade": {"length_ms": stats(xfade_len), "centre_ms": stats(xfade_centre)},
        "timing": timing,
        "cleanup": cleanup,
    }


def _grid_error(pos, grid):
    return pos - round(pos / grid) * grid


def _cleanup(raw, sr, clips, shifts):
    """What was removed between clips, and how quiet the DI was where you cut."""
    frame = int(0.010 * sr)
    gap_ms, removed_peak, cut_level = [], [], []
    for i in range(len(clips) - 1):
        a, b = clips[i].end, clips[i + 1].start
        if b - a <= BUTT_TOLERANCE_MS / 1000 * sr:
            continue
        gap_ms.append((b - a) * 1000 / sr)
        levels = rms_frames(raw[a:b], frame)
        if len(levels):
            removed_peak.append(float(db(levels.max())))
    for i, (clip, shift) in enumerate(zip(clips, shifts)):
        if i + 1 < len(clips) and clips[i + 1].start - clip.end <= BUTT_TOLERANCE_MS / 1000 * sr:
            continue  # only clips that end into a gap
        src_end = clip.end - shift
        tail = raw[max(0, src_end - frame) : src_end]
        if len(tail):
            cut_level.append(float(db(np.sqrt((tail**2).mean()))))
    return {
        "gaps": len(gap_ms),
        "gap_ms": stats(gap_ms),
        "removed_peak_db": stats(removed_peak),
        "level_at_phrase_end_db": stats(cut_level),
    }
