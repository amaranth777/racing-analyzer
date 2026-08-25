import json

from gt7coach.cli import main


def test_watch_once_uses_single_capture(monkeypatch, tmp_path, capsys):
    calls = []
    def fake_capture(address, output_dir, db, **kwargs):
        calls.append(kwargs)
        return {"capture": {"started": False, "packets": 0, "reason": "start_timeout", "capture_path": None}, "session_id": None}
    monkeypatch.setattr("gt7coach.cli.capture_and_import", fake_capture)
    assert main(["watch", "--once", "--ps5", "192.168.50.246", "--output-dir", str(tmp_path / "captures"), "--db", str(tmp_path / "db.sqlite3")]) == 0
    assert len(calls) == 1
    assert json.loads(capsys.readouterr().out)["capture"]["reason"] == "start_timeout"


def test_watch_default_uses_forever_splitter(monkeypatch, tmp_path, capsys):
    calls = []
    def fake_watch(address, output_dir, db, **kwargs):
        calls.append((address, output_dir, db, kwargs))
        kwargs["on_segment"]({"session_id": 1, "path": "segment.bin"})
        return {"segments_imported": 1, "packets": 2}
    monkeypatch.setattr("gt7coach.cli.watch_forever", fake_watch)
    assert main(["watch", "--ps5", "192.168.50.246", "--output-dir", str(tmp_path / "captures"), "--db", str(tmp_path / "db.sqlite3")]) == 0
    assert len(calls) == 1
    assert "start_timeout_s" not in calls[0][3]
    assert json.loads(capsys.readouterr().out)["session_id"] == 1
