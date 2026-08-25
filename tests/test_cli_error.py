import json
import sqlite3

from gt7coach.cli import main
from gt7coach.store import SCHEMA


def test_compare_cli_reports_missing_second_lap_as_json(tmp_path, capsys):
    db = tmp_path / "one.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 3, 3, 344, 1365, 0)")
    def row(seq, lap, ts, x):
        return (1, seq, ts, seq, lap, -1, -1, 0, x, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0)
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 0, 0, 0), row(1, 1, 1_000_000_000, 0), row(2, 2, 2_000_000_000, 100),
    ])
    conn.commit(); conn.close()
    assert main(["--db", str(db), "compare"]) == 2
    output = json.loads(capsys.readouterr().out)
    assert output["error"] == "at least two complete positive laps are required"
