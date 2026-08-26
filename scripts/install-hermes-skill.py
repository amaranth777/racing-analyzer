#!/usr/bin/env python3
"""Install the repository-owned RacingAnalyzer Skill for the active Hermes profile."""
from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

SKILL_NAME = "racing-analyzer"


def source_path() -> Path:
    return Path(__file__).resolve().parents[1] / "skills" / SKILL_NAME / "SKILL.md"


def hermes_home() -> Path:
    value = os.environ.get("HERMES_HOME")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".hermes"


def destination_path() -> Path:
    return hermes_home() / "skills" / SKILL_NAME / "SKILL.md"


def install(*, force: bool = False, check: bool = False) -> int:
    source = source_path()
    destination = destination_path()
    if not source.is_file():
        raise SystemExit(f"Skill source does not exist: {source}")
    content = source.read_bytes()

    if check:
        print(f"source={source}")
        print(f"destination={destination}")
        print(f"destination_exists={destination.exists()}")
        return 0

    if destination.exists() and not force:
        if destination.read_bytes() == content:
            print(f"already_installed={destination}")
            return 0
        raise SystemExit(
            f"Refusing to overwrite existing Skill: {destination}; use --force"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{SKILL_NAME}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    print(f"installed={destination}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="replace a different installed Skill")
    parser.add_argument("--check", action="store_true", help="show source and destination without writing")
    args = parser.parse_args(argv)
    return install(force=args.force, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
