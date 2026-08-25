import sqlite3
import struct
from pathlib import Path

from gt7coach.state import classify_packet_state, coalesce_states
from gt7coach.store import SCHEMA, import_capture

FIXTURE = Path(__file__).parent / "fixtures" / "first_packet.bin"


def test_classify_menu_outlap_and_driving_states():
    class Packet:
        def __init__(self, lap, flags, speed_mps, rpm, throttle, brake):
            self.lap = lap; self.flags = flags; self.speed_mps = speed_mps
            self.rpm = rpm; self.throttle = throttle; self.brake = brake

    assert classify_packet_state(Packet(-1, 0, 0, 0, 0, 0)) == "menu_or_idle"
    # GT7 can leave stale dynamic values in menu packets.
    assert classify_packet_state(Packet(-1, 0, 40, 7108, 0, 0.7)) == "menu_or_idle"
    assert classify_packet_state(Packet(0, 153, 5, 2000, 0.2, 0)) == "outlap_or_unknown"
    assert classify_packet_state(Packet(1, 153, 20, 5000, 0.8, 0)) == "driving"
    assert classify_packet_state(Packet(-1, 1, 2, 1000, 0, 0)) == "unknown"


def test_coalesce_states_preserves_contiguous_ranges():
    states = [(0, 100, "menu_or_idle"), (1, 200, "menu_or_idle"),
              (2, 300, "driving"), (3, 400, "driving"), (4, 500, "outlap_or_unknown")]
    assert coalesce_states(states) == [
        {"start_seq": 0, "end_seq": 1, "kind": "menu_or_idle", "start_ts_ns": 100, "end_ts_ns": 200},
        {"start_seq": 2, "end_seq": 3, "kind": "driving", "start_ts_ns": 300, "end_ts_ns": 400},
        {"start_seq": 4, "end_seq": 4, "kind": "outlap_or_unknown", "start_ts_ns": 500, "end_ts_ns": 500},
    ]


def test_import_persists_state_spans(tmp_path):
    db = tmp_path / "states.sqlite3"
    raw = tmp_path / "capture.bin"
    payload = FIXTURE.read_bytes()
    raw.write_bytes(struct.pack("<QI", 1, len(payload)) + payload)
    import_capture(db, raw)
    conn = sqlite3.connect(db)
    spans = conn.execute("SELECT kind, start_seq, end_seq FROM state_spans").fetchall()
    conn.close()
    assert spans == [("driving", 0, 0)]
