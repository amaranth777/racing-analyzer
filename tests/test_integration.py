import sqlite3
from pathlib import Path

from gt7coach.store import SCHEMA, session_analysis


def test_session_analysis_finds_completed_lap_and_segments(tmp_path):
    db = tmp_path / "lap.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 4, 4, 344, 1365, 0)")
    def row(seq, lap, x, speed, throttle=0.0, brake=0.0, last_lap_ms=-1):
        return (1, seq, seq, seq, lap, -1, last_lap_ms, 0, x, 0, 0, speed, 0, throttle, brake, 2, 0, 0.1, 0, 0, 0)
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 0, 0, 10), row(1, 1, 0, 10), row(2, 1, 100, 20, 1),
        row(3, 1, 200, 30, 0, 1), row(4, 2, 300, 10, last_lap_ms=439208),
    ])
    conn.commit(); conn.close()

    result = session_analysis(db, 1, segment_m=200)

    assert result["lap"] == 1
    assert result["frames"] == 3
    assert result["distance_m"] == 200.0
    assert result["segment_count"] == 1
    assert result["slowest_segments"][0]["sector"] == 0


def test_session_analysis_ignores_short_aborted_lap(tmp_path):
    db = tmp_path / "aborted.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 7, 7, 344, 1365, 0)")
    def row(seq, lap, x, last_lap_ms=-1):
        return (1, seq, seq, seq, lap, -1, last_lap_ms, 0, x, 0, 0, 10, 0, 0, 0, 2, 0, 0, 0, 0, 0)
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 0, 0), row(1, 1, 0), row(2, 0, 10),
        row(3, 1, 0), row(4, 1, 100), row(5, 1, 200), row(6, 2, 300, last_lap_ms=439208),
    ])
    conn.commit()
    conn.close()

    result = session_analysis(db, 1, segment_m=200)

    assert result["lap"] == 1
    assert result["frames"] == 3
    assert result["distance_m"] == 200.0
import sqlite3
from gt7coach.store import SCHEMA, session_analysis


def test_session_analysis_includes_conservative_events(tmp_path):
    db = tmp_path / "events.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 4, 4, 344, 1365, 0)")
    def row(seq, lap, x, speed, throttle=0.0, brake=0.0, last_lap_ms=-1):
        return (1, seq, seq * 100_000_000, seq, lap, -1, last_lap_ms, 0, x, 0, 0, speed, 0, throttle, brake, 2, 0, 0, 0, 0, 0)
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 0, 0, 10), row(1, 1, 0, 40), row(2, 1, 50, 35, brake=0.9),
        row(3, 1, 100, 30, brake=0.9), row(4, 1, 150, 25, brake=0.9),
        row(5, 1, 200, 22), row(6, 1, 300, 20), row(7, 1, 400, 18),
        row(8, 2, 500, 10, last_lap_ms=439208),
    ])
    conn.commit(); conn.close()

    result = session_analysis(db, 1, segment_m=200)

    assert [event["type"] for event in result["events"]] == ["heavy_braking"]
    assert result["events"][0]["from_m"] == 50.0
import sqlite3

from gt7coach.store import SCHEMA, session_comparison


def test_session_comparison_uses_complete_laps_only(tmp_path):
    db = tmp_path / "compare.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 8, 8, 344, 1365, 0)")
    def row(seq, lap, t_ns, x, last_lap_ms=-1):
        return (1, seq, t_ns, seq, lap, -1, last_lap_ms, 0, x, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0)
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 0, 0, 0),
        row(1, 1, 1_000_000_000, 0), row(2, 1, 2_000_000_000, 100),
        row(3, 1, 4_000_000_000, 200),
        row(4, 2, 5_000_000_000, 0, last_lap_ms=439208), row(5, 2, 6_000_000_000, 100),
        row(6, 2, 7_000_000_000, 200),
        row(7, 3, 8_000_000_000, 0, last_lap_ms=440000),
    ])
    conn.commit(); conn.close()

    result = session_comparison(db, 1, segment_m=200)

    assert [x["lap"] for x in result["laps"]] == [1, 2]
    assert result["best_lap"] == 2
    assert result["theoretical_best_s"] == 2.0
import sqlite3
import pytest

from gt7coach.store import SCHEMA, session_comparison


def test_comparison_rejects_aborted_lap_as_real_lap(tmp_path):
    db = tmp_path / "real-shape.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 9, 9, 344, 1365, 0)")
    def row(seq, lap, t_ns, x, last_lap_ms=-1):
        return (1, seq, t_ns, seq, lap, -1, last_lap_ms, 0, x, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0)
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 0, 0, 0), row(1, 1, 1_000_000_000, 0), row(2, 0, 2_000_000_000, 10),
        row(3, 1, 3_000_000_000, 0), row(4, 1, 4_000_000_000, 100),
        row(5, 2, 5_000_000_000, 0, last_lap_ms=439208), row(6, 2, 6_000_000_000, 100),
        row(7, 3, 7_000_000_000, 0, last_lap_ms=440000), row(8, -1, 8_000_000_000, 0),
    ])
    conn.commit(); conn.close()

    result = session_comparison(db, 1, segment_m=200)
    assert [item["lap"] for item in result["laps"]] == [1, 2]
import sqlite3

from gt7coach.store import SCHEMA, session_analysis


def test_session_analysis_includes_control_metrics(tmp_path):
    db = tmp_path / "metrics.sqlite3"
    conn = sqlite3.connect(db); conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 4, 4, 344, 1365, 0)")
    def row(seq, lap, x, steer, throttle, brake, last_lap_ms=-1):
        return (1, seq, seq, seq, lap, -1, last_lap_ms, 0, x, 0, 0, 20, 0, throttle, brake, 2, 0, steer, 0, 0, 0)
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 0, 0, 0, 0, 0), row(1, 1, 0, 0.2, 0, 0.8),
        row(2, 1, 100, -0.2, 0.8, 0), row(3, 2, 200, 0, 0, 0, last_lap_ms=439208),
    ])
    conn.commit(); conn.close()
    result = session_analysis(db, 1, 200)
    assert result["control_metrics"]["samples"] == 2
    assert result["control_metrics"]["steering_reversals"] == 1
