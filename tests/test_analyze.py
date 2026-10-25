import numpy as np
import soundfile as sf

from guitaredit.__main__ import main
from guitaredit.analyze import Options, analyze
from guitaredit.audio import detect_onsets
from synth import EditStyle, make, session_text


def test_onsets_find_every_pick():
    s = make()
    found = detect_onsets(s.raw, s.sr)
    for o in s.onsets:
        assert np.min(np.abs(found - o)) < 0.003 * s.sr  # within 3 ms


def test_recovers_known_style():
    style = EditStyle(pre_attack_ms=12, fade_in_ms=3, fade_out_ms=25, crossfade_ms=4, strength=0.8)
    s = make(style)
    p = analyze(s.raw, s.edited, s.sr, s.clips, Options(bpm=s.bpm))

    assert abs(p["cuts"]["pre_attack_ms"]["median"] - 12) < 1.5
    assert abs(p["fade_in"]["length_ms"]["median"] - 3) < 1
    assert abs(p["fade_out"]["length_ms"]["median"] - 25) < 3
    assert abs(p["crossfade"]["length_ms"]["median"] - 4) < 1.5
    assert abs(p["crossfade"]["centre_ms"]["median"]) < 1
    assert abs(p["timing"]["strength"]["median"] - 0.8) < 0.1
    assert p["timing"]["left_alone_within_ms"] < 3
    assert p["cleanup"]["gaps"] == 3
    assert p["cleanup"]["removed_peak_db"]["median"] > -45


def test_shift_estimates_match():
    s = make(seed=3)
    p = analyze(s.raw, s.edited, s.sr, s.clips, Options(bpm=s.bpm))
    true = np.median(np.abs(s.shifts)) * 1000 / s.sr
    assert abs(p["timing"]["shift_ms"]["median"] - true) < 0.5


def test_cli_end_to_end(tmp_path, capsys):
    s = make()
    sf.write(tmp_path / "raw.wav", s.raw, s.sr, subtype="FLOAT")
    sf.write(tmp_path / "edited.wav", s.edited, s.sr, subtype="FLOAT")
    (tmp_path / "session.txt").write_text(session_text(s))
    code = main([
        "analyze", "--raw", str(tmp_path / "raw.wav"), "--edited", str(tmp_path / "edited.wav"),
        "--session", str(tmp_path / "session.txt"), "--track", "Gtr DI", "--bpm", "120",
        "--json", str(tmp_path / "profile.json"),
    ])
    assert code == 0
    assert "Tightening strength" in capsys.readouterr().out
    assert (tmp_path / "profile.json").exists()
