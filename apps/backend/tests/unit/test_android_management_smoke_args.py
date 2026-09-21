import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "android-management-smoke.py"


def test_smoke_requires_explicit_permission() -> None:
    result = subprocess.run([sys.executable, str(SCRIPT), "--workspace", "/tmp/autoflow-test"], capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "--allow-device-mutation" in result.stderr


def test_smoke_help_has_no_side_effect() -> None:
    result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert "allow-device-mutation" in result.stdout
