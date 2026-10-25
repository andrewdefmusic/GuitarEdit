import pytest

from guitaredit.session_text import parse_session_text, parse_time

SAMPLE = """SESSION NAME:\tSong 1
SAMPLE RATE:\t44100.000000

T R A C K  L I S T I N G
TRACK NAME:\tGtr DI L
COMMENTS:\t
USER DELAY:\t0 Samples
STATE:
PLUG-INS:
CHANNEL \tEVENT   \tCLIP NAME                     \tSTART TIME    \tEND TIME      \tDURATION      \tSTATE
1       \t1       \tGtr DI L_01-01                \t0:01.000      \t0:01.500      \t0:00.500      \tUnmuted
1       \t2       \t(cross fade)                  \t0:01.499      \t0:01.501      \t0:00.002      \t
1       \t3       \tGtr DI L_01-02                \t0:01.500      \t0:02.250      \t0:00.750      \tMuted


TRACK NAME:\tGtr DI St
COMMENTS:\t
CHANNEL \tEVENT   \tCLIP NAME                     \tSTART TIME    \tEND TIME      \tDURATION      \tSTATE
1       \t1       \tGtr DI St_01                  \t100           \t200           \t100           \tUnmuted
2       \t1       \tGtr DI St_01                  \t100           \t200           \t100           \tUnmuted
"""


def test_parses_tracks_and_clips():
    s = parse_session_text(SAMPLE)
    assert s.name == "Song 1"
    assert s.sample_rate == 44100
    left = s.tracks["Gtr DI L"]
    assert [(c.start, c.end, c.muted) for c in left] == [(44100, 66150, False), (66150, 99225, True)]
    assert len(s.tracks["Gtr DI St"]) == 1  # second channel of a stereo clip is skipped


def test_rejects_timecode():
    with pytest.raises(ValueError, match="Samples"):
        parse_time("01:00:00:00", 48000)
