import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioDebugControlLookup,
    StudioDebugControlReceipt,
    StudioDebugControlRequest,
    StudioDebugVariablesReceipt,
    StudioDebugVariablesRequest,
)

BASE = {'commandId': 'command', 'runId': 'run', 'pauseId': 'pause', 'controlRevision': 1}


def test_debug_request_and_lookup_roundtrip():
    assert StudioDebugControlRequest.model_validate(BASE).model_dump(by_alias=True) == BASE
    receipt = {**BASE, 'workflowId': 'workflow', 'action': 'step', 'success': True, 'error': None, 'httpStatus': 200}
    assert StudioDebugControlLookup.model_validate(receipt).model_dump(by_alias=True) == receipt


@pytest.mark.parametrize('patch', [{'runId': ''}, {'pauseId': ''}, {'commandId': ' '}, {'controlRevision': -1}, {'controlRevision': True}, {'controlRevision': '1'}, {'controlRevision': 1.5}, {'extra': 1}])
def test_debug_request_requires_explicit_context(patch):
    with pytest.raises(ValidationError):
        StudioDebugControlRequest.model_validate({**BASE, **patch})


@pytest.mark.parametrize('patch', [{'action': 'jump'}, {'success': 'true'}, {'success': False, 'error': None}, {'success': True, 'error': 'failed'}])
def test_debug_receipt_rejects_ambiguous_outcome(patch):
    with pytest.raises(ValidationError):
        StudioDebugControlReceipt.model_validate({**BASE, 'workflowId': 'workflow', 'action': 'step', 'success': True, 'error': None, **patch})


def test_debug_lookup_rejects_success_with_failure_status():
    with pytest.raises(ValidationError):
        StudioDebugControlLookup.model_validate({**BASE, 'workflowId': 'workflow', 'action': 'resume', 'success': True, 'error': None, 'httpStatus': 500})


def test_debug_variables_request_and_receipt_roundtrip():
    request = {**BASE, 'changes': [{'name': 'count', 'value': 2}, {'name': 'items', 'value': ['first']}]}
    assert StudioDebugVariablesRequest.model_validate(request).model_dump(by_alias=True) == request
    receipt = {**request, 'workflowId': 'workflow', 'success': True, 'error': None}
    assert StudioDebugVariablesReceipt.model_validate(receipt).model_dump(by_alias=True) == receipt


@pytest.mark.parametrize('changes', [[], [{'name': '1bad', 'value': 1}], [{'name': 'same', 'value': 1}, {'name': 'same', 'value': 2}]])
def test_debug_variables_reject_invalid_batches(changes):
    with pytest.raises(ValidationError):
        StudioDebugVariablesRequest.model_validate({**BASE, 'changes': changes})


def test_debug_variables_reject_request_larger_than_one_mib():
    with pytest.raises(ValidationError):
        StudioDebugVariablesRequest.model_validate({**BASE, 'changes': [{'name': 'large', 'value': 'x' * (1024 * 1024)}]})
