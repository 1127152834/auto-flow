import importlib.util
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


def test_authorized_smoke_runs_the_guarded_runner(tmp_path: Path, monkeypatch, capsys) -> None:
    spec = importlib.util.spec_from_file_location("android_management_smoke", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    async def fake_runner(_args):
        return {"status": "passed", "deviceId": "owned-device"}

    monkeypatch.setattr(module, "run_smoke", fake_runner)
    assert module.main(["--workspace", str(tmp_path), "--allow-device-mutation"]) == 0
    assert '"status": "passed"' in capsys.readouterr().out
