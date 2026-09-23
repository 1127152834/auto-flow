"""Run with backend uv Python and the frozen executable path as argument."""
import sys
import types

from PyInstaller.archive.readers import CArchiveReader
from autoflow.application.environments.service import EnvironmentService
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.infrastructure.process.project_workflow_worker import ProjectWorkflowWorkerManager

archive = CArchiveReader(sys.argv[1]).open_embedded_archive('PYZ.pyz')


def walk(code):
    yield code
    for value in code.co_consts:
        if isinstance(value, types.CodeType):
            yield from walk(value)


for module, cls, names in [
    ('autoflow.application.environments.service', EnvironmentService,
     ['open_manual', 'cleanup_terminal_tasks', 'close_instance']),
    ('autoflow.application.project_runs.scheduler', ProjectBatchScheduler, ['tick']),
    ('autoflow.infrastructure.process.project_workflow_worker', ProjectWorkflowWorkerManager, ['run']),
]:
    codes = list(walk(archive.extract(module)))
    for name in names:
        packed = next(code for code in codes if code.co_name == name)
        source = getattr(cls, name).__code__
        assert (packed.co_code, packed.co_consts, packed.co_names) == (
            source.co_code, source.co_consts, source.co_names
        ), (module, name)
        print(f'{module}.{name}: frozen bytecode matches final source')
