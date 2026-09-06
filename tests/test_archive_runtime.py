import sqlite3
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "archive_runtime.py"


def run_archive(runtime: Path, archive: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--runtime-dir", str(runtime), "--archive-dir", str(archive)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )


def make_database(runtime: Path, name: str = "session-1") -> Path:
    runtime.mkdir(parents=True, exist_ok=True)
    database = runtime / "gt7.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sessions (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO sessions(name) VALUES (?)", (name,))
    return database


def test_archive_runtime_creates_sqlite_snapshot_and_copies_captures(tmp_path):
    runtime = tmp_path / "runtime"
    archive = tmp_path / "archive"
    captures = runtime / "captures"
    captures.mkdir(parents=True)
    database = make_database(runtime)
    source_capture = captures / "capture-001.bin"
    source_capture.write_bytes(b"capture-data")
    nested_capture = captures / "nested" / "capture-002.bin"
    nested_capture.parent.mkdir()
    nested_capture.write_bytes(b"nested-data")

    result = run_archive(runtime, archive)

    assert result.returncode == 0, result.stderr
    assert result.stdout.split()[-1] == "captures=2"
    assert (archive / "gt7.sqlite3").is_file()
    assert (archive / "captures" / source_capture.name).read_bytes() == b"capture-data"
    assert (archive / "captures" / "nested" / nested_capture.name).read_bytes() == b"nested-data"
    with sqlite3.connect(archive / "gt7.sqlite3") as connection:
        assert connection.execute("SELECT name FROM sessions").fetchall() == [("session-1",)]
    assert database.is_file()


def test_archive_runtime_snapshot_is_consistent_until_next_run(tmp_path):
    runtime = tmp_path / "runtime"
    archive = tmp_path / "archive"
    database = make_database(runtime, "before")
    source_capture = runtime / "captures" / "capture.bin"
    source_capture.parent.mkdir()
    source_capture.write_bytes(b"before")

    assert run_archive(runtime, archive).returncode == 0

    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO sessions(name) VALUES ('after')")
    source_capture.write_bytes(b"after")

    with sqlite3.connect(archive / "gt7.sqlite3") as connection:
        assert connection.execute("SELECT name FROM sessions ORDER BY rowid").fetchall() == [("before",)]
    assert (archive / "captures" / "capture.bin").read_bytes() == b"before"


def test_archive_runtime_is_repeatable_and_keeps_runtime_sources(tmp_path):
    runtime = tmp_path / "runtime"
    archive = tmp_path / "archive"
    captures = runtime / "captures"
    captures.mkdir(parents=True)
    database = make_database(runtime, "before")
    source_capture = captures / "capture.bin"
    source_capture.write_bytes(b"before")

    assert run_archive(runtime, archive).returncode == 0

    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO sessions(name) VALUES ('after')")
    source_capture.write_bytes(b"after")
    assert run_archive(runtime, archive).returncode == 0

    assert database.is_file()
    assert source_capture.read_bytes() == b"after"
    assert (archive / "captures" / "capture.bin").read_bytes() == b"after"
    with sqlite3.connect(archive / "gt7.sqlite3") as connection:
        assert connection.execute("SELECT name FROM sessions ORDER BY rowid").fetchall() == [("before",), ("after",)]


def test_archive_runtime_fails_nonzero_without_runtime_database(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    result = run_archive(runtime, tmp_path / "archive")

    assert result.returncode != 0
    assert result.stderr.strip().split() == ["status=error", f"path={(tmp_path / 'archive').resolve()}"]


def test_archive_runtime_succeeds_without_captures_directory(tmp_path):
    runtime = tmp_path / "runtime"
    make_database(runtime)

    result = run_archive(runtime, tmp_path / "archive")

    assert result.returncode == 0, result.stderr
    assert "captures=0" in result.stdout


def test_archive_runtime_rejects_archive_inside_runtime(tmp_path):
    runtime = tmp_path / "runtime"
    make_database(runtime)

    result = run_archive(runtime, runtime / "archive")

    assert result.returncode != 0
    assert result.stderr.strip().split() == ["status=error", f"path={(runtime / 'archive').resolve()}"]



def test_archive_runtime_retries_capture_changed_during_copy(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("archive_runtime", SCRIPT)
    archive_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(archive_module)

    runtime = tmp_path / "runtime"
    archive = tmp_path / "archive"
    make_database(runtime)
    source_capture = runtime / "captures" / "capture.bin"
    source_capture.parent.mkdir()
    source_capture.write_bytes(b"partial")

    original_copy2 = archive_module.shutil.copy2
    calls = 0

    def copy2_then_source_continues(source, destination):
        nonlocal calls
        calls += 1
        result = original_copy2(source, destination)
        if calls == 1:
            Path(source).write_bytes(b"complete capture")
        return result

    monkeypatch.setattr(archive_module.shutil, "copy2", copy2_then_source_continues)

    assert archive_module.archive_runtime(runtime, archive) == 1
    assert calls == 2
    assert (archive / "captures" / "capture.bin").read_bytes() == b"complete capture"



def test_archive_runtime_skips_unreferenced_active_capture(tmp_path):
    runtime = tmp_path / "runtime"
    archive = tmp_path / "archive"
    make_database(runtime)
    captures = runtime / "captures"
    captures.mkdir()
    referenced = captures / "referenced.bin"
    active = captures / "active.bin"
    referenced.write_bytes(b"referenced")
    active.write_bytes(b"active")

    with sqlite3.connect(runtime / "gt7.sqlite3") as connection:
        connection.execute("ALTER TABLE sessions ADD COLUMN source_path TEXT")
        connection.execute("UPDATE sessions SET source_path = ?", (str(referenced),))

    result = run_archive(runtime, archive)

    assert result.returncode == 0, result.stderr
    assert (archive / "captures" / "referenced.bin").read_bytes() == b"referenced"
    assert not (archive / "captures" / "active.bin").exists()
