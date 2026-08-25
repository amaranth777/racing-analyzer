from gt7coach.diagnostics import detect_events


def row(t, distance, speed, throttle=0.0, brake=0.0, steering=0.0, sway=0.0):
    return {
        "ts_ns": int(t * 1_000_000_000), "distance_m": distance,
        "speed_mps": speed, "throttle": throttle, "brake": brake,
        "wheel_rotation": steering, "sway": sway,
    }


def test_detects_only_sustained_heavy_brake_and_long_coast():
    rows = [
        row(0.0, 0, 40, throttle=1.0),
        row(0.1, 5, 38, brake=0.9),
        row(0.2, 10, 35, brake=0.95),
        row(0.3, 15, 32, brake=0.9),
        row(0.4, 20, 30, brake=0.0),
        row(0.9, 50, 28),
        row(1.5, 80, 26),
        row(2.1, 110, 24),
    ]
    events = detect_events(rows)
    assert [event["type"] for event in events] == ["heavy_braking", "long_coast"]
    assert events[0]["duration_s"] == 0.2
    assert events[1]["duration_s"] == 1.7


def test_single_frame_spike_is_not_an_event():
    rows = [row(0, 0, 20), row(0.1, 2, 20, brake=1.0), row(0.2, 4, 20)]
    assert detect_events(rows) == []
