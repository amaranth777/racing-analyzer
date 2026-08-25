import sqlite3

from gt7coach.store import SCHEMA, session_analysis


def test_analysis_reports_boundary_timestamps(tmp_path):
    db = tmp_path / "analysis-timestamps.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 4, 4, 344, 1365, 0)")

    def row(seq, ts_ns, lap, last_lap_ms=-1):
        return (1, seq, ts_ns, seq, lap, -1, last_lap_ms, 0,
                seq * 100.0, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0)

    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 100, 0),
        row(1, 200, 1),
        row(2, 300, 1),
        row(3, 400, 2, 439208),
    ])
    conn.commit()
    conn.close()

    result = session_analysis(db, 1, segment_m=200)

    assert result["start_seq"] == 1
    assert result["end_seq"] == 3
    assert result["start_ts_ns"] == 200
    assert result["end_ts_ns"] == 400
    assert result["lap_time_s"] == 439.208
