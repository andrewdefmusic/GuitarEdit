"""Command line: python -m guitaredit analyze ..."""

from __future__ import annotations

import argparse
import json
import sys

from .analyze import Options, analyze
from .audio import load_mono
from .report import render
from .session_text import parse_session_text, parse_time


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="guitaredit")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="measure the editing style of one edited DI track")
    a.add_argument("--raw", required=True, help="unedited DI audio file")
    a.add_argument("--edited", required=True, help="edited DI, consolidated from the same start")
    a.add_argument("--session", required=True, help="Session Info as Text export (Samples or Min:Secs)")
    a.add_argument("--track", required=True, help="name of the edited track in the session text")
    a.add_argument(
        "--start", default="0",
        help="session position where both audio files start (samples or M:SS.sss, default 0)",
    )
    a.add_argument("--bpm", type=float, help="song tempo, enables tightening strength")
    a.add_argument("--grid", type=int, default=16, help="grid subdivision, e.g. 16 for 1/16 notes")
    a.add_argument("--json", help="also write the style profile to this file")
    args = p.parse_args(argv)

    with open(args.session, encoding="utf-8", errors="replace") as f:
        session = parse_session_text(f.read())
    if args.track not in session.tracks:
        names = ", ".join(session.tracks) or "none"
        print(f"Track {args.track!r} not found. Tracks: {names}", file=sys.stderr)
        return 2

    raw, sr = load_mono(args.raw)
    edited, sr2 = load_mono(args.edited)
    if sr != sr2:
        print("Raw and edited files must share a sample rate.", file=sys.stderr)
        return 2
    origin = parse_time(args.start, sr)
    clips = session.tracks[args.track]
    for c in clips:
        c.start -= origin
        c.end -= origin

    profile = analyze(raw, edited, sr, clips, Options(bpm=args.bpm, grid=args.grid))
    print(render(profile))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(profile, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
