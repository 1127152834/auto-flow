"""Environment save/restore through the production app and a real browser.

The QA script is the single implementation of the chain; this test runs it and
asserts on its evidence, so the packaged probe and the regression can never
drift apart. Skips unless ``AUTOFLOW_TEST_CLOAKBROWSER`` points at an installed
kernel.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / "scripts" / "qa-pm5-browser-chain.py"


def test_management_chain_saves_linked_environment_and_restores_login(tmp_path):
    configured = os.environ.get("AUTOFLOW_TEST_CLOAKBROWSER")
    if not configured:
        pytest.skip("set AUTOFLOW_TEST_CLOAKBROWSER to an installed CloakBrowser executable")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--workspace",
            str(tmp_path / "workspace"),
            "--out",
            str(tmp_path / "evidence"),
            "--kernel",
            configured,
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    report = json.loads((tmp_path / "evidence" / "browser-chain.json").read_text("utf-8"))

    assert result.returncode == 0, report
    assert report["login"]["signedIn"] is True
    assert report["endStatus"] == 202
    assert report["endPhase"] == "completed"
    assert report["browserClosedByEnd"] is True
    assert report["savedEnvironmentId"]
    assert report["endTargets"], "the account record association must be reported"
    assert report["resumeStatus"]["body"] == "已登录"
    # Save a second time, then read the newer content from a third instance.
    assert report["secondSaveStatus"] == 202
    assert report["secondSavePhase"] == "completed"
    assert report["secondSaveGeneration"] == 2
    assert report["secondCloseConfirmed"] is True
    assert report["thirdRead"]["body"] == "已登录"
    assert report["thirdRead"]["marker"] == "v2"
