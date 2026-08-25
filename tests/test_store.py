import sqlite3
import struct
from pathlib import Path

from gt7coach.store import SCHEMA, import_capture, session_summary


def test_import_and_summary(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "first_packet.bin"
    raw = tmp_path / "sample.bin"
    raw.write_bytes(struct.pack("<QI", 123, 344) + fixture.read_bytes())
    db = tmp_path / "x.sqlite3"
    summary = session_summary(db, import_capture(db, raw))
    assert summary["frames"] == 1
    assert summary["packet_size"] == 344
    assert summary["car_code"] == 1365
    assert summary["max_speed_kmh"] > 190


def test_summary_accepts_gt7_timing_line_transition(tmp_path):
    """GT7 puts LastLapTime before the 2 -> -1 timing-line transition."""
    db = tmp_path / "timing.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO sessions VALUES(1, 'sample', 0, 1, 2, 344, 1365, 0)")
    rows = [
        (1, 0, 0, 1, 0, -1, -1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0),
        (1, 1, 1, 2, 1, -1, -1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0),
        (1, 2, 2, 3, 2, -1, 439208, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0),
    ]
    conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    result = session_summary(db, 1)

    assert result["completed_laps"] == [{
        "lap": 1,
        "lap_time_s": 439.208,
        "start_seq": 1,
        "end_seq": 2,
        "start_ts_ns": 1,
        "end_ts_ns": 2,
    }]
