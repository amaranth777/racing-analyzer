import sqlite3

from gt7coach.store import SCHEMA, session_comparison


def test_comparison_reports_each_lap_boundary(tmp_path):
    db = tmp_path / "compare-timestamps.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 6, 6, 344, 1365, 0)")

    def row(seq, ts_ns, lap, last_lap_ms=-1):
        return (1, seq, ts_ns, seq, lap, -1, last_lap_ms, 0,
                seq * 100.0, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0)

    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 100, 0),
        row(1, 200, 1),
        row(2, 300, 2, 439208),
        row(3, 400, 2),
        row(4, 500, 3, 440000),
    ])
    conn.commit()
    conn.close()

    result = session_comparison(db, 1, segment_m=200)

    assert result["laps"] == [
        {
            "lap": 1,
            "lap_time_s": 439.208,
            "start_seq": 1,
            "end_seq": 2,
            "start_ts_ns": 200,
            "end_ts_ns": 300,
        },
        {
            "lap": 2,
            "lap_time_s": 440.0,
            "start_seq": 2,
            "end_seq": 4,
            "start_ts_ns": 300,
            "end_ts_ns": 500,
        },
    ]
