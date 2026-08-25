import json
import sqlite3

from gt7coach.cli import main
from gt7coach.store import SCHEMA


def test_analyze_hides_wheel_diagnostics_and_diagnose_caps_them(tmp_path, capsys):
    db = tmp_path / "cli-wheel.sqlite3"
    conn = sqlite3.connect(db); conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 4, 4, 344, 1365, 0)")
    def frame(seq, lap, x, last_lap_ms=-1):
        return (1, seq, seq * 100_000_000, seq, lap, -1, last_lap_ms, 0, x, 0, 0,
                20, 0, 0.8, 0, 2, 0, 0, 0, 0, 0)
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        frame(0, 0, 0), frame(1, 1, 0), frame(2, 1, 10), frame(3, 1, 20), frame(4, 2, 30, last_lap_ms=439208),
    ])
    conn.executemany("INSERT INTO wheel_frames VALUES(?,?,?,?,?,?,?,?,?,?)", [
        (1, i, 0, 0, 80, 80, .33, .33, .33, .33) for i in range(5)
    ])
    conn.commit(); conn.close()
    assert main(["--db", str(db), "analyze"]) == 0
    analyzed = json.loads(capsys.readouterr().out)
    assert "wheel_events" not in analyzed
    assert "control_metrics" not in analyzed
    assert main(["--db", str(db), "diagnose"]) == 0
    diagnosed = json.loads(capsys.readouterr().out)
    assert len(diagnosed["wheel_events"]) <= 10
