"""Verify complete migrated module code and both owned model bytes in a frozen build."""
import hashlib
import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

executable = Path(sys.argv[1])
source_root = Path(sys.argv[2])
archive = CArchiveReader(str(executable)).open_embedded_archive("PYZ.pyz")
for module in [
    "autoflow.infrastructure.process.project_workflow_worker",
    "autoflow.infrastructure.process.project_test_browser_worker",
    "autoflow.domain.workflows.catalog",
    "autoflow.providers.browser.project_graph",
    "autoflow.providers.browser.project_workflow_worker",
    "autoflow.application.workflows.executors.media_recognition",
    "autoflow.application.workflows.executors.captcha",
]:
    path = source_root / (module.replace(".", "/") + ".py")
    source = compile(path.read_text(), str(path), "exec", dont_inherit=True)
    packed = archive.extract(module)
    assert (source.co_code, source.co_consts, source.co_names) == (
        packed.co_code, packed.co_consts, packed.co_names
    ), module
    print(f"{module}: complete frozen module matches source")
for name in ("craft_mlt_25k.pth", "zh_sim_g2.pth"):
    relative = Path("autoflow/resources/easyocr") / name
    expected = hashlib.sha256((source_root / relative).read_bytes()).hexdigest()
    actual = hashlib.sha256((executable.parent / "_internal" / relative).read_bytes()).hexdigest()
    assert actual == expected, name
    print(f"{name}: {actual}")
