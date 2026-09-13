import pytest

from autoflow.domain.workflows.inspection import inspection_target
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import prepare_run, resolve_node_config
from autoflow.domain.workflows.validation import workflow_issues
from tests.fixtures.workflows import workflow_payload


def test_frame_path_references_resolve_once_and_point_at_invalid_index():
    payload = workflow_payload()
    node = payload['document']['nodes'][1]
    node['config']['framePath'] = ['#{frame}']
    payload['document']['variables'] = [{'name': 'frame', 'type': 'string', 'value': 'outer'}]
    prepared = prepare_run(payload['document'], payload['layout'])
    assert resolve_node_config(prepared.document['nodes'][1], prepared.variables)['framePath'] == ['#outer']
    node['config']['framePath'] = ['#outer', 7]
    issues = workflow_issues(payload['document'])
    assert any(i.node_id == node['id'] and i.path == ['config', 'framePath', '1'] and i.code == 'INVALID_FRAME_PATH' for i in issues)


def test_hidden_screenshot_frame_path_references_are_not_used():
    payload = workflow_payload()
    payload['document']['nodes'][-1]['config']['framePath'] = ['{not_available}']
    prepare_run(payload['document'], payload['layout'])


@pytest.mark.parametrize('variables', [
    [{'name': 'x', 'type': 'string', 'value': '{future_output}'}],
    [{'name': 'x', 'type': 'string', 'value': '{y}'}, {'name': 'y', 'type': 'string', 'value': '{x}'}],
    [{'name': 'x', 'type': 'number', 'value': 'wrong'}],
])
def test_inspection_rejects_unavailable_or_invalid_initial_values(variables):
    with pytest.raises(WorkflowError):
        inspection_target('{x}', [], variables)
