import socket
import struct
import threading
import time
from pathlib import Path

from gt7coach.capture import capture_gt7_session

FIXTURE = Path(__file__).parent / "fixtures" / "first_packet.bin"


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_auto_session_starts_on_valid_packet_and_stops_after_idle(tmp_path):
    listen_port = free_port()
    payload = FIXTURE.read_bytes()
    result_holder = {}

    def run_capture():
        result_holder["result"] = capture_gt7_session(
            "127.0.0.1", tmp_path, start_timeout_s=2.0,
            idle_timeout_s=0.25, listen_port=listen_port,
            ps5_port=free_port(), heartbeat_interval_s=0.05,
        )

    thread = threading.Thread(target=run_capture)
    thread.start()
    time.sleep(0.1)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for _ in range(4):
        sender.sendto(payload, ("127.0.0.1", listen_port))
        time.sleep(0.05)
    sender.close()
    thread.join(timeout=3)
    assert not thread.is_alive()

    result = result_holder["result"]
    assert result["started"] is True
    assert result["packets"] == 4
    assert result["reason"] == "idle_timeout"
    raw = Path(result["capture_path"])
    assert raw.exists()
    with raw.open("rb") as stream:
        count = 0
        while stream.read(12):
            size = struct.unpack("<QI", stream.read(0))[1] if False else None
            header = stream.seek(-12, 1)
            ts_size = stream.read(12)
            _, size = struct.unpack("<QI", ts_size)
            assert len(stream.read(size)) == size
            count += 1
    assert count == 4
