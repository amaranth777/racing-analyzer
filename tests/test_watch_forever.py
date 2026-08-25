import socket
import threading
import time
from pathlib import Path


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_watch_forever_splits_lap_data_at_menu_and_continues(monkeypatch, tmp_path):
    from gt7coach.capture import watch_forever

    class Packet:
        def __init__(self, lap, flags):
            self.lap = lap
            self.flags = flags
            self.speed_mps = 10.0
            self.rpm = 3000.0
            self.throttle = 0.5
            self.brake = 0.0

    monkeypatch.setattr(
        "gt7coach.capture.decode_packet",
        lambda payload: Packet(1, 153) if payload == b"D" else Packet(-1, 0),
    )
    imported = []

    def fake_import(db, source):
        imported.append(Path(source).read_bytes())
        return len(imported)

    monkeypatch.setattr("gt7coach.store.import_capture", fake_import)
    listen_port = free_port()
    stop = threading.Event()
    result_holder = {}

    def run():
        result_holder["result"] = watch_forever(
            "127.0.0.1", tmp_path / "segments", tmp_path / "db.sqlite3",
            listen_port=listen_port, ps5_port=free_port(),
            heartbeat_interval_s=0.02, stop_event=stop,
        )

    thread = threading.Thread(target=run)
    thread.start()
    time.sleep(0.1)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for payload in (b"D", b"D", b"M", b"D"):
        sender.sendto(payload, ("127.0.0.1", listen_port))
        time.sleep(0.03)
    time.sleep(0.1)
    assert thread.is_alive()
    stop.set()
    thread.join(timeout=2)
    sender.close()

    assert not thread.is_alive()
    assert len(imported) == 2
    assert all(b"M" not in raw for raw in imported)
    assert result_holder["result"]["segments_imported"] == 2
