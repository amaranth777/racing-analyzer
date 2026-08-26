import json
import sqlite3

from gt7coach.cli import main
from gt7coach.store import SCHEMA


def make_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 3, 3, 344, 1365, 0)")
    rows = [
        (1, 0, 100, 0, 0, -1, -1, 0, 0, 0, 0, 20, 0, 0.0, 0.0, 2, 0, 0.0, 0, 0, 0),
        (1, 1, 200, 1, 1, -1, -1, 0, 100, 0, 0, 20, 0, 1.0, 0.0, 3, 0, 0.2, 0, 0, 0),
        (1, 2, 300, 2, 2, -1, 439208, 0, 200, 0, 0, 20, 0, 0.0, 0.8, 3, 0, 0.2, 0, 0, 0),
    ]
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def test_analyze_keeps_diagnostics_and_returns_evidence(tmp_path, capsys):
    db = tmp_path / "analyze.sqlite3"
    make_db(db)

    assert main(["--db", str(db), "analyze", "--session", "1"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert "control_metrics" in result
    assert "wheel_events" in result
    assert "events" in result
    assert "segments" in result
    assert "recommendations" not in result
