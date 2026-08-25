from gt7coach.diagnostics import control_metrics


def row(steering, throttle=0.0, brake=0.0):
    return {"wheel_rotation": steering, "throttle": throttle, "brake": brake}


def test_control_metrics_measure_overlap_and_reversals():
    rows = [
        row(0.0), row(0.5, brake=0.8), row(0.2, brake=0.9),
        row(-0.4, throttle=0.8), row(-0.1, throttle=0.9), row(0.3, throttle=0.8),
    ]
    result = control_metrics(rows)
    assert result["samples"] == 6
    assert result["brake_while_steering_pct"] == 33.3
    assert result["throttle_while_steering_pct"] == 50.0
    assert result["steering_reversals"] == 2


def test_control_metrics_empty_is_zeroed():
    result = control_metrics([])
    assert result == {
        "samples": 0,
        "brake_while_steering_pct": 0.0,
        "throttle_while_steering_pct": 0.0,
        "steering_reversals": 0,
    }
