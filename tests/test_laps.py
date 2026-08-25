from gt7coach.laps import LapBoundary, extract_lap_boundaries


def frame(seq, lap, ts=None, last_lap_ms=-1):
    return {
        "seq": seq,
        "ts_ns": seq * 1_000_000 if ts is None else ts,
        "lap": lap,
        "last_lap_ms": last_lap_ms,
    }


def test_extracts_only_consecutive_complete_lap():
    rows = [
        frame(10, 0),
        frame(20, 1),
        frame(30, 1),
        frame(40, 2, last_lap_ms=439208),
        frame(50, 2, last_lap_ms=439208),
        frame(60, -1, last_lap_ms=439208),
    ]

    assert extract_lap_boundaries(rows) == [
        LapBoundary(
            lap=1,
            start_seq=20,
            end_seq=40,
            start_ts_ns=20_000_000,
            end_ts_ns=40_000_000,
            lap_time_ms=439208,
        )
    ]


def test_ignores_aborted_lap_and_nonconsecutive_finish():
    rows = [
        frame(0, 0),
        frame(1, 1),
        frame(2, 0),
        frame(3, 1),
        frame(4, 2, last_lap_ms=443413),
        frame(5, -1, last_lap_ms=443413),
    ]

    boundaries = extract_lap_boundaries(rows)
    assert len(boundaries) == 1
    assert boundaries[0].start_seq == 3
    assert boundaries[0].end_seq == 4
    assert boundaries[0].lap_time_ms == 443413


def test_requires_positive_lap_time_on_finish_transition():
    rows = [frame(0, 0), frame(1, 1), frame(2, 2)]
    assert extract_lap_boundaries(rows) == []
