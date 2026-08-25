import json
import sqlite3

from gt7coach.cli import main


def test_watch_parser_runs_one_capture_and_import(monkeypatch, tmp_path, capsys):
    captured = {}
    def fake_capture(address, output_dir, db, **kwargs):
        captured.update({"address": address, "output_dir": output_dir, "db": db, **kwargs})
        return {"capture": {"started": False, "packets": 0, "reason": "start_timeout", "capture_path": None}, "session_id": None}
    monkeypatch.setattr("gt7coach.cli.capture_and_import", fake_capture)
    assert main(["watch", "--once", "--ps5", "192.168.50.246", "--output-dir", str(tmp_path / "captures"), "--db", str(tmp_path / "db.sqlite3"), "--start-timeout", "1", "--idle-timeout", "2"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["capture"]["reason"] == "start_timeout"
    assert captured["address"] == "192.168.50.246"
    assert captured["start_timeout_s"] == 1.0
    assert captured["idle_timeout_s"] == 2.0
