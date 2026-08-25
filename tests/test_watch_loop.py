import threading

from gt7coach.capture import watch_sessions


def test_watch_sessions_continues_after_one_finished_session(monkeypatch, tmp_path):
    results = [
        {"capture": {"started": True, "packets": 3}, "session_id": 1},
        {"capture": {"started": True, "packets": 4}, "session_id": 2},
    ]
    calls = []
    stop = threading.Event()

    def fake_capture(address, output_dir, db, **kwargs):
        calls.append((address, output_dir, db, kwargs))
        return results[len(calls) - 1]

    def stop_after_second(result):
        if result["session_id"] == 2:
            stop.set()

    monkeypatch.setattr("gt7coach.capture.capture_and_import", fake_capture)
    returned = watch_sessions(
        "127.0.0.1", tmp_path / "captures", tmp_path / "db.sqlite3",
        stop_event=stop, retry_delay_s=0, on_result=stop_after_second,
    )
    assert [item["session_id"] for item in returned] == [1, 2]
    assert len(calls) == 2
