import json
import sqlite3

from gt7coach.cli import main
from gt7coach.store import SCHEMA, compare_sessions


def make_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    for session_id, lap_time_ms in ((1, 439208), (5, 443413)):
        conn.execute(
            "INSERT INTO sessions VALUES(?, ?, 0, 3, 3, 344, 1365, 0)",
            (session_id, f"sample-{session_id}"),
        )
        rows = [
            (session_id, 0, 100, 0, 0, -1, -1, 0, 0, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0),
            (session_id, 1, 200, 1, 1, -1, -1, 0, 0, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0),
            (session_id, 2, 300, 2, 2, -1, lap_time_ms, 0, 200, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0),
        ]
        conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def test_compare_sessions_uses_gt7_lap_times_and_metadata(tmp_path):
    db = tmp_path / "cross.sqlite3"
    make_db(db)

    result = compare_sessions(db, [1, 5], segment_m=200)

    assert result["best_session_id"] == 1
    assert [item["session_id"] for item in result["laps"]] == [1, 5]
    assert result["laps"][0]["lap_time_s"] == 439.208
    assert result["laps"][0]["start_ts_ns"] == 200
    assert result["laps"][0]["end_ts_ns"] == 300


def test_compare_cli_accepts_multiple_sessions(tmp_path, capsys):
    db = tmp_path / "cross-cli.sqlite3"
    make_db(db)

    assert main(["--db", str(db), "compare", "--sessions", "1", "5"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["best_session_id"] == 1
    assert [item["session_id"] for item in output["laps"]] == [1, 5]
