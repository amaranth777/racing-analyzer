import sqlite3

from gt7coach.store import SCHEMA, session_summary


def test_summary_reports_unique_lap_start_and_end_timestamps(tmp_path):
    db = tmp_path / "timestamps.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 6, 6, 344, 1365, 0)")

    def row(seq, ts_ns, lap, last_lap_ms=-1):
        return (1, seq, ts_ns, seq, lap, -1, last_lap_ms, 0,
                seq * 100.0, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0)

    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 100, 0),
        row(1, 200, 1),
        row(2, 300, 1),
        row(3, 400, 2, 439208),
        row(4, 500, 2, 439208),
        row(5, 600, -1, 439208),
    ])
    conn.commit()
    conn.close()

    result = session_summary(db, 1)

    assert result["completed_laps"] == [{
        "lap": 1,
        "lap_time_s": 439.208,
        "start_seq": 1,
        "end_seq": 3,
        "start_ts_ns": 200,
        "end_ts_ns": 400,
    }]
