import json
import sqlite3

from gt7coach.cli import main
from gt7coach.store import SCHEMA


def _row(session_id, seq, lap, ts_ns, x, last_lap_ms=-1):
    return (session_id, seq, ts_ns, seq, lap, -1, last_lap_ms, 0, x, 0, 0,
            20, 0, 0, 0, 2, 0, 0, 0, 0, 0)


def _make_db(tmp_path, sessions):
    db = tmp_path / "quality.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    for session in sessions:
        session_id = session["id"]
        rows = session["rows"]
        conn.execute(
            "INSERT INTO sessions VALUES(?, 'sample', ?, ?, ?, 344, 1365, ?)",
            (session_id, rows[0][2], rows[-1][2], session.get("packet_count", len(rows)),
             session.get("decode_errors", 0)),
        )
        conn.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return db


def _complete_rows(session_id=1, duration_ns=2_000_000_000, middle=True):
    rows = [_row(session_id, 0, 0, 0, 0), _row(session_id, 1, 1, duration_ns // 2, 0)]
    if middle:
        rows.append(_row(session_id, 2, 1, duration_ns * 3 // 4, 50))
        finish_seq = 3
    else:
        finish_seq = 2
    rows.append(_row(session_id, finish_seq, 2, duration_ns, 100, last_lap_ms=439208))
    return rows


def test_quality_cli_reports_clean_complete_session(tmp_path, capsys):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows()}])

    assert main(["--db", str(db), "quality", "--session", "1"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output == {
        "ok": True,
        "session_id": 1,
        "frames": 3,
        "decode_errors": 0,
        "complete_laps": 1,
        "issues": [],
    }


def test_quality_reports_no_complete_lap(tmp_path, capsys):
    rows = [_row(1, 0, 0, 0, 0), _row(1, 1, 1, 1_000_000_000, 0),
            _row(1, 2, 1, 2_000_000_000, 100)]
    db = _make_db(tmp_path, [{"id": 1, "rows": rows}])

    assert main(["--db", str(db), "quality", "--session", "1"]) == 2

    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is False
    assert output["complete_laps"] == 0
    assert output["issues"] == ["no_complete_lap"]


def test_quality_reports_too_few_frames_for_complete_lap(tmp_path, capsys):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows(middle=False)}])

    assert main(["--db", str(db), "quality", "--session", "1"]) == 2

    output = json.loads(capsys.readouterr().out)
    assert output["frames"] == 2
    assert output["issues"] == ["too_few_frames"]


def test_quality_reports_too_short_complete_lap(tmp_path, capsys):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows(duration_ns=100_000_000)}])

    assert main(["--db", str(db), "quality", "--session", "1"]) == 2

    output = json.loads(capsys.readouterr().out)
    assert output["issues"] == ["too_short"]


def test_quality_reports_decode_errors(tmp_path, capsys):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows(), "decode_errors": 2}])

    assert main(["--db", str(db), "quality", "--session", "1"]) == 2

    output = json.loads(capsys.readouterr().out)
    assert output["decode_errors"] == 2
    assert output["issues"] == ["decode_errors"]


def test_quality_defaults_to_latest_session(tmp_path, capsys):
    db = _make_db(tmp_path, [
        {"id": 1, "rows": _complete_rows(1)},
        {"id": 2, "rows": _complete_rows(2)},
    ])

    assert main(["--db", str(db), "quality"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["session_id"] == 2


def test_quality_writes_idempotent_quarantine_manifest(tmp_path, capsys):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows(middle=False)}])
    manifest = tmp_path / "quarantine.json"

    assert main(["--db", str(db), "quality", "--session", "1",
                 "--quarantine", str(manifest)]) == 2
    first = json.loads(manifest.read_text())
    assert first == {"sessions": [{"session_id": 1, "issues": ["too_few_frames"]}]}

    capsys.readouterr()
    assert main(["--db", str(db), "quality", "--session", "1",
                 "--quarantine", str(manifest)]) == 2
    assert json.loads(manifest.read_text()) == first

def test_validate_is_quality_command_alias(tmp_path, capsys):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows()}])

    assert main(["--db", str(db), "validate", "--session", "1"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["session_id"] == 1


from gt7coach.quality import assess_session


def test_assess_session_reports_latest_lap_availability_facts(tmp_path):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows()}])

    result = assess_session(db, 1)

    assert result["laps"] == [{
        "lap": 1,
        "lap_time_s": 439.208,
        "distance_m": 50.0,
        "usable": True,
        "issues": [],
    }]



def test_quality_cli_matches_track_from_tracks_dir(tmp_path, capsys):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows()}])
    tracks_dir = tmp_path / "tracks"
    tracks_dir.mkdir()
    (tracks_dir / "nord.json").write_text(json.dumps({
        "track_id": "nurburgring_nordschleife",
        "display_name": "Nürburgring Nordschleife",
        "length_m_nominal": 50,
        "mapping_status": "uncalibrated",
        "named_sections": [],
    }))

    assert main(["--db", str(db), "quality", "--session", "1",
                 "--tracks-dir", str(tracks_dir)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["track_match"]["status"] == "matched"
    assert output["track_match"]["track_id"] == "nurburgring_nordschleife"


def test_quality_cli_reports_invalid_tracks_dir(tmp_path, capsys):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows()}])

    assert main(["--db", str(db), "validate", "--tracks-dir",
                 str(tmp_path / "missing")]) == 2

    output = json.loads(capsys.readouterr().out)
    assert "tracks-dir" in output["error"]



def test_match_track_returns_ambiguous_for_multiple_close_candidates():
    from gt7coach.tracks import match_track

    result = match_track([
        {"track_id": "a", "display_name": "A", "length_m_nominal": 1000},
        {"track_id": "b", "display_name": "B", "length_m_nominal": 1020},
    ], 1010, tolerance_ratio=0.03)

    assert result["status"] == "ambiguous"
    assert result["track_id"] is None


def test_analyze_does_not_use_decode_error_lap(tmp_path, capsys):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows(), "decode_errors": 1}])

    assert main(["--db", str(db), "analyze", "--session", "1"]) == 2

    output = json.loads(capsys.readouterr().out)
    assert output["error"] == "no usable complete positive lap found"


def test_analyze_does_not_use_too_short_lap(tmp_path, capsys):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows(duration_ns=100_000_000)}])

    assert main(["--db", str(db), "analyze", "--session", "1"]) == 2

    output = json.loads(capsys.readouterr().out)
    assert output["error"] == "no usable complete positive lap found"


def test_quality_cli_reports_invalid_track_json(tmp_path, capsys):
    db = _make_db(tmp_path, [{"id": 1, "rows": _complete_rows()}])
    tracks_dir = tmp_path / "tracks"
    tracks_dir.mkdir()
    (tracks_dir / "broken.json").write_text("{not-json")

    assert main(["--db", str(db), "quality", "--tracks-dir", str(tracks_dir)]) == 2

    output = json.loads(capsys.readouterr().out)
    assert output["error"].startswith("invalid track JSON:")


def test_quality_cli_does_not_match_session_without_complete_lap(tmp_path, capsys):
    rows = [_row(1, 0, 0, 0, 0), _row(1, 1, 1_000_000_000, 0, 0),
            _row(1, 2, 1, 2_000_000_000, 100)]
    db = _make_db(tmp_path, [{"id": 1, "rows": rows}])
    tracks_dir = tmp_path / "tracks"
    tracks_dir.mkdir()
    (tracks_dir / "nord.json").write_text(json.dumps({
        "track_id": "nurburgring_nordschleife",
        "display_name": "Nürburgring Nordschleife",
        "length_m_nominal": 20832,
        "mapping_status": "uncalibrated",
        "named_sections": [],
    }))

    assert main(["--db", str(db), "validate", "--tracks-dir", str(tracks_dir)]) == 2

    output = json.loads(capsys.readouterr().out)
    assert output["track_match"]["status"] == "unknown"
    assert output["track_match"]["track_id"] is None
