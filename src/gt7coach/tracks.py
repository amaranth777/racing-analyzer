"""Track metadata and explicitly opt-in distance-to-name mapping."""
from __future__ import annotations

import json
from pathlib import Path


def load_track(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("track metadata must be an object")
    status = data.get("mapping_status", "uncalibrated")
    if status not in {"uncalibrated", "calibrated"}:
        raise ValueError("mapping_status must be calibrated or uncalibrated")
    sections = data.get("named_sections", [])
    if not isinstance(sections, list):
        raise ValueError("named_sections must be a list")
    checked = []
    for section in sections:
        if not isinstance(section, dict) or not section.get("name"):
            raise ValueError("each named section needs a name")
        start = float(section["from_m"])
        end = float(section["to_m"])
        if start < 0 or end <= start:
            raise ValueError("named section range is invalid")
        checked.append({"name": str(section["name"]), "from_m": start, "to_m": end})
    result = dict(data)
    result["mapping_status"] = status
    result["named_sections"] = checked
    return result


def map_distance(track: dict, distance_m: float, *, segment_m: float = 200.0) -> dict:
    if segment_m <= 0:
        raise ValueError("segment_m must be positive")
    distance = float(distance_m)
    if distance < 0:
        raise ValueError("distance_m must be non-negative")
    if track.get("mapping_status") == "calibrated":
        for section in track.get("named_sections", []):
            if float(section["from_m"]) <= distance < float(section["to_m"]):
                return {
                    "label": section["name"], "named": True,
                    "from_m": float(section["from_m"]),
                    "to_m": float(section["to_m"]),
                }
    sector = int(distance // segment_m)
    return {"label": f"micro-sector-{sector:03d}", "named": False}


def match_track(track_candidates, distance_m: float, *, tolerance_ratio: float = 0.03) -> dict:
    """Match a lap distance to nominal track lengths without guessing."""
    distance = float(distance_m)
    tolerance = float(tolerance_ratio)
    if distance < 0 or tolerance < 0:
        raise ValueError("distance_m and tolerance_ratio must be non-negative")
    matches = []
    for track in track_candidates:
        nominal = track.get("length_m_nominal")
        if nominal is None or float(nominal) <= 0:
            continue
        nominal = float(nominal)
        error = abs(distance - nominal) / nominal
        if error <= tolerance:
            matches.append((error, track, nominal))
    matches.sort(key=lambda item: item[0])
    if len(matches) != 1:
        return {
            "track_id": None, "display_name": None, "distance_m": distance,
            "nominal_length_m": None, "relative_error": None,
            "confidence": "none",
            "status": "ambiguous" if len(matches) > 1 else "unknown",
        }
    error, track, nominal = matches[0]
    return {
        "track_id": track.get("track_id"),
        "display_name": track.get("display_name"),
        "distance_m": distance, "nominal_length_m": nominal,
        "relative_error": round(error, 6),
        "confidence": "high" if error <= tolerance / 2 else "medium",
        "status": "matched",
    }
