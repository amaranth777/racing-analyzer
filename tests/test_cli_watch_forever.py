import json

from gt7coach.cli import main


def test_watch_default_uses_forever_splitter(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_watch(address, output_dir, db, **kwargs):
        calls.append((address, output_dir, db, kwargs))
        kwargs["on_segment"]({"session_id": 1, "path": "segment.bin"})
        return {"segments_imported": 1, "packets": 2}

    monkeypatch.setattr("gt7coach.cli.watch_forever", fake_watch)
    assert main([
        "watch", "--ps5", "192.168.50.246",
        "--output-dir", str(tmp_path / "captures"),
        "--db", str(tmp_path / "db.sqlite3"),
    ]) == 0
    assert len(calls) == 1
    assert json.loads(capsys.readouterr().out)["session_id"] == 1
