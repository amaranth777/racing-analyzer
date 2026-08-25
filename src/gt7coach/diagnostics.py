"""Conservative, explainable post-lap driving event detection."""
from __future__ import annotations

from collections.abc import Mapping, Sequence


def _runs(rows, predicate):
    run = []
    for row in rows:
        if predicate(row):
            run.append(row)
        elif run:
            yield run
            run = []
    if run:
        yield run


def _event(event_type, run):
    return {
        "type": event_type,
        "from_m": round(float(run[0]["distance_m"]), 1),
        "to_m": round(float(run[-1]["distance_m"]), 1),
        "duration_s": round((int(run[-1]["ts_ns"]) - int(run[0]["ts_ns"])) / 1e9, 3),
        "speed_min_kmh": round(min(float(row["speed_mps"]) for row in run) * 3.6, 1),
    }


def detect_events(rows: Sequence[Mapping[str, float]], *, min_brake_s: float = 0.15,
                  min_coast_s: float = 1.0) -> list[dict[str, float | str]]:
    """Detect only sustained pedal events; isolated samples are ignored."""
    events = []
    for run in _runs(rows, lambda row: float(row["brake"]) >= 0.8):
        if (int(run[-1]["ts_ns"]) - int(run[0]["ts_ns"])) / 1e9 >= min_brake_s:
            events.append(_event("heavy_braking", run))
    for run in _runs(rows, lambda row: float(row["throttle"]) <= 0.05 and float(row["brake"]) <= 0.05):
        if (int(run[-1]["ts_ns"]) - int(run[0]["ts_ns"])) / 1e9 >= min_coast_s:
            events.append(_event("long_coast", run))
    return sorted(events, key=lambda event: event["from_m"])


def control_metrics(rows):
    """Summarize directly observable pedal/steering coordination."""
    samples = len(rows)
    if not samples:
        return {
            "samples": 0,
            "brake_while_steering_pct": 0.0,
            "throttle_while_steering_pct": 0.0,
            "steering_reversals": 0,
        }
    steering_rows = [abs(float(row["wheel_rotation"])) > 0.05 for row in rows]
    brake_overlap = sum(steer and float(row["brake"]) > 0.05 for steer, row in zip(steering_rows, rows))
    throttle_overlap = sum(steer and float(row["throttle"]) > 0.05 for steer, row in zip(steering_rows, rows))
    signs = [
        1 if float(row["wheel_rotation"]) > 0.05 else -1
        for row in rows if abs(float(row["wheel_rotation"])) > 0.05
    ]
    reversals = sum(previous != current for previous, current in zip(signs, signs[1:]))
    return {
        "samples": samples,
        "brake_while_steering_pct": round(brake_overlap / samples * 100, 1),
        "throttle_while_steering_pct": round(throttle_overlap / samples * 100, 1),
        "steering_reversals": reversals,
    }


def _wheel_run_event(event_type, axle, rows):
    return {
        "type": event_type,
        "axle": axle,
        "from_m": round(float(rows[0]["distance_m"]), 1),
        "to_m": round(float(rows[-1]["distance_m"]), 1),
        "duration_s": round((int(rows[-1]["ts_ns"]) - int(rows[0]["ts_ns"])) / 1e9, 3),
        "confidence": "suspected",
    }


def detect_wheel_events(rows, *, min_duration_s=0.15):
    """Find sustained wheel-speed anomalies, deliberately labelled suspected."""
    if len(rows) < 2:
        return []
    normalized = []
    for row in rows:
        speed = max(abs(float(row["speed_mps"])) * 3.6, 1.0)
        wheels = tuple(float(value) for value in row["wheel_speeds_kmh"])
        normalized.append({
            **row,
            "front_ratio": (wheels[0] + wheels[1]) / 2 / speed,
            "rear_ratio": (wheels[2] + wheels[3]) / 2 / speed,
        })
    events = []
    for event_type, axle, predicate in (
        ("suspected_power_slip", "rear", lambda row: row["rear_ratio"] > 1.08 and row["throttle"] > 0.5),
        ("suspected_lockup", "front", lambda row: row["front_ratio"] < 0.88 and row["brake"] > 0.5),
    ):
        run = []
        for row in normalized:
            if predicate(row):
                run.append(row)
            elif run:
                if (run[-1]["ts_ns"] - run[0]["ts_ns"]) / 1e9 >= min_duration_s:
                    events.append(_wheel_run_event(event_type, axle, run))
                run = []
        if run and (run[-1]["ts_ns"] - run[0]["ts_ns"]) / 1e9 >= min_duration_s:
            events.append(_wheel_run_event(event_type, axle, run))
    return sorted(events, key=lambda event: event["from_m"])


def wheel_speeds_kmh(rps, diameters):
    """Convert GT7 wheel values to line speed; GT7 values already encode 1/pi."""
    return tuple(round(abs(float(value)) * float(diameter) * 3.6, 1)
                 for value, diameter in zip(rps, diameters))
