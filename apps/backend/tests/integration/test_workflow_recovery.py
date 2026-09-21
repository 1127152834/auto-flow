import asyncio
import os
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from autoflow.infrastructure.process.workflow_recovery import recover_worker_directories


@pytest.mark.asyncio
async def test_absent_run_has_no_cleanup_work(tmp_path):
    await recover_worker_directories(tmp_path, str(uuid4()), tmp_path / 'missing-kernel')


@pytest.mark.asyncio
async def test_recovery_only_removes_verified_run_generation(tmp_path, monkeypatch):
    monkeypatch.setattr('autoflow.infrastructure.process.workflow_recovery.sys', SimpleNamespace(platform='darwin'))
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
    monkeypatch.setattr(module, 'signal_processes', lambda *_args: None)
    monkeypatch.setattr(module, 'signal', SimpleNamespace(SIGTERM=15, SIGKILL=9))
    await recover_worker_directories(tmp_path, run_id, tmp_path / 'CloakBrowser')
    assert scans and all(folder == directory for folder in scans)
    assert not directory.exists()
    assert other.exists()


@pytest.mark.asyncio
async def test_uncertain_process_cleanup_preserves_directory(tmp_path, monkeypatch):
    monkeypatch.setattr('autoflow.infrastructure.process.workflow_recovery.sys', SimpleNamespace(platform='darwin'))
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
    monkeypatch.setattr('autoflow.infrastructure.process.workflow_recovery.sys', SimpleNamespace(platform='darwin'))
    import autoflow.infrastructure.process.project_browser_processes as processes

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
    from autoflow.bootstrap.workflows import configure_project_workflow_runtime
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

    dispatcher = configure_project_workflow_runtime(
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
            assert app.state.project_workflow_runtime.query_run(run_id=queued.run_id).status == 'reconciling'
        recovered = await dispatcher.reconcile(queued.run_id)
        assert recovered.status == 'interrupted'
    finally:
        await dispatcher.shutdown()
        factory.dispose()


@pytest.mark.asyncio
async def test_windows_restart_keeps_directory_without_native_ownership(tmp_path, monkeypatch):
    monkeypatch.setattr('autoflow.infrastructure.process.workflow_recovery.sys', SimpleNamespace(platform='win32'))
    run_id = str(uuid4())
    directory = tmp_path / 'workflow-runs' / run_id / 'generation-1'
    directory.mkdir(parents=True)
    with pytest.raises(RuntimeError, match='Windows workflow restart cleanup needs native ownership'):
        await recover_worker_directories(tmp_path, run_id, tmp_path / 'CloakBrowser')
    assert directory.exists()


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != 'win32', reason='requires native Windows Job ownership')
@pytest.mark.parametrize('mode', ['live', 'root-exit', 'wrong-birth', 'foreign-job', 'denied'])
async def test_native_windows_recovery_owns_job_and_descendants(tmp_path, monkeypatch, mode):
    import json

    from autoflow.infrastructure.process import windows_job
    from autoflow.infrastructure.process.browser_processes import (
        process_birth,
        process_identity_is_alive,
    )

    run_id = str(uuid4())
    directory = tmp_path / 'workflow-runs' / run_id / 'generation-1'
    directory.mkdir(parents=True)
    name = f'Local\\AutoFlow-{run_id}-1-{uuid4().hex}'
    code = """
import subprocess, sys, time
from autoflow.bootstrap.test_browser_worker import browser_worker_main
def run(stopped):
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    print(child.pid, flush=True)
    time.sleep(60)
    return 0
browser_worker_main(run)
"""
    async def spawn(job_name):
        return await asyncio.create_subprocess_exec(sys.executable, '-c', code, env={**os.environ, 'AUTOFLOW_WORKER_JOB_NAME': job_name}, stdout=asyncio.subprocess.PIPE)

    root = await spawn(name)
    foreign = None
    handle = None
    try:
        child_pid = int(await asyncio.wait_for(root.stdout.readline(), 10))
        child_birth, root_birth = process_birth(child_pid), process_birth(root.pid)
        assert child_birth is not None and root_birth is not None
        handle = windows_job.record_worker_job(directory, run_id, 1, name, root.pid, root_birth)
        windows_job.close_worker_job(handle)
        handle = None  # Simulate the original supervisor losing its retained handle.
        proof_path = directory / 'worker-job.json'
        original = proof_path.read_text()
        if mode in {'wrong-birth', 'foreign-job'}:
            proof = json.loads(original)
            if mode == 'wrong-birth':
                proof['birth'] += 1
            else:
                proof['name'] = f'Local\\AutoFlow-{run_id}-1-{uuid4().hex}'
                foreign = await spawn(proof['name'])
                assert int(await asyncio.wait_for(foreign.stdout.readline(), 10)) > 0
            proof_path.write_text(json.dumps(proof))
            with pytest.raises(OSError, match='does not own'):
                await recover_worker_directories(tmp_path, run_id, tmp_path / 'kernel')
            assert root.returncode is None and process_identity_is_alive(child_pid, child_birth)
            assert directory.exists()
            if foreign:
                assert foreign.returncode is None
            proof_path.write_text(original)
        elif mode == 'denied':
            api = windows_job._api
            class Denied:
                def __getattr__(self, name):
                    return getattr(api(), name)
                def TerminateJobObject(self, *_args):
                    return False
            with monkeypatch.context() as scoped:
                scoped.setattr(windows_job, '_api', Denied)
                with pytest.raises(OSError, match='termination denied'):
                    await recover_worker_directories(tmp_path, run_id, tmp_path / 'kernel')
            assert directory.exists() and process_identity_is_alive(child_pid, child_birth)
        elif mode == 'root-exit':
            root.kill()
            await root.wait()
            async with asyncio.timeout(5):
                while process_identity_is_alive(child_pid, child_birth):
                    await asyncio.sleep(.02)
        await recover_worker_directories(tmp_path, run_id, tmp_path / 'kernel', timeout=3)
        await asyncio.wait_for(root.wait(), 5)
        assert not directory.exists()
        assert not process_identity_is_alive(child_pid, child_birth)
        if foreign:
            assert foreign.returncode is None
    finally:
        if handle:
            windows_job.close_worker_job(handle)
        for process in [root, foreign]:
            if process is not None:
                if process.returncode is None:
                    process.kill()
                await process.wait()


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != 'win32', reason='requires native Windows junctions')
async def test_native_windows_recovery_rejects_junction_before_reading_ownership(tmp_path):
    import subprocess
    run_id = str(uuid4())
    run = tmp_path / 'workflow-runs' / run_id
    run.parent.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'keep').write_text('foreign')
    await asyncio.to_thread(subprocess.run, ['cmd', '/c', 'mklink', '/J', str(run), str(outside)], capture_output=True, check=True)
    with pytest.raises(RuntimeError, match='ownership path'):
        await recover_worker_directories(tmp_path, run_id, tmp_path / 'kernel')
    assert (outside / 'keep').read_text() == 'foreign'
