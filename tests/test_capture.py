import socket
import struct
import threading
from pathlib import Path

from gt7coach.capture import capture_udp


def test_capture_udp_writes_framed_packets(tmp_path):
    output = tmp_path / "capture.bin"
    ready = threading.Event()

    def fake_ps5():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        ready.port = port
        ready.set()
        data, address = sock.recvfrom(4096)
        assert data == b"~"
        sock.sendto(b"packet-one", address)
        sock.close()

    server = threading.Thread(target=fake_ps5)
    server.start()
    ready.wait(timeout=2)
    capture_udp("127.0.0.1", output, seconds=0.3, ps5_port=ready.port, listen_port=0)
    server.join(timeout=2)

    raw = output.read_bytes()
    timestamp, size = struct.unpack("<QI", raw[:12])
    assert timestamp > 0
    assert size == len(b"packet-one")
    assert raw[12:] == b"packet-one"
