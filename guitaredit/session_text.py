"""Parse the track listing from a Pro Tools "Export Session Info as Text" file.

Export with Time Format set to Samples (preferred) or Min:Secs. Only the
track listing section is read; each track becomes a list of clips with
start/end positions in samples.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Clip:
    event: int
    name: str
    start: int  # samples
    end: int  # samples
    muted: bool = False


@dataclass
class Session:
    name: str = ""
    sample_rate: float = 48000.0
    tracks: dict[str, list[Clip]] = field(default_factory=dict)


_MINSEC = re.compile(r"^(\d+):(\d+(?:\.\d+)?)$")


def parse_time(text: str, sample_rate: float) -> int:
    text = text.strip()
    if text.isdigit():
        return int(text)
    m = _MINSEC.match(text)
    if m:
        seconds = int(m.group(1)) * 60 + float(m.group(2))
        return round(seconds * sample_rate)
    raise ValueError(
        f"Unsupported time format {text!r}. Export the session text with "
        "Time Format set to Samples or Min:Secs."
    )


def parse_session_text(text: str) -> Session:
    session = Session()
    lines = text.splitlines()
    for line in lines:
        key, _, value = line.partition(":")
        key = key.strip().upper()
        if key == "SESSION NAME":
            session.name = value.strip()
        elif key == "SAMPLE RATE":
            session.sample_rate = float(value.strip())

    track = None
    in_clips = False
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("TRACK NAME:"):
            track = stripped.split(":", 1)[1].strip()
            session.tracks[track] = []
            in_clips = False
            continue
        if track is None:
            continue
        cols = [c.strip() for c in line.split("\t")]
        if cols and cols[0].upper() == "CHANNEL":
            in_clips = True
            continue
        if not stripped:
            in_clips = False
            continue
        if in_clips and len(cols) >= 6 and cols[0].isdigit():
            # CHANNEL, EVENT, CLIP NAME, START TIME, END TIME, DURATION, [STATE]
            channel = int(cols[0])
            if channel != 1:
                continue  # stereo tracks repeat each clip per channel
            if cols[2].startswith("(") and "fade" in cols[2].lower():
                continue  # fade rows appear when "Show Crossfades" is ticked
            state = cols[6] if len(cols) > 6 else ""
            session.tracks[track].append(
                Clip(
                    event=int(cols[1]),
                    name=cols[2],
                    start=parse_time(cols[3], session.sample_rate),
                    end=parse_time(cols[4], session.sample_rate),
                    muted=state.lower() == "muted",
                )
            )
    return session
