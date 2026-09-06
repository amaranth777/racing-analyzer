import json

from gt7coach.tracks import load_track, map_distance


def test_uncalibrated_track_never_invents_named_section(tmp_path):
    path = tmp_path / "track.json"
    path.write_text(json.dumps({
        "track_id": "nordschleife",
        "display_name": "Nürburgring Nordschleife",
        "mapping_status": "uncalibrated",
        "named_sections": [],
    }))
    track = load_track(path)
    assert track["mapping_status"] == "uncalibrated"
    assert map_distance(track, 800.0, segment_m=200)["label"] == "micro-sector-004"
    assert map_distance(track, 800.0, segment_m=200)["named"] is False


def test_calibrated_range_resolves_name(tmp_path):
    path = tmp_path / "track.json"
    path.write_text(json.dumps({
        "track_id": "nordschleife",
        "display_name": "Nürburgring Nordschleife",
        "mapping_status": "calibrated",
        "named_sections": [{"name": "Example", "from_m": 800, "to_m": 1000}],
    }))
    track = load_track(path)
    assert map_distance(track, 900.0, segment_m=200) == {
        "label": "Example", "named": True, "from_m": 800.0, "to_m": 1000.0,
    }


from gt7coach.tracks import match_track


def test_match_track_uses_nominal_length_with_confidence(tmp_path):
    candidates = [{
        "track_id": "nurburgring_nordschleife",
        "display_name": "Nürburgring Nordschleife",
        "length_m_nominal": 20832,
    }]

    result = match_track(candidates, 20744.4)

    assert result == {
        "track_id": "nurburgring_nordschleife",
        "display_name": "Nürburgring Nordschleife",
        "distance_m": 20744.4,
        "nominal_length_m": 20832.0,
        "relative_error": round(abs(20744.4 - 20832) / 20832, 6),
        "confidence": "high",
        "status": "matched",
    }



def test_match_track_returns_unknown_when_no_candidate_is_close():
    candidates = [{
        "track_id": "short",
        "display_name": "Short",
        "length_m_nominal": 5000,
    }]

    result = match_track(candidates, 7000)

    assert result["status"] == "unknown"
    assert result["confidence"] == "none"
    assert result["track_id"] is None
