import sqlite3

from gt7coach.store import SCHEMA, compare_sessions


def _insert_session(conn, session_id, lap_time_ms, offset=0, duplicate_of=None):
    conn.execute(
        "INSERT INTO sessions VALUES(?, ?, 0, 3, 3, 344, 1365, 0)",
        (session_id, f"sample-{duplicate_of or session_id}"),
    )
    rows = [
        (session_id, 0, 100 + offset, 0, 0, -1, -1, 0, 0, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0),
        (session_id, 1, 200 + offset, 1, 1, -1, -1, 0, 0, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0),
        (session_id, 2, 300 + offset, 2, 2, -1, lap_time_ms, 0, 200, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0),
    ]
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def test_compare_sessions_deduplicates_identical_complete_laps(tmp_path):
    db = tmp_path / "dedupe.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    _insert_session(conn, 1, 439208)
    _insert_session(conn, 2, 439208, duplicate_of=1)
    _insert_session(conn, 3, 439208, duplicate_of=1)
    _insert_session(conn, 5, 443413, offset=10)
    conn.commit()
    conn.close()

    result = compare_sessions(db, [1, 2, 3, 5], segment_m=200)

    assert [lap["session_id"] for lap in result["laps"]] == [1, 5]
    assert result["duplicate_session_ids"] == [2, 3]
    assert result["deduplicated_count"] == 2


def test_compare_sessions_keeps_same_time_with_different_telemetry(tmp_path):
    db = tmp_path / "different-telemetry.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    _insert_session(conn, 1, 439208)
    _insert_session(conn, 2, 439208)
    conn.execute(
        "UPDATE frames SET speed_mps=speed_mps + 1 WHERE session_id=2 AND seq=1"
    )
    conn.commit()
    conn.close()

    result = compare_sessions(db, [1, 2], segment_m=200)

    assert [lap["session_id"] for lap in result["laps"]] == [1, 2]
    assert result["duplicate_session_ids"] == []
    assert result["deduplicated_count"] == 2
