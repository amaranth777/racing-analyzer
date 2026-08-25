import sqlite3
import struct
from pathlib import Path

from gt7coach.store import SCHEMA, import_capture

FIXTURE = Path(__file__).parent / "fixtures" / "first_packet.bin"


def test_import_persists_wheel_fields(tmp_path):
    db = tmp_path / "wheels.sqlite3"
    capture = tmp_path / "capture.bin"
    payload = FIXTURE.read_bytes()
    capture.write_bytes(struct.pack("<QI", 1, len(payload)) + payload)
    import_capture(db, capture)
    conn = sqlite3.connect(db)
    frame_count = conn.execute("SELECT count(*) FROM frames").fetchone()[0]
    wheel_count = conn.execute("SELECT count(*) FROM wheel_frames").fetchone()[0]
    row = conn.execute("SELECT front_left_rps, rear_right_diameter_m FROM wheel_frames").fetchone()
    conn.close()
    assert frame_count == 1
    assert wheel_count == 1
    assert row[0] != 0
    assert row[1] > 0
