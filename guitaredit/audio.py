"""Audio helpers: loading, RMS envelopes and pick-attack (onset) detection."""

from __future__ import annotations

import numpy as np
import soundfile as sf


def load_mono(path: str) -> tuple[np.ndarray, int]:
    data, sr = sf.read(path, dtype="float64", always_2d=True)
    return data.mean(axis=1), sr


def rms_frames(x: np.ndarray, hop: int) -> np.ndarray:
    """RMS of consecutive non-overlapping frames of length `hop`."""
    n = len(x) // hop
    if n == 0:
        return np.zeros(0)
    frames = x[: n * hop].reshape(n, hop)
    return np.sqrt((frames**2).mean(axis=1))


def db(x: np.ndarray | float, floor: float = 1e-9) -> np.ndarray:
    return 20 * np.log10(np.maximum(x, floor))


def detect_onsets(
    x: np.ndarray,
    sr: int,
    hop: int = 64,
    rise_db: float = 9.0,
    min_gap_ms: float = 60.0,
    floor_db: float = -60.0,
) -> np.ndarray:
    """Return onset positions in samples.

    A guitar DI pick attack is a sharp rise in broadband energy. We take the
    RMS envelope of a first-difference (high-passed) signal and mark frames
    whose level jumps by `rise_db` over the minimum of the preceding ~10 ms.
    Each onset is then refined to the sample where the attack crosses 30%
    of its local peak.
    """
    hp = np.diff(x, prepend=x[:1])
    # energy smoothed over ~4 ms so low strings don't flicker between frames
    width = max(hop, int(0.004 * sr))
    smooth = np.convolve(hp**2, np.ones(width) / width, mode="full")[: len(hp)]
    env = db(np.sqrt(smooth[hop - 1 :: hop]))
    look = max(1, int(0.010 * sr / hop))
    min_gap = int(min_gap_ms / 1000 * sr / hop)
    onsets = []
    last = -min_gap
    for i in range(look, len(env)):
        if env[i] < floor_db:
            continue
        if env[i] - env[i - look : i].min() >= rise_db and i - last >= min_gap:
            onsets.append(_refine(hp, i * hop, hop))
            last = i
    return np.array(onsets, dtype=np.int64)


def _refine(hp: np.ndarray, pos: int, hop: int) -> int:
    lo = max(0, pos - 2 * hop)
    hi = min(len(hp), pos + 3 * hop)
    seg = np.abs(hp[lo:hi])
    if len(seg) == 0 or seg.max() == 0:
        return pos
    above = np.nonzero(seg >= 0.3 * seg.max())[0]
    return lo + int(above[0])
