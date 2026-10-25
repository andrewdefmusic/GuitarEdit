"""Synthetic guitar DI plus an edit with known settings, for testing the analyzer."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from guitaredit.session_text import Clip


@dataclass
class EditStyle:
    pre_attack_ms: float = 10.0
    fade_in_ms: float = 3.0
    fade_out_ms: float = 25.0
    crossfade_ms: float = 4.0
    strength: float = 0.8
    tolerance_ms: float = 2.0
    tail_ms: float = 520.0


@dataclass
class Synth:
    sr: int
    bpm: float
    raw: np.ndarray
    edited: np.ndarray
    clips: list[Clip]
    onsets: list[int]
    shifts: list[int] = field(default_factory=list)


def pluck(sr, f0, length, rng):
    t = np.arange(length) / sr
    tone = sum(np.sin(2 * np.pi * f0 * h * t + rng.uniform(0, 6)) / h for h in range(1, 7))
    attack = np.minimum(1.0, t / 0.001)
    return 0.4 * tone * attack * np.exp(-t / 0.25)


def make(style: EditStyle | None = None, seed: int = 1, sr: int = 48000, bpm: float = 120.0) -> Synth:
    style = style or EditStyle()
    rng = np.random.default_rng(seed)
    sixteenth = 60 / bpm / 4 * sr
    jitter = int(0.012 * sr)
    phrases = 4
    notes_per_phrase = 6
    length = int(sixteenth * (phrases * 16 + 8))
    raw = rng.normal(0, 10 ** (-70 / 20), length)
    raw += 10 ** (-60 / 20) * np.sin(2 * np.pi * 60 * np.arange(length) / sr)

    onsets, phrase_of = [], []
    for p in range(phrases):
        base = 4 + p * 16
        for n in range(notes_per_phrase):
            grid_pos = int((base + 2 * n) * sixteenth)
            onsets.append(grid_pos + int(rng.integers(-jitter, jitter + 1)))
            phrase_of.append(p)
        # a squeak in the rest after each phrase
        sq = int((base + 14.6) * sixteenth)
        burst = rng.normal(0, 10 ** (-40 / 20), int(0.03 * sr)) * np.hanning(int(0.03 * sr))
        raw[sq : sq + len(burst)] += burst

    for i, o in enumerate(onsets):
        nxt = onsets[i + 1] if i + 1 < len(onsets) and phrase_of[i + 1] == phrase_of[i] else o + int(0.5 * sr)
        note = pluck(sr, rng.uniform(82, 330), nxt - o, rng)
        mute = min(len(note), int(0.02 * sr))
        note[-mute:] *= np.linspace(1, 0, mute)  # player mutes the string
        raw[o:nxt] += note

    pre = int(style.pre_attack_ms / 1000 * sr)
    tol = style.tolerance_ms / 1000 * sr
    shifts = []
    for o in onsets:
        dev = o - round(o / sixteenth) * sixteenth
        shifts.append(0 if abs(dev) <= tol else int(round(-dev * style.strength)))

    # clip boundaries on the edited timeline
    clips, segments = [], []
    for i, (o, s) in enumerate(zip(onsets, shifts)):
        start = o - pre + s
        last_in_phrase = i + 1 == len(onsets) or phrase_of[i + 1] != phrase_of[i]
        end = o + s + int(style.tail_ms / 1000 * sr) if last_in_phrase else onsets[i + 1] - pre + shifts[i + 1]
        clips.append(Clip(event=i + 1, name=f"Gtr DI_{i + 1:02d}", start=start, end=end))
        segments.append((start, end, s, last_in_phrase))

    edited = np.zeros(length)
    t = np.arange(length)
    xf = int(style.crossfade_ms / 1000 * sr)
    fin = int(style.fade_in_ms / 1000 * sr)
    fout = int(style.fade_out_ms / 1000 * sr)
    for i, (start, end, s, last) in enumerate(segments):
        first = i == 0 or segments[i - 1][3]
        gain = np.zeros(length)
        lo = start if first else start - xf // 2
        hi = end if last else end + xf // 2
        gain[lo:hi] = 1.0
        if first:
            gain[start : start + fin] = np.linspace(0, 1, fin, endpoint=False)
        else:
            gain[lo : lo + xf] = np.linspace(0, 1, xf, endpoint=False)
        if last:
            gain[end - fout : end] = np.linspace(1, 0, fout, endpoint=False)
        else:
            gain[hi - xf : hi] = np.linspace(1, 0, xf, endpoint=False)
        src = np.clip(t - s, 0, length - 1)
        edited += gain * raw[src]

    return Synth(sr=sr, bpm=bpm, raw=raw, edited=edited, clips=clips, onsets=onsets, shifts=shifts)


def session_text(synth: Synth, track: str = "Gtr DI") -> str:
    lines = [
        "SESSION NAME:\tSynthetic",
        f"SAMPLE RATE:\t{synth.sr:.6f}",
        "BIT DEPTH:\t24-bit",
        "TIME CODE FORMAT:\t30 Frame",
        "",
        "T R A C K  L I S T I N G",
        f"TRACK NAME:\t{track}",
        "COMMENTS:\t",
        "USER DELAY:\t0 Samples",
        "STATE: ",
        "PLUG-INS: ",
        "CHANNEL \tEVENT   \tCLIP NAME                     \tSTART TIME    \tEND TIME      \tDURATION      \tSTATE",
    ]
    for c in synth.clips:
        lines.append(f"1       \t{c.event}       \t{c.name}\t{c.start}\t{c.end}\t{c.end - c.start}\tUnmuted")
    lines.append("")
    return "\n".join(lines)
