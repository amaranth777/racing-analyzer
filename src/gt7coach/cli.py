from __future__ import annotations

import argparse
import json
from pathlib import Path

from .capture import capture_and_import, capture_udp, watch_forever, watch_sessions
from .quality import assess_session
from .store import (add_setup, compare_sessions, import_capture, list_setups,
                    session_analysis, session_comparison, session_summary)
from .tracks import load_track, map_distance


def _write_quarantine_manifest(path: Path, result: dict) -> None:
    """Atomically mark a failed session without moving or deleting data."""
    manifest = {"sessions": []}
    if path.exists():
        try:
            loaded = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict) and isinstance(loaded.get("sessions"), list):
            manifest["sessions"] = loaded["sessions"]
    entry = {"session_id": result["session_id"], "issues": result["issues"]}
    manifest["sessions"] = [
        item for item in manifest["sessions"]
        if not isinstance(item, dict) or item.get("session_id") != entry["session_id"]
    ]
    manifest["sessions"].append(entry)
    manifest["sessions"].sort(key=lambda item: item.get("session_id", 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="RacingAnalyzer",
        description="RacingAnalyzer - GT7 telemetry capture and analysis",
    )
    parser.add_argument("--db", default="data/gt7.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--address", required=True)
    capture.add_argument("--seconds", type=float, default=600.0)
    capture.add_argument("--output", type=Path, required=True)
    watch = sub.add_parser("watch")
    watch.add_argument("--once", action="store_true", help="capture one session and exit")
    watch.add_argument("--ps5", required=True)
    watch.add_argument("--output-dir", type=Path, default=Path("data/captures"))
    watch.add_argument("--db", type=Path, default=Path("data/gt7.sqlite3"))
    watch.add_argument("--start-timeout", type=float, default=30.0)
    watch.add_argument("--idle-timeout", type=float, default=10.0)
    watch.add_argument("--listen-port", type=int, default=33740)
    watch.add_argument("--ps5-port", type=int, default=33739)
    imp = sub.add_parser("import")
    imp.add_argument("capture", type=Path)
    summ = sub.add_parser("summary")
    summ.add_argument("--session", type=int)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("--session", type=int)
    analyze.add_argument("--segment-m", type=float, default=200.0)
    analyze.add_argument("--track", type=Path)
    compare = sub.add_parser("compare")
    compare.add_argument("--session", type=int)
    compare.add_argument("--sessions", type=int, nargs="+")
    compare.add_argument("--segment-m", type=float, default=200.0)
    diagnose = sub.add_parser("diagnose")
    diagnose.add_argument("--session", type=int)
    diagnose.add_argument("--segment-m", type=float, default=200.0)
    diagnose.add_argument("--track", type=Path)
    for command_name in ("validate", "quality"):
        quality = sub.add_parser(command_name)
        quality.add_argument("--session", type=int)
        quality.add_argument("--quarantine", type=Path)
    setup = sub.add_parser("setup")
    setup_sub = setup.add_subparsers(dest="setup_command", required=True)
    setup_add = setup_sub.add_parser("add")
    setup_add.add_argument("--track", required=True)
    setup_add.add_argument("--car-code", required=True, type=int)
    setup_add.add_argument("--name", required=True)
    setup_add.add_argument("--notes", default="")
    setup_list = setup_sub.add_parser("list")
    setup_list.add_argument("--track")
    setup_list.add_argument("--car-code", type=int)

    args = parser.parse_args(argv)
    if args.command == "capture":
        count = capture_udp(args.address, args.output, seconds=args.seconds)
        print(json.dumps({"packets": count, "output": str(args.output)}, ensure_ascii=False))
        return 0
    if args.command == "watch":
        kwargs = {
            "listen_port": args.listen_port,
            "ps5_port": args.ps5_port,
        }
        if args.once:
            result = capture_and_import(
                args.ps5, args.output_dir, args.db,
                start_timeout_s=args.start_timeout,
                idle_timeout_s=args.idle_timeout,
                **kwargs,
            )
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")), flush=True)
            return 0
        watch_forever(
            args.ps5, args.output_dir, args.db,
            on_segment=lambda result: print(
                json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                flush=True,
            ),
            **kwargs,
        )
        return 0
    if args.command == "import":
        sid = import_capture(args.db, args.capture)
        print(json.dumps({"session_id": sid, "db": str(args.db)}, ensure_ascii=False))
        return 0
    if args.command == "setup":
        if args.setup_command == "add":
            result = add_setup(args.db, track_id=args.track, car_code=args.car_code,
                               name=args.name, notes=args.notes)
        else:
            result = list_setups(args.db, track_id=args.track, car_code=args.car_code)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0
    if args.command == "compare":
        try:
            if args.sessions:
                result = compare_sessions(args.db, args.sessions, args.segment_m)
            else:
                result = session_comparison(args.db, args.session, args.segment_m)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False, separators=(",", ":")))
            return 2
        result["segment_winners"] = result["segment_winners"][:10]
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0
    if args.command in {"validate", "quality"}:
        try:
            result = assess_session(args.db, args.session)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False, separators=(",", ":")))
            return 2
        if args.quarantine is not None and not result["ok"]:
            _write_quarantine_manifest(args.quarantine, result)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0 if result["ok"] else 2
    if args.command in {"analyze", "diagnose"}:
        result = session_analysis(args.db, args.session, args.segment_m)
        result["slowest_segments"] = result["slowest_segments"][:5]
        result["events"] = result["events"][:10]
        if args.track:
            track = load_track(args.track)
            for segment in result["slowest_segments"]:
                segment.update(map_distance(track, segment["from_m"], segment_m=args.segment_m))
            for event in result["events"]:
                event.update(map_distance(track, event["from_m"], segment_m=args.segment_m))
        if args.command == "analyze":
            result["events"] = result["events"][:10]
            result["wheel_events"] = result["wheel_events"][:10]
        else:
            result.pop("segments", None)
            result.pop("slowest_segments", None)
            result["wheel_events"] = result["wheel_events"][:10]
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0
    print(json.dumps(session_summary(args.db, args.session), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
