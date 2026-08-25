from gt7coach.comparison import compare_laps, segment_times


def row(t, x, speed=20.0):
    return {"ts_ns": int(t * 1_000_000_000), "x": x, "y": 0.0,
            "z": 0.0, "speed_mps": speed, "throttle": 0.0,
            "brake": 0.0, "wheel_rotation": 0.0}


def test_segment_times_use_sample_intervals():
    rows = [row(0, 0), row(1, 50), row(3, 100), row(5, 150), row(7, 200)]
    segments = segment_times(rows, segment_m=100)
    assert [x["sector"] for x in segments] == [0, 1]
    assert [x["time_s"] for x in segments] == [3.0, 4.0]


def test_compare_laps_returns_actual_and_theoretical_best():
    lap1 = [row(0, 0), row(1, 50), row(3, 100), row(5, 150), row(7, 200)]
    lap2 = [row(0, 0), row(1, 50), row(2, 100), row(3, 150), row(4, 200)]
    result = compare_laps({1: lap1, 2: lap2}, segment_m=100)
    assert result["best_lap"] == 2
    assert result["laps"][0]["lap_time_s"] == 7.0
    assert result["theoretical_best_s"] == 4.0
    assert [x["lap"] for x in result["segment_winners"]] == [2, 2]
