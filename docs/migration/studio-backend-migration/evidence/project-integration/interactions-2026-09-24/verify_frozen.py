"""Compare the interaction block's complete frozen module code with local source."""
import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

archive = CArchiveReader(sys.argv[1]).open_embedded_archive("PYZ.pyz")
source_root = Path(sys.argv[2])
for module in [
    "autoflow.application.project_runs.interactions",
    "autoflow.application.workflows.dispatcher",
    "autoflow.application.workflows.executors.input_prompt",
    "autoflow.adapters.http.project_run_interactions",
    "autoflow.adapters.http.project_run_events",
    "autoflow.adapters.http.project_run_events_schemas",
    "autoflow.domain.workflows.catalog",
    "autoflow.infrastructure.process.project_workflow_worker",
    "autoflow.providers.browser.project_workflow_worker",
    "autoflow.providers.browser.project_graph",
    "autoflow.providers.browser.workflow_worker",
]:
    path = source_root / (module.replace(".", "/") + ".py")
    source = compile(path.read_text(), str(path), "exec", dont_inherit=True)
    packed = archive.extract(module)
    assert (source.co_code, source.co_consts, source.co_names) == (
        packed.co_code, packed.co_consts, packed.co_names
    ), module
    print(f"{module}: entire frozen module matches source")
