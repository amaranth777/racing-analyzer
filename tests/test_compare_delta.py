import sqlite3

from gt7coach.store import SCHEMA, compare_sessions


def test_compare_sessions_reports_delta_from_best_lap(tmp_path):
    db = tmp_path / "delta.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    for session_id, lap_time_ms in ((1, 439208), (5, 443413)):
        conn.execute(
            "INSERT INTO sessions VALUES(?, ?, 0, 3, 3, 344, 1365, 0)",
            (session_id, f"sample-{session_id}"),
        )
        conn.executemany(
            "INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (session_id, 0, 100, 0, 0, -1, -1, 0, 0, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0),
                (session_id, 1, 200, 1, 1, -1, -1, 0, 0, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0),
                (session_id, 2, 300, 2, 2, -1, lap_time_ms, 0, 200, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0),
            ],
        )
    conn.commit()
    conn.close()

    result = compare_sessions(db, [1, 5], segment_m=200)

    assert result["slowest_session_id"] == 5
    assert result["delta_s"] == 4.205
    assert result["delta_pct"] == 0.96
