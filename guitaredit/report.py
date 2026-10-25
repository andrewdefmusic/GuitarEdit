"""Turn a style profile into a short plain-language report."""

from __future__ import annotations


def _rng(s: dict, unit: str = " ms") -> str:
    if not s or s.get("n", 0) == 0:
        return "not measured"
    return f"{s['median']}{unit} typical ({s['p10']} to {s['p90']}{unit}, {s['n']} measured)"


def render(profile: dict) -> str:
    t = profile["timing"]
    c = profile["cleanup"]
    lines = [
        f"Clips analysed: {profile['clips']} (pick attacks found in raw DI: {profile['onsets_detected']})",
        "",
        "Cuts",
        f"  Cut before the pick attack: {_rng(profile['cuts']['pre_attack_ms'])}",
        "",
        "Fades",
        f"  Fade-in length:  {_rng(profile['fade_in']['length_ms'])}",
        f"  Fade-in gain at midpoint: {_rng(profile['fade_in']['mid_gain'], '')}"
        "  (0.5 = linear, 0.71 = equal power)",
        f"  Fade-out length: {_rng(profile['fade_out']['length_ms'])}",
        f"  Crossfade length: {_rng(profile['crossfade']['length_ms'])}",
        f"  Crossfade centre vs edit point: {_rng(profile['crossfade']['centre_ms'])}",
        "",
        "Timing",
        f"  Clips moved: {t['moved_clips']} of {profile['clips']}",
        f"  Distance moved: {_rng(t['shift_ms'])}",
    ]
    if "strength" in t:
        lines += [
            f"  Grid: {t['grid']} at {t['bpm']} BPM",
            f"  Tightening strength (1 = fully on grid): {_rng(t['strength'], '')}",
            f"  Notes left alone were within: {t['left_alone_within_ms']} ms of the grid",
        ]
    lines += [
        "",
        "Cleanup",
        f"  Gaps cut between phrases: {c['gaps']}, length {_rng(c['gap_ms'])}",
        f"  Loudest thing removed in a gap: {_rng(c['removed_peak_db'], ' dBFS')}",
        f"  DI level where phrases are cut off: {_rng(c['level_at_phrase_end_db'], ' dBFS')}",
    ]
    return "\n".join(lines)
