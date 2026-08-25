from gt7coach.analysis import cumulative_distance, summarize_segments


def frame(x, speed_mps, throttle, brake, steer):
    return {"x": x, "y": 0.0, "z": 0.0, "speed_mps": speed_mps,
            "throttle": throttle, "brake": brake, "wheel_rotation": steer}


def test_cumulative_distance_uses_position_delta():
    rows = [frame(0, 10, 1, 0, 0), frame(100, 10, 1, 0, 0), frame(250, 10, 1, 0, 0)]
    assert cumulative_distance(rows) == [0.0, 100.0, 250.0]


def test_segments_aggregate_200m_windows():
    rows = [frame(0, 10, 1, 0, 0.1), frame(100, 20, 0.5, 0.5, 0.2),
            frame(200, 30, 0, 1, 0.3), frame(300, 40, 1, 0, 0.4)]
    segments = summarize_segments(rows, segment_m=200)
    assert [x["sector"] for x in segments] == [0, 1]
    assert segments[0]["from_m"] == 0.0
    assert segments[0]["to_m"] == 200.0
    assert segments[0]["mean_speed_kmh"] == 54.0
    assert segments[0]["full_throttle_pct"] == 50.0
    assert segments[0]["brake_pct"] == 50.0
    assert segments[1]["mean_speed_kmh"] == 126.0
