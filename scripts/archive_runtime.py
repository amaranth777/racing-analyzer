#!/usr/bin/env python3
"""Create a local, repeatable archive of a RacingAnalyzer runtime directory."""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

DATABASE_NAME = "gt7.sqlite3"
CAPTURES_NAME = "captures"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--archive-dir", type=Path, required=True)
    return parser.parse_args(argv)


def _validate_dirs(runtime_dir: Path, archive_dir: Path) -> None:
    if not runtime_dir.is_dir():
        raise FileNotFoundError(f"runtime directory does not exist: {runtime_dir}")
    if archive_dir == runtime_dir or archive_dir.is_relative_to(runtime_dir):
        raise ValueError("archive directory must not be the runtime directory or its child")


def _database_signature(source: Path) -> int:
    """Newest mtime of the database and its WAL; changes whenever SQLite writes."""
    wal = source.with_name(source.name + "-wal")
    return max(path.stat().st_mtime_ns for path in (source, wal) if path.exists())


def _backup_database(source: Path, destination: Path) -> bool:
    """Snapshot source into destination unless it is unchanged; return True if written.

    The snapshot is stamped with the source signature taken *before* the backup, so a
    write that lands during the backup still differs from the stamp and is picked up
    by the next run.
    """
    signature = _database_signature(source)
    if destination.is_file() and destination.stat().st_mtime_ns == signature:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with sqlite3.connect(source) as source_connection, sqlite3.connect(temporary) as destination_connection:
            source_connection.backup(destination_connection)
            destination_connection.commit()
        os.utime(temporary, ns=(signature, signature))
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return True


CAPTURE_COPY_ATTEMPTS = 3


def _copy_capture_consistently(source: Path, destination: Path) -> None:
    if destination.is_file():
        source_stat, destination_stat = source.stat(), destination.stat()
        # copy2 preserves mtime, so equal size + mtime means this capture is already archived.
        if (source_stat.st_size, source_stat.st_mtime_ns) == (destination_stat.st_size, destination_stat.st_mtime_ns):
            return
    destination.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(CAPTURE_COPY_ATTEMPTS):
        before = source.stat()
        temporary = destination.with_name(f".{destination.name}.tmp")
        try:
            shutil.copy2(source, temporary)
            after = source.stat()
            if (before.st_mtime_ns, before.st_size, before.st_ino) != (
                after.st_mtime_ns,
                after.st_size,
                after.st_ino,
            ):
                continue
            os.replace(temporary, destination)
            return
        finally:
            temporary.unlink(missing_ok=True)
    raise RuntimeError(f"capture changed while copying: {source}")


def _referenced_captures(database: Path, runtime_dir: Path, source_dir: Path) -> set[Path] | None:
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(sessions)")}
        if "source_path" not in columns:
            return None
        values = [row[0] for row in connection.execute("SELECT source_path FROM sessions")]

    source_dir = source_dir.resolve()
    referenced: set[Path] = set()
    for value in values:
        if not value:
            raise ValueError("session has an empty source_path")
        raw = Path(value).expanduser()
        candidates = [raw] if raw.is_absolute() else [runtime_dir.parent / raw, runtime_dir / raw]
        resolved = next((candidate.resolve() for candidate in candidates if candidate.resolve().is_relative_to(source_dir)), None)
        if resolved is None:
            raise ValueError(f"session source_path is outside captures: {value}")
        if not resolved.is_file():
            raise FileNotFoundError(f"referenced capture does not exist: {resolved}")
        referenced.add(resolved)
    return referenced


def _copy_captures(source_dir: Path, destination_dir: Path, referenced: set[Path] | None = None) -> int:
    if not source_dir.exists():
        if referenced:
            raise FileNotFoundError(f"captures path does not exist: {source_dir}")
        return 0
    if not source_dir.is_dir():
        raise NotADirectoryError(f"captures path is not a directory: {source_dir}")

    source_dir = source_dir.resolve()
    if referenced is None:
        entries = [path for path in sorted(source_dir.rglob("*")) if path.is_file()]
    else:
        entries = sorted(referenced)
    count = 0
    for source in entries:
        if not source.is_file() or not source.resolve().is_relative_to(source_dir):
            raise ValueError(f"unsupported capture entry: {source}")
        relative = source.relative_to(source_dir)
        _copy_capture_consistently(source, destination_dir / relative)
        count += 1
    return count


def archive_runtime(runtime_dir: Path, archive_dir: Path) -> int:
    """Archive the runtime database and captures locally; return capture count."""
    runtime_dir = runtime_dir.expanduser().resolve()
    archive_dir = archive_dir.expanduser().resolve()
    _validate_dirs(runtime_dir, archive_dir)

    database = runtime_dir / DATABASE_NAME
    if not database.is_file():
        raise FileNotFoundError(f"runtime database does not exist: {database}")

    _backup_database(database, archive_dir / DATABASE_NAME)
    source_dir = runtime_dir / CAPTURES_NAME
    referenced = _referenced_captures(database, runtime_dir, source_dir)
    return _copy_captures(source_dir, archive_dir / CAPTURES_NAME, referenced)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        captures = archive_runtime(args.runtime_dir, args.archive_dir)
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"status=error path={args.archive_dir.expanduser().resolve()}", file=sys.stderr)
        return 1
    print(f"status=ok archive={args.archive_dir.expanduser().resolve()} database={args.archive_dir.expanduser().resolve() / DATABASE_NAME} captures={captures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
