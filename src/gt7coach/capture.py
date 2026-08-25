"""Raw GT7 UDP capture without decoding or data loss."""
from __future__ import annotations

import socket
import struct
import time
from pathlib import Path

from .protocol import PacketError, decode_packet


def capture_udp(ps5_address: str, output: str | Path, *, seconds: float = 600.0,
                ps5_port: int = 33739, listen_port: int = 33740,
                heartbeat: bytes = b"~") -> int:
    """Capture raw UDP packets and return the number of packets written."""
    if seconds <= 0:
        raise ValueError("seconds must be positive")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", listen_port))
    sock.settimeout(0.2)
    sock.sendto(heartbeat, (ps5_address, ps5_port))
    deadline = time.monotonic() + seconds
    count = 0
    with output.open("wb") as stream:
        while time.monotonic() < deadline:
            try:
                payload, address = sock.recvfrom(4096)
            except socket.timeout:
                sock.sendto(heartbeat, (ps5_address, ps5_port))
                continue
            if address[0] != ps5_address:
                continue
            stream.write(struct.pack("<QI", time.time_ns(), len(payload)))
            stream.write(payload)
            count += 1
    sock.close()
    return count


def capture_gt7_session(ps5_address: str, output_dir: str | Path, *,
                        start_timeout_s: float = 30.0, idle_timeout_s: float = 10.0,
                        listen_port: int = 33740, ps5_port: int = 33739,
                        heartbeat: bytes = b"~", heartbeat_interval_s: float = 0.5) -> dict:
    """Capture one automatically bounded GT7 play session.

    The first decodable packet starts a session. Consecutive silence after that
    ends it. Invalid UDP packets are ignored and never persisted.
    """
    if start_timeout_s <= 0 or idle_timeout_s <= 0 or heartbeat_interval_s <= 0:
        raise ValueError("timeouts and heartbeat interval must be positive")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", listen_port))
    sock.settimeout(min(0.2, heartbeat_interval_s))
    started = False
    packets = 0
    capture_path = None
    stream = None
    deadline = time.monotonic() + start_timeout_s
    next_heartbeat = 0.0
    last_valid = None
    reason = "start_timeout"
    try:
        while True:
            now = time.monotonic()
            if not started and now >= deadline:
                break
            if started and last_valid is not None and now - last_valid >= idle_timeout_s:
                reason = "idle_timeout"
                break
            if now >= next_heartbeat:
                try:
                    sock.sendto(heartbeat, (ps5_address, ps5_port))
                except OSError:
                    pass
                next_heartbeat = now + heartbeat_interval_s
            try:
                payload, address = sock.recvfrom(4096)
            except socket.timeout:
                continue
            if address[0] != ps5_address:
                continue
            try:
                decode_packet(payload)
            except (PacketError, ValueError, struct.error):
                continue
            if not started:
                capture_path = output_dir / f"gt7-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.bin"
                stream = capture_path.open("wb")
                started = True
            stream.write(struct.pack("<QI", time.time_ns(), len(payload)))
            stream.write(payload)
            stream.flush()
            packets += 1
            last_valid = time.monotonic()
    finally:
        if stream is not None:
            stream.close()
        sock.close()
    return {
        "started": started,
        "packets": packets,
        "reason": reason if started else "start_timeout",
        "capture_path": str(capture_path) if capture_path else None,
    }


def capture_and_import(ps5_address: str, output_dir: str | Path, db: str | Path, **kwargs) -> dict:
    """Capture one detected GT7 session, then import its raw file offline."""
    from .store import import_capture
    capture = capture_gt7_session(ps5_address, output_dir, **kwargs)
    result = {"capture": capture, "session_id": None}
    if not capture["started"] or not capture["capture_path"] or capture["packets"] == 0:
        return result
    session_id = import_capture(db, capture["capture_path"])
    result["session_id"] = session_id
    result["frames"] = capture["packets"]
    result["decode_errors"] = 0
    return result


def watch_sessions(ps5_address: str, output_dir: str | Path, db: str | Path, *,
                   stop_event=None, retry_delay_s: float = 1.0, on_result=None,
                   **kwargs) -> list[dict]:
    """Continuously capture, import, and wait for the next GT7 session."""
    import threading
    if retry_delay_s < 0:
        raise ValueError("retry_delay_s must be non-negative")
    stop_event = stop_event or threading.Event()
    results = []
    while not stop_event.is_set():
        result = capture_and_import(ps5_address, output_dir, db, **kwargs)
        results.append(result)
        if on_result is not None:
            on_result(result)
        if stop_event.is_set():
            break
        if retry_delay_s:
            stop_event.wait(retry_delay_s)
    return results


def watch_forever(ps5_address: str, output_dir: str | Path, db: str | Path, *,
                  listen_port: int = 33740, ps5_port: int = 33739,
                  heartbeat: bytes = b"~", heartbeat_interval_s: float = 0.5,
                  stop_event=None, on_segment=None) -> dict:
    """Run until explicitly stopped; split non-menu telemetry at menu packets."""
    import threading
    from .store import import_capture
    if heartbeat_interval_s <= 0:
        raise ValueError("heartbeat interval must be positive")
    stop_event = stop_event or threading.Event()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", listen_port))
    sock.settimeout(min(0.2, heartbeat_interval_s))
    stream = None
    segment_path = None
    segments_imported = 0
    packets = 0
    next_heartbeat = 0.0

    def close_segment():
        nonlocal stream, segment_path, segments_imported
        if stream is None:
            return
        stream.close()
        session_id = import_capture(db, segment_path)
        segments_imported += 1
        if on_segment is not None:
            on_segment({"path": str(segment_path), "session_id": session_id})
        stream = None
        segment_path = None

    try:
        while not stop_event.is_set():
            now = time.monotonic()
            if now >= next_heartbeat:
                try:
                    sock.sendto(heartbeat, (ps5_address, ps5_port))
                except OSError:
                    pass
                next_heartbeat = now + heartbeat_interval_s
            try:
                payload, address = sock.recvfrom(4096)
            except socket.timeout:
                continue
            if address[0] != ps5_address:
                continue
            try:
                packet = decode_packet(payload)
            except (PacketError, ValueError, struct.error):
                continue
            is_menu = packet.lap == -1 and packet.flags == 0
            if is_menu:
                close_segment()
                continue
            if stream is None:
                segment_path = output_dir / (
                    f"gt7-segment-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.bin"
                )
                stream = segment_path.open("wb")
            stream.write(struct.pack("<QI", time.time_ns(), len(payload)))
            stream.write(payload)
            stream.flush()
            packets += 1
    finally:
        close_segment()
        sock.close()
    return {"segments_imported": segments_imported, "packets": packets}
