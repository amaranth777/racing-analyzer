import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-hermes-skill.py"
SKILL = ROOT / "skills" / "racing-analyzer" / "SKILL.md"


def run_installer(home, *args):
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(INSTALLER), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def test_skill_source_has_loader_contract():
    text = SKILL.read_text()
    assert text.startswith("---\n")
    assert "name: racing-analyzer" in text
    assert "## When to Use" in text
    assert "## Quick Reference" in text
    assert "## Evidence Contract" in text
    assert "## Analyzer/Hermes Boundary" in text
    assert "recommendations" in text
    assert "confidence: \"suspected\"" in text
    assert "description: Use RacingAnalyzer to inspect GT7 telemetry evidence." in text
    assert "/home/" not in text
    assert "$HERMES_HOME" in text


def test_check_does_not_write_profile(tmp_path):
    result = run_installer(tmp_path, "--check")
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "skills" / "racing-analyzer" / "SKILL.md").exists()


def test_install_writes_exact_skill_content(tmp_path):
    result = run_installer(tmp_path)
    assert result.returncode == 0, result.stderr
    installed = tmp_path / "skills" / "racing-analyzer" / "SKILL.md"
    assert installed.read_bytes() == SKILL.read_bytes()
    assert hashlib.sha256(installed.read_bytes()).hexdigest() == hashlib.sha256(SKILL.read_bytes()).hexdigest()


def test_install_refuses_to_overwrite_without_force(tmp_path):
    target = tmp_path / "skills" / "racing-analyzer" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("local skill\n")
    result = run_installer(tmp_path)
    assert result.returncode != 0
    assert target.read_text() == "local skill\n"


def test_install_force_replaces_existing_skill(tmp_path):
    target = tmp_path / "skills" / "racing-analyzer" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("old skill\n")
    result = run_installer(tmp_path, "--force")
    assert result.returncode == 0, result.stderr
    assert target.read_bytes() == SKILL.read_bytes()
