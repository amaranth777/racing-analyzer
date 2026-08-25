import subprocess
import sys
from pathlib import Path


def test_project_help_uses_racing_analyzer_name():
    result = subprocess.run(
        [sys.executable, "-m", "gt7coach.cli", "--help"],
        check=True, capture_output=True, text=True,
    )
    assert "RacingAnalyzer" in result.stdout


def test_racing_analyzer_console_script_is_declared():
    text = Path("pyproject.toml").read_text()
    assert 'racing-analyzer = "gt7coach.cli:main"' in text
