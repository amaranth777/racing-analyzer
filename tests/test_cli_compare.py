import json
import sqlite3

from gt7coach.cli import main
from gt7coach.store import SCHEMA


def test_compare_cli_emits_theoretical_best(tmp_path, capsys):
    db = tmp_path / "x.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 8, 8, 344, 1365, 0)")
    def row(seq, lap, t_ns, x, last_lap_ms=-1):
        return (1, seq, t_ns, seq, lap, -1, last_lap_ms, 0, x, 0, 0, 20, 0, 0, 0, 2, 0, 0, 0, 0, 0)
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        row(0, 0, 0, 0), row(1, 1, 1_000_000_000, 0), row(2, 1, 2_000_000_000, 100), row(3, 1, 4_000_000_000, 200),
        row(4, 2, 5_000_000_000, 0, last_lap_ms=439208), row(5, 2, 6_000_000_000, 100), row(6, 2, 7_000_000_000, 200), row(7, 3, 8_000_000_000, 0, last_lap_ms=440000),
    ])
    conn.commit(); conn.close()
    assert main(["--db", str(db), "compare", "--segment-m", "200"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["best_lap"] == 2
    assert output["theoretical_best_s"] == 2.0
    assert len(output["segment_winners"]) == 1
