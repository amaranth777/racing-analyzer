import socket
import sqlite3
import threading
import time
from pathlib import Path

from gt7coach.capture import capture_and_import


def free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_auto_capture_does_not_create_session_without_gt7_packet(tmp_path):
    db = tmp_path / "gt7.sqlite3"
    result = capture_and_import(
        "127.0.0.1", tmp_path / "captures", db,
        start_timeout_s=0.12, idle_timeout_s=0.1,
        listen_port=free_port(), ps5_port=free_port(),
        heartbeat_interval_s=0.03,
    )
    assert result["capture"]["started"] is False
    assert result["capture"]["reason"] == "start_timeout"
    assert result["session_id"] is None
    assert not db.exists()
