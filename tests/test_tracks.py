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
