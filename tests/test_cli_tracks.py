import json
import sqlite3

from gt7coach.cli import main
from gt7coach.store import SCHEMA


def test_analyze_cli_adds_safe_track_labels(tmp_path, capsys):
    db = tmp_path / "x.sqlite3"
    track = tmp_path / "track.json"
    track.write_text(json.dumps({
        "track_id": "nordschleife",
        "display_name": "Nürburgring Nordschleife",
        "mapping_status": "uncalibrated",
        "named_sections": [],
    }))
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 4, 4, 344, 1365, 0)")
    def row(seq, lap, x, speed, last_lap_ms=-1):
        return (1, seq, seq, seq, lap, -1, last_lap_ms, 0, x, 0, 0, speed, 0, 0, 0, 2, 0, 0, 0, 0, 0)
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 0, 0, 10), row(1, 1, 0, 10), row(2, 1, 100, 20),
        row(3, 1, 200, 30), row(4, 2, 300, 10, last_lap_ms=439208),
    ])
    conn.commit(); conn.close()
    assert main(["--db", str(db), "analyze", "--track", str(track)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["slowest_segments"][0]["label"].startswith("micro-sector-")
