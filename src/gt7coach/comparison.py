"""Deterministic lap and fixed-distance sector comparison."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def segment_times(rows: Sequence[Mapping[str, float]], segment_m: float = 200.0) -> list[dict[str, float | int]]:
    if segment_m <= 0:
        raise ValueError("segment_m must be positive")
    if len(rows) < 2:
        return []
    distances = [0.0]
    for previous, current in zip(rows, rows[1:]):
        distances.append(distances[-1] + math.dist(
            (float(previous["x"]), float(previous["y"]), float(previous["z"])),
            (float(current["x"]), float(current["y"]), float(current["z"])),
        ))
    last_sector = max(0, int(math.ceil(distances[-1] / segment_m)) - 1)
    totals = [0.0] * (last_sector + 1)
    for previous, current, start, end in zip(rows, rows[1:], distances, distances[1:]):
        duration = (int(current["ts_ns"]) - int(previous["ts_ns"])) / 1e9
        if duration < 0:
            raise ValueError("timestamps must be non-decreasing")
        sector = min(int(start // segment_m), last_sector)
        totals[sector] += duration
    result = []
    for sector, duration in enumerate(totals):
        result.append({
            "sector": sector,
            "from_m": round(sector * segment_m, 3),
            "to_m": round(min((sector + 1) * segment_m, distances[-1]), 3),
            "time_s": round(duration, 3),
        })
    return result


def compare_laps(laps: Mapping[int, Sequence[Mapping[str, float]]], segment_m: float = 200.0) -> dict:
    if not laps:
        raise ValueError("at least one lap is required")
    by_lap = {int(number): segment_times(rows, segment_m) for number, rows in laps.items()}
    summaries = []
    for number, segments in by_lap.items():
        summaries.append({"lap": number, "lap_time_s": round(sum(x["time_s"] for x in segments), 3)})
    best = min(summaries, key=lambda item: item["lap_time_s"])
    count = max(len(segments) for segments in by_lap.values())
    winners = []
    theoretical = 0.0
    for sector in range(count):
        candidates = [
            (number, segments[sector]["time_s"])
            for number, segments in by_lap.items()
            if sector < len(segments)
        ]
        number, duration = min(candidates, key=lambda item: item[1])
        theoretical += duration
        winners.append({"sector": sector, "lap": number, "time_s": duration})
    return {
        "best_lap": best["lap"], "laps": summaries,
        "theoretical_best_s": round(theoretical, 3),
        "segment_winners": winners,
    }
