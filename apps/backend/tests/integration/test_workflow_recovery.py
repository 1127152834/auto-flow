import asyncio
import os
import sys
from uuid import uuid4

import pytest

from autoflow.infrastructure.process.workflow_recovery import recover_worker_directories


@pytest.mark.asyncio
async def test_absent_run_has_no_cleanup_work(tmp_path):
    await recover_worker_directories(tmp_path, str(uuid4()), tmp_path / 'missing-kernel')


@pytest.mark.asyncio
async def test_recovery_only_removes_verified_run_generation(tmp_path, monkeypatch):
    import autoflow.infrastructure.process.workflow_recovery as module

    run_id = str(uuid4())
    directory = tmp_path / 'workflow-runs' / run_id / 'generation-1'
    directory.mkdir(parents=True)
    (directory / 'cache').write_text('synthetic')
    other = tmp_path / 'workflow-runs' / str(uuid4()) / 'generation-1'
    other.mkdir(parents=True)
    scans = []

    def capture(pid, birth, folder, executable, previous=None, **_kwargs):
        scans.append(folder)
        return {}

    monkeypatch.setattr(module, 'capture_processes', capture)
    await recover_worker_directories(tmp_path, run_id, tmp_path / 'CloakBrowser')
    assert scans and all(folder == directory for folder in scans)
    assert not directory.exists()
    assert other.exists()


@pytest.mark.asyncio
async def test_uncertain_process_cleanup_preserves_directory(tmp_path, monkeypatch):
    import autoflow.infrastructure.process.workflow_recovery as module

    run_id = str(uuid4())
    directory = tmp_path / 'workflow-runs' / run_id / 'generation-1'
    directory.mkdir(parents=True)

    def uncertain(*_args, **_kwargs):
        raise RuntimeError('native ownership unavailable')

    monkeypatch.setattr(module, 'capture_processes', uncertain)
    with pytest.raises(RuntimeError, match='native ownership unavailable'):
        await recover_worker_directories(tmp_path, run_id, tmp_path / 'CloakBrowser')
    assert directory.exists()


@pytest.mark.asyncio
async def test_unreadable_live_native_candidate_is_not_proof_of_cleanup(tmp_path, monkeypatch):
    import autoflow.infrastructure.process.browser_processes as processes

    run_id = str(uuid4())
    directory = tmp_path / 'workflow-runs' / run_id / 'generation-1'
    directory.mkdir(parents=True)
    monkeypatch.setattr(processes.subprocess, 'check_output', lambda *_args, **_kwargs: '123 1 123 python --workflow-worker\n')
    monkeypatch.setattr(processes, 'process_birth', lambda _pid: 123)
    monkeypatch.setattr(processes, '_process_exists', lambda _pid: True)
    monkeypatch.setattr(processes, '_native_arguments', lambda _pid: None)
    with pytest.raises(RuntimeError):
        await recover_worker_directories(tmp_path, run_id, tmp_path / 'CloakBrowser')
    assert directory.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize('symlink_level', ['run', 'generation'])
async def test_recovery_rejects_symlink_ownership(tmp_path, symlink_level):
    run_id = str(uuid4())
    run = tmp_path / 'workflow-runs' / run_id
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'keep').write_text('do not remove')
    if symlink_level == 'run':
        run.parent.mkdir()
        run.symlink_to(outside, target_is_directory=True)
    else:
        run.mkdir(parents=True)
        (run / 'generation-1').symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeError):
        await recover_worker_directories(tmp_path, run_id, tmp_path / 'CloakBrowser')
    assert (outside / 'keep').read_text() == 'do not remove'


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == 'win32', reason='native POSIX ownership test')
async def test_real_orphan_process_is_terminated_before_removing_cache(tmp_path):
    run_id = str(uuid4())
    directory = tmp_path / 'workflow-runs' / run_id / 'generation-1'
    directory.mkdir(parents=True)
    env = {**os.environ, 'CLOAKBROWSER_CACHE_DIR': str(directory)}
    process = await asyncio.create_subprocess_exec(
        sys.executable, '-c', "import time; print('ready',flush=True); time.sleep(60)",
        '--workflow-worker', env=env, start_new_session=True,
        stdout=asyncio.subprocess.PIPE,
    )
    try:
        assert await process.stdout.readline() == b'ready\n'
        await recover_worker_directories(tmp_path, run_id, tmp_path / 'CloakBrowser', timeout=.3)
        await asyncio.wait_for(process.wait(), 2)
        assert process.returncode is not None
        assert not directory.exists()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


@pytest.mark.asyncio
async def test_bootstrap_recovery_waits_for_profile_guard_release(tmp_path):
    from fastapi import FastAPI

    from autoflow.application.settings.runtime import QuiesceGate
    from autoflow.bootstrap.workflows import configure_workflow_runtime
    from autoflow.domain.kernels.models import InstalledKernel
    from autoflow.infrastructure.database.session import (
        create_session_factory,
        migrate_database,
    )
    from autoflow.infrastructure.database.workflow_runtime import (
        SqlAlchemyWorkflowRuntimeRepository,
    )
    from autoflow.infrastructure.filesystem.kernel_installations import (
        FilesystemKernelInstallationStore,
    )
    from autoflow.infrastructure.filesystem.profile_data import (
        FilesystemProfileUsageGuard,
    )
    from tests.fixtures.workflow_runs import NOW, create_queued_run

    database = tmp_path / 'data.sqlite3'
    migrate_database(database)
    factory = create_session_factory(database)
    guard = FilesystemProfileUsageGuard(tmp_path / 'profiles')
    profile_id = str(uuid4())
    executable = tmp_path / 'CloakBrowser'
    executable.write_text('synthetic')
    kernel = InstalledKernel('public', '145.0.7632.109.2', executable, 9)
    app = FastAPI()

    async def proxy(*_args):
        raise AssertionError('recovery must not resolve proxies or execute')

    dispatcher = configure_workflow_runtime(
        app, session_factory=factory, profiles=None, installed=lambda: [kernel],
        resolve_proxy=proxy, read_license=lambda: None, usage_guard=guard,
        installations=FilesystemKernelInstallationStore(tmp_path / 'kernels'),
        temp_dir=tmp_path / 'tmp', gate=QuiesceGate(),
    )
    try:
        queued, _ = create_queued_run(factory, resource_request={
            'profileId': profile_id, 'kernelId': f'{kernel.edition}:{kernel.version}',
        })
        with factory() as session:
            SqlAlchemyWorkflowRuntimeRepository(session).transition_run(
                queued.run_id, target_status='running', expected_status_revision=1,
                expected_execution_generation=0, now=NOW,
            )
            session.commit()
        with guard.guard(profile_id):
            await dispatcher.startup()
            assert app.state.workflow_runtime.query_run(run_id=queued.run_id).status == 'reconciling'
        recovered = await dispatcher.reconcile(queued.run_id)
        assert recovered.status == 'interrupted'
    finally:
        await dispatcher.shutdown()
        factory.dispose()
