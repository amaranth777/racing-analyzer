from gt7coach.diagnostics import detect_wheel_events


def row(t, speed=100, throttle=0, brake=0, wheels=(100, 100, 100, 100)):
    return {
        "ts_ns": int(t * 1_000_000_000), "distance_m": t * 10,
        "speed_mps": speed / 3.6, "throttle": throttle, "brake": brake,
        "wheel_speeds_kmh": wheels,
    }


def test_detects_sustained_suspected_power_slip_and_lockup():
    rows = [
        row(0.0, throttle=0.8, wheels=(100, 100, 100, 125)),
        row(0.1, throttle=0.8, wheels=(100, 100, 100, 125)),
        row(0.2, throttle=0.8, wheels=(100, 100, 100, 125)),
        row(0.3, brake=0.9, wheels=(75, 100, 100, 100)),
        row(0.4, brake=0.9, wheels=(75, 100, 100, 100)),
        row(0.5, brake=0.9, wheels=(75, 100, 100, 100)),
    ]
    events = detect_wheel_events(rows)
    assert [event["type"] for event in events] == [
        "suspected_power_slip", "suspected_lockup"
    ]
    assert events[0]["axle"] == "rear"
    assert events[1]["axle"] == "front"


def test_single_wheel_speed_spike_is_not_reported():
    rows = [row(0.0, throttle=0.9, wheels=(100, 100, 100, 140)), row(0.1)]
    assert detect_wheel_events(rows) == []
