import sqlite3

from gt7coach.store import SCHEMA, session_analysis


def test_session_analysis_includes_suspected_wheel_events(tmp_path):
    db = tmp_path / "wheel-analysis.sqlite3"
    conn = sqlite3.connect(db); conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 4, 4, 344, 1365, 0)")
    def frame(seq, lap, x, throttle, brake, last_lap_ms=-1):
        return (1, seq, seq * 100_000_000, seq, lap, -1, last_lap_ms, 0, x, 0, 0,
                20, 0, throttle, brake, 2, 0, 0, 0, 0, 0)
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        frame(0, 0, 0, 0, 0), frame(1, 1, 0, 0.8, 0),
        frame(2, 1, 10, 0.8, 0), frame(3, 1, 20, 0.8, 0),
        frame(4, 2, 30, 0, 0, last_lap_ms=439208),
    ])
    # 20 m/s = 72 km/h; rear wheel line speed ~= 90 km/h.
    conn.executemany("INSERT INTO wheel_frames VALUES(?,?,?,?,?,?,?,?,?,?)", [
        (1, 0, 0, 0, 80, 80, 0.33, 0.33, 0.33, 0.33),
        (1, 1, 0, 0, 80, 80, 0.33, 0.33, 0.33, 0.33),
        (1, 2, 0, 0, 80, 80, 0.33, 0.33, 0.33, 0.33),
        (1, 3, 0, 0, 80, 80, 0.33, 0.33, 0.33, 0.33),
        (1, 4, 0, 0, 0, 0, 0.33, 0.33, 0.33, 0.33),
    ])
    conn.commit(); conn.close()
    result = session_analysis(db, 1, 200)
    assert result["wheel_events"][0]["type"] == "suspected_power_slip"
    assert result["wheel_events"][0]["confidence"] == "suspected"
