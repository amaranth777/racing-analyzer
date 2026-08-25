import socket
import threading
import time
from pathlib import Path

from gt7coach.capture import capture_and_import

FIXTURE = Path(__file__).parent / "fixtures" / "first_packet.bin"


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_auto_capture_imports_finished_session_into_sqlite(tmp_path):
    listen_port = free_port()
    payload = FIXTURE.read_bytes()
    db = tmp_path / "gt7.sqlite3"
    result_holder = {}

    def run_capture():
        result_holder["result"] = capture_and_import(
            "127.0.0.1", tmp_path / "captures", db,
            start_timeout_s=2.0, idle_timeout_s=0.2,
            listen_port=listen_port, ps5_port=free_port(),
            heartbeat_interval_s=0.05,
        )

    thread = threading.Thread(target=run_capture)
    thread.start()
    time.sleep(0.1)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for _ in range(3):
        sender.sendto(payload, ("127.0.0.1", listen_port))
        time.sleep(0.04)
    sender.close()
    thread.join(timeout=3)
    assert not thread.is_alive()

    result = result_holder["result"]
    assert result["capture"]["started"] is True
    assert result["capture"]["packets"] == 3
    assert result["session_id"] == 1
    assert result["frames"] == 3
    assert result["decode_errors"] == 0
    assert Path(result["capture"]["capture_path"]).exists()
