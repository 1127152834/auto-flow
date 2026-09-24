from copy import deepcopy

import pytest

from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import prepare_run
from tests.fixtures.workflows import workflow_payload


def document(configuration):
    value = workflow_payload()
    value['content']['browserEnvironmentVersion'] = 1
    value['content']['schemaVersion'] = 3
    node = next(node for node in value['content']['nodes'] if node['id'] == 'open')
    node['data']['browserEnvironment'] = configuration
    return value


@pytest.mark.parametrize('configuration', [
    {'source': 'current', 'profileId': 'hidden-template'},
    {'source': 'fixedEnvironment', 'environmentId': 'environment', 'proxy': {'mode': 'none'}},
    {'source': 'newFromProfile', 'proxy': {'mode': 'fixed', 'proxyId': ''}},
    {'source': 'newFromProfile', 'kernel': {'edition': 'external', 'version': '1'}},
    {'source': 'inputEnvironment', 'inputId': ''},
    {'source': 'newFromProfile', 'userDataDir': '/tmp/untrusted'},
    None,
])
def test_new_contract_rejects_inapplicable_or_incomplete_browser_parameters(configuration):
    with pytest.raises(WorkflowError) as error:
        prepare_run(document(configuration))
    assert any(issue.node_id == 'open' and 'browserEnvironment' in issue.path for issue in error.value.issues)


def test_node_mode_is_persisted_and_legacy_documents_are_not_silently_migrated():
    value = document({'source': 'newFromProfile', 'proxy': {'mode': 'sourceDefault'}})
    snapshot = deepcopy(value)
    prepared = prepare_run(value)
    assert prepared.document['content']['browserEnvironmentVersion'] == 1
    assert value == snapshot
    old = workflow_payload()
    assert 'browserEnvironmentVersion' not in prepare_run(old).document['content']


def test_unknown_mode_version_is_rejected_and_node_config_requires_opt_in():
    value = document({'source': 'current'})
    value['content']['browserEnvironmentVersion'] = 2
    with pytest.raises(WorkflowError):
        prepare_run(value)
    del value['content']['browserEnvironmentVersion']
    with pytest.raises(WorkflowError):
        prepare_run(value)


def test_preparation_freezes_node_defaults_and_kernel_without_opening_browser(tmp_path, valid_profile_values):
    from autoflow.application.project_runs.resources import ProjectRunResourceResolver
    from tests.unit.test_project_run_resources import ResourceQuery, automation
    from tests.unit.test_workflow_browser_resources import resources
    browser, state, original = resources(tmp_path, valid_profile_values)
    defaults = {'profileId': original.id, 'proxy': {'mode': 'fixed', 'proxyId': 'project-proxy'}}
    value = document({'source': 'newFromProfile', 'kernel': {'edition': original.spec.browser_edition, 'version': original.spec.browser_version}})
    frozen = ProjectRunResourceResolver(ResourceQuery(), browser)(automation({'source': 'newFromProfile'}), defaults, document=value)
    defaults['proxy']['proxyId'] = 'later'
    node = frozen['nodeBrowserEnvironments']['open']
    assert frozen['browser'] == 'node'
    assert node['frozenConfiguration']['profileSpec']['proxy_id'] == 'project-proxy'
    assert node['frozenConfiguration']['fingerprintSeed'] == 42
    assert node['kernelId'] == f'{original.spec.browser_edition}:{original.spec.browser_version}'
    assert state['holds'] == 0
    assert 'proxy_profile' not in state
    assert 'license' not in str(frozen).lower()

@pytest.mark.asyncio
async def test_delayed_browser_failure_captures_actual_current_page():
    from types import SimpleNamespace

    from autoflow.providers.browser.project_graph import ProjectGraphExecutor
    raw_page = object()
    session = SimpleNamespace(current_page=lambda: SimpleNamespace(_raw=raw_page))
    captured = []
    async def emit(*_): pass
    async def capture(page, *_):
        captured.append(page)
        return {'status':'captured'}
    graph = ProjectGraphExecutor(None, {}, emit, lambda: False, capture_failure=capture)
    graph.graph_adapter = True
    graph.context.browser = session
    graph.nodes = {'open': {'moduleType':'open_page'}}
    await graph.publish({'type':'execution:node_start','nodeId':'open','executionId':'visit'})
    await graph.publish({'type':'execution:node_complete','nodeId':'open','executionId':'visit','success':False,'error':'navigation failed'})
    assert captured == [raw_page]
