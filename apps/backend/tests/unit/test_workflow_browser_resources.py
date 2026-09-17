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
