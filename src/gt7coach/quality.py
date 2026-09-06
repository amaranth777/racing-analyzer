"""Deterministic quality checks for imported GT7 sessions."""
from __future__ import annotations

from pathlib import Path

from .laps import extract_lap_boundaries
from .store import connect

MIN_COMPLETE_LAP_FRAMES = 3
MIN_COMPLETE_LAP_DURATION_NS = 1_000_000_000


def assess_session(db: str | Path, session_id: int | None = None) -> dict:
    """Return stable quality facts and issue codes for one session."""
    conn = connect(db)
    try:
        session = conn.execute(
            "SELECT * FROM sessions WHERE id=COALESCE(?, (SELECT max(id) FROM sessions))",
            (session_id,),
        ).fetchone()
        if session is None:
            raise ValueError("no imported sessions")
        frames = conn.execute(
            "SELECT seq, ts_ns, lap, last_lap_ms FROM frames "
            "WHERE session_id=? ORDER BY seq",
            (session["id"],),
        ).fetchall()
    finally:
        conn.close()

    boundaries = extract_lap_boundaries(frames)
    issues: list[str] = []
    if int(session["decode_errors"]) > 0:
        issues.append("decode_errors")
    if not boundaries:
        issues.append("no_complete_lap")
        quality_frames = len(frames)
    else:
        boundary = boundaries[-1]
        quality_frames = boundary.end_seq - boundary.start_seq + 1
        if quality_frames < MIN_COMPLETE_LAP_FRAMES:
            issues.append("too_few_frames")
        lap_duration_ns = boundary.end_ts_ns - boundary.start_ts_ns
        if lap_duration_ns < MIN_COMPLETE_LAP_DURATION_NS:
            issues.append("too_short")

    return {
        "ok": not issues,
        "session_id": int(session["id"]),
        "frames": quality_frames,
        "decode_errors": int(session["decode_errors"]),
        "complete_laps": len(boundaries),
        "issues": issues,
    }
