"""Deterministic post-lap geometry and pedal analysis."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def cumulative_distance(rows: Sequence[Mapping[str, float]]) -> list[float]:
    """Return distance along the recorded position polyline in metres."""
    distances = [0.0]
    for previous, current in zip(rows, rows[1:]):
        delta = math.sqrt(sum((float(current[axis]) - float(previous[axis])) ** 2 for axis in ("x", "y", "z")))
        distances.append(distances[-1] + delta)
    return distances


def summarize_segments(rows: Sequence[Mapping[str, float]], segment_m: float = 200.0) -> list[dict[str, float | int]]:
    """Aggregate samples into fixed-distance windows.

    Samples on a boundary belong to the next segment. Values are deliberately
    sample means; later, a frame-duration weighted variant can be added when
    variable-rate captures become a real input.
    """
    if segment_m <= 0:
        raise ValueError("segment_m must be positive")
    if not rows:
        return []
    distances = cumulative_distance(rows)
    last_sector = max(0, int(math.ceil(distances[-1] / segment_m)) - 1)
    result = []
    for sector in range(last_sector + 1):
        indices = [i for i, distance in enumerate(distances) if min(int(distance // segment_m), last_sector) == sector]
        if not indices:
            continue
        values = [rows[i] for i in indices]
        result.append({
            "sector": sector,
            "from_m": round(sector * segment_m, 3),
            "to_m": round(min((sector + 1) * segment_m, distances[-1]), 3),
            "frames": len(values),
            "mean_speed_kmh": round(sum(float(row["speed_mps"]) for row in values) / len(values) * 3.6, 1),
            "full_throttle_pct": round(sum(float(row["throttle"]) >= 0.95 for row in values) / len(values) * 100, 1),
            "brake_pct": round(sum(float(row["brake"]) > 0.05 for row in values) / len(values) * 100, 1),
            "steering_abs_mean_rad": round(sum(abs(float(row["wheel_rotation"])) for row in values) / len(values), 3),
        })
    return result
