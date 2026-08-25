"""Coarse GT7 game-state classification for offline capture indexing."""
from __future__ import annotations


def classify_packet_state(packet) -> str:
    """Classify one decoded packet without claiming exact UI screen identity."""
    if packet.lap > 0:
        return "driving"
    if packet.lap == 0:
        return "outlap_or_unknown"
    if packet.lap == -1 and packet.flags == 0:
        return "menu_or_idle"
    return "unknown"


def coalesce_states(states) -> list[dict]:
    """Merge adjacent ``(seq, ts_ns, kind)`` records into state spans."""
    spans = []
    for seq, ts_ns, kind in states:
        if (
            spans
            and spans[-1]["kind"] == kind
            and seq == spans[-1]["end_seq"] + 1
        ):
            spans[-1]["end_seq"] = seq
            spans[-1]["end_ts_ns"] = ts_ns
        else:
            spans.append({
                "start_seq": seq, "end_seq": seq, "kind": kind,
                "start_ts_ns": ts_ns, "end_ts_ns": ts_ns,
            })
    return spans
