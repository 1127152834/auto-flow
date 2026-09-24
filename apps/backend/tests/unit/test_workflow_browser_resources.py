from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from autoflow.application.workflows.browser_resources import WorkflowBrowserResources
from autoflow.domain.kernels.models import InstalledKernel
from autoflow.domain.profiles.models import Profile, ProfileSpec


def resources(tmp_path, valid_profile_values):
    now = datetime.now(UTC)
    original = Profile('f6d83744-96d8-4b1c-a001-a1662c32db4a', ProfileSpec.from_values(valid_profile_values), 42, now, now)
    state = {'profile': original, 'holds': 0}
    executable = tmp_path / 'CloakBrowser'
    executable.write_text('synthetic')
    kernel = InstalledKernel(original.spec.browser_edition, original.spec.browser_version, executable, 9)

    @contextmanager
    def guard(_ref):
        state['holds'] += 1
        try:
            yield
        finally:
            state['holds'] -= 1

    async def proxy(profile, request_id):
        state['proxy_profile'] = profile

    service = WorkflowBrowserResources(
        SimpleNamespace(get=lambda _id: state['profile']),
        lambda: [kernel], proxy, lambda: 'synthetic-license',
        SimpleNamespace(guard=guard), guard,
    )
    return service, state, original


@pytest.mark.asyncio
async def test_resource_snapshot_uses_original_settings_and_holds_locks(tmp_path, valid_profile_values):
    service, state, original = resources(tmp_path, valid_profile_values)
    request = service.freeze(original.id)
    state['profile'] = Profile(original.id, ProfileSpec.from_values({**valid_profile_values, 'name': 'later edit'}), 999, original.created_at, original.updated_at)
    lease = await service.acquire(request, 'request-1')
    assert lease.browser['fingerprintSeed'] == 42
    assert lease.browser['headless'] == original.spec.headless
    assert state['holds'] == 2
    assert 'licenseKey' not in repr(request)
    assert not any(isinstance(item, Path) for item in request.values())
    lease.release()
    lease.release()
    assert state['holds'] == 0


@pytest.mark.asyncio
async def test_proxy_override_is_applied_to_frozen_profile(tmp_path, valid_profile_values):
    service, state, original = resources(tmp_path, valid_profile_values)
    request = service.freeze(original.id, proxy={'mode':'fixed','proxyId':'chosen'})
    lease = await service.acquire(request, 'request-1')
    assert state['proxy_profile'].spec.proxy_mode == 'proxy'
    assert state['proxy_profile'].spec.proxy_id == 'chosen'
    lease.release()


@pytest.mark.asyncio
async def test_resource_resolution_failure_releases_acquired_locks(tmp_path, valid_profile_values):
    service, state, original = resources(tmp_path, valid_profile_values)
    request = service.freeze(original.id)

    async def unavailable(*_args):
        raise RuntimeError('synthetic proxy resolution failure')

    service._resolve_proxy = unavailable
    with pytest.raises(RuntimeError, match='synthetic proxy resolution failure'):
        await service.acquire(request, 'request-1')
    assert state['holds'] == 0


def test_proxy_snapshot_rejects_unrecognized_private_or_path_fields(tmp_path, valid_profile_values):
    from autoflow.domain.workflows.runtime import WorkflowRuntimeError

    service, _, original = resources(tmp_path, valid_profile_values)
    with pytest.raises(WorkflowRuntimeError) as caught:
        service.freeze(original.id, proxy={
            'mode': 'none', 'password': 'synthetic-secret',
            'executablePath': '/synthetic/arbitrary',
        })
    assert caught.value.code == 'WORKFLOW_RESOURCE_INVALID'
    assert 'synthetic-secret' not in str(caught.value)


def test_empty_proxy_policy_is_invalid(tmp_path, valid_profile_values):
    from autoflow.domain.workflows.runtime import WorkflowRuntimeError

    service, _, original = resources(tmp_path, valid_profile_values)
    with pytest.raises(WorkflowRuntimeError):
        service.freeze(original.id, proxy={})


@pytest.mark.asyncio
async def test_invalid_snapshot_has_resource_error_without_taking_guards(tmp_path, valid_profile_values):
    from autoflow.domain.workflows.runtime import WorkflowRuntimeError

    service, state, original = resources(tmp_path, valid_profile_values)
    request = service.freeze(original.id)
    request['frozenConfiguration'] = {}
    with pytest.raises(WorkflowRuntimeError) as caught:
        await service.acquire(request, 'request-1')
    assert caught.value.code == 'WORKFLOW_RESOURCE_INVALID'
    assert state['holds'] == 0


@pytest.mark.asyncio
async def test_worker_payload_cannot_mutate_request_snapshot(tmp_path, valid_profile_values):
    service, _, original = resources(tmp_path, valid_profile_values)
    request = service.freeze(original.id)
    lease = await service.acquire(request, 'request-1')
    try:
        lease.browser['extensionPaths'].append('/synthetic')
        assert request['frozenConfiguration']['profileSpec']['extension_paths'] == []
    finally:
        lease.release()


@pytest.mark.asyncio
async def test_shared_source_guards_last_until_last_independent_work_copy(tmp_path, valid_profile_values):
    import subprocess
    import sys

    from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock
    service, _state, original = resources(tmp_path, valid_profile_values)
    held = []
    @contextmanager
    def exclusive(key):
        lock = ExclusiveFileLock(tmp_path / (key + '.lock'))
        assert lock.acquire(), key
        held.append(key)
        try: yield
        finally: lock.release(); held.remove(key)
    service._group_guard = lambda: exclusive('workspace')
    service._kernel_guard = lambda _kernel: exclusive('kernel')
    service._usage_guard = SimpleNamespace(guard=lambda _profile: exclusive('profile'))
    service._environment_directory = lambda identity: tmp_path / identity
    def outsider(key):
        script = 'import sys; from pathlib import Path; from autoflow.infrastructure.filesystem.locking import ExclusiveFileLock; lock=ExclusiveFileLock(Path(sys.argv[1])); sys.exit(0 if lock.acquire() else 1)'
        return subprocess.run([sys.executable, '-c', script, str(tmp_path / (key + '.lock'))], check=False).returncode
    first = await service.acquire(service.freeze(original.id), 'run-a')
    second = None
    try:
        second = await service.acquire(service.freeze(original.id), 'run-b')
        assert sorted(held) == ['kernel', 'profile', 'workspace']
        assert first.browser['userDataDir'] != second.browser['userDataDir']
        assert all(outsider(key) == 1 for key in held)
        first.release()
        assert sorted(held) == ['kernel', 'profile', 'workspace']
        assert all(outsider(key) == 1 for key in held)
        async def unavailable(*_args): raise RuntimeError('second resolve failed')
        service._resolve_proxy = unavailable
        with pytest.raises(RuntimeError, match='second resolve failed'):
            await service.acquire(service.freeze(original.id), 'run-c')
        assert sorted(held) == ['kernel', 'profile', 'workspace']
        second.release()
        assert held == [] and all(outsider(key) == 0 for key in ['workspace', 'kernel', 'profile'])
    finally:
        first.release()
        if second: second.release()


@pytest.mark.asyncio
async def test_unknown_native_guard_cleanup_pins_workspace_and_cannot_be_hidden_by_retry(tmp_path, valid_profile_values):
    service, _state, original = resources(tmp_path, valid_profile_values)
    workspace_closed = []
    @contextmanager
    def workspace():
        try: yield
        finally: workspace_closed.append(True)
    @contextmanager
    def uncertain(_identity):
        yield
        raise RuntimeError('native lock release unknown')
    service._group_guard = workspace
    service._usage_guard = SimpleNamespace(guard=uncertain)
    lease = await service.acquire(service.freeze(original.id), 'run-a')
    for _ in range(2):
        with pytest.raises(RuntimeError, match='native lock release unknown'): lease.release()
        assert not workspace_closed
    from autoflow.domain.workflows.runtime import WorkflowRuntimeError
    with pytest.raises(WorkflowRuntimeError, match='资源锁清理'):
        await service.acquire(service.freeze(original.id), 'run-b')
    assert not workspace_closed


@pytest.mark.asyncio
async def test_persistent_identity_wins_over_later_template_snapshot(tmp_path, valid_profile_values):
    from copy import deepcopy

    service, state, original = resources(tmp_path, valid_profile_values)
    saved = service.freeze(original.id, proxy={'mode': 'none'})
    state['profile'] = Profile(original.id, ProfileSpec.from_values({
        **valid_profile_values, 'locale': 'fr-FR', 'proxy_mode': 'proxy', 'proxy_id': 'later-proxy',
    }), 999, original.created_at, original.updated_at)
    request = service.freeze(original.id)
    request.update(browser='persistent', userDataDir=str(tmp_path / 'instance'), identityPackage={
        'schemaVersion': 1,
        'profileId': original.id,
        'kernelId': saved['kernelId'],
        'frozenConfiguration': deepcopy(saved['frozenConfiguration']),
    })
    lease = await service.acquire(request, 'saved-run')
    try:
        assert lease.browser['fingerprintSeed'] == 42
        assert state['proxy_profile'].spec.proxy_mode == 'none'
        assert state['proxy_profile'].spec.locale == original.spec.locale
    finally:
        lease.release()


@pytest.mark.asyncio
async def test_persistent_without_identity_is_not_restored_from_current_template(tmp_path, valid_profile_values):
    from autoflow.domain.workflows.runtime import WorkflowRuntimeError

    service, state, original = resources(tmp_path, valid_profile_values)
    request = service.freeze(original.id)
    request.update(browser='persistent', userDataDir=str(tmp_path / 'instance'))
    with pytest.raises(WorkflowRuntimeError) as caught:
        await service.acquire(request, 'legacy-run')
    assert caught.value.code == 'ENVIRONMENT_IDENTITY_UNVERIFIED'
    assert state['holds'] == 0

@pytest.mark.asyncio
async def test_studio_private_directory_does_not_query_project_task_identity(tmp_path, valid_profile_values):
    service, _, profile = resources(tmp_path, valid_profile_values)
    def project_directory(_request):
        raise AssertionError('Studio has no Project Task run identity')
    service._environment_directory = project_directory
    directory = tmp_path / 'owned-studio-worker' / 'preview'
    lease = await service.acquire(service.freeze(profile.id), 'studio-run', work_directory=directory)
    assert lease.browser['userDataDir'] == str(directory)
    lease.release()
