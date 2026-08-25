import json
import sqlite3

from gt7coach.cli import main
from gt7coach.store import SCHEMA


def test_setup_cli_add_and_list(tmp_path, capsys):
    db = tmp_path / "setup.sqlite3"
    conn = sqlite3.connect(db); conn.executescript(SCHEMA); conn.commit(); conn.close()
    assert main(["--db", str(db), "setup", "add", "--track", "nordschleife", "--car-code", "1365", "--name", "R8 baseline", "--notes", "safe"]) == 0
    added = json.loads(capsys.readouterr().out)
    assert added["name"] == "R8 baseline"
    assert main(["--db", str(db), "setup", "list", "--track", "nordschleife"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert len(listed) == 1
    assert listed[0]["car_code"] == 1365
