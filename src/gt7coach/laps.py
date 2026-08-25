from dataclasses import dataclass
from collections.abc import Mapping, Sequence


@dataclass(frozen=True)
class LapBoundary:
    lap: int
    start_seq: int
    end_seq: int
    start_ts_ns: int
    end_ts_ns: int
    lap_time_ms: int


def extract_lap_boundaries(rows: Sequence[Mapping[str, int]]) -> list[LapBoundary]:
    """Extract complete laps bounded by consecutive timing-line transitions."""
    transitions = []
    for index, (before, after) in enumerate(zip(rows, rows[1:]), 1):
        if int(before["lap"]) != int(after["lap"]):
            transitions.append((index, before, after))

    boundaries = []
    for start_transition, finish_transition in zip(transitions, transitions[1:]):
        _, before, start = start_transition
        _, finish_before, finish = finish_transition
        lap = int(start["lap"])
        if lap <= 0 or int(before["lap"]) != lap - 1:
            continue
        if int(finish_before["lap"]) != lap or int(finish["lap"]) != lap + 1:
            continue
        lap_time_ms = int(finish["last_lap_ms"])
        if lap_time_ms <= 0:
            continue
        boundaries.append(
            LapBoundary(
                lap=lap,
                start_seq=int(start["seq"]),
                end_seq=int(finish["seq"]),
                start_ts_ns=int(start["ts_ns"]),
                end_ts_ns=int(finish["ts_ns"]),
                lap_time_ms=lap_time_ms,
            )
        )
    return boundaries
