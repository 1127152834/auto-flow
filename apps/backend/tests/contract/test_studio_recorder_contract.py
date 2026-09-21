import pytest
from autoflow.adapters.http.workflow_studio_schemas import (
    StudioRecorderBatch,
    StudioRecorderCommandState,
    StudioRecorderControl,
    StudioRecorderReadRequest,
    StudioRecorderStartRequest,
    StudioRecorderStatus,
    StudioRecorderStopped,
)
from pydantic import ValidationError


def test_stable_session_and_cursor():
    assert StudioRecorderStartRequest.model_validate({'sessionId': 'session', 'commandId': 'start-1'}).session_id == 'session'
    assert StudioRecorderReadRequest.model_validate({'sessionId': 'session', 'commandId': 'stop-1'}).after_seq == 0


@pytest.mark.parametrize('value', [
    {'success': True, 'sessionId': None, 'recording': False, 'paused': False, 'nextSeq': 0},
    {'success': True, 'sessionId': 'session', 'recording': True, 'paused': True, 'nextSeq': 3},
    {'success': True, 'sessionId': 'session', 'recording': False, 'paused': False, 'nextSeq': 3},
])
def test_recorder_status_roundtrip(value):
    assert StudioRecorderStatus.model_validate(value).model_dump(by_alias=True) == value


@pytest.mark.parametrize('patch', [
    {'recording': 'true'}, {'nextSeq': -1}, {'nextSeq': 1.5}, {'nextSeq': True},
    {'sessionId': ''}, {'sessionId': None, 'recording': True},
    {'sessionId': None, 'recording': False, 'nextSeq': 1},
])
def test_recorder_status_requires_a_valid_owner_and_cursor(patch):
    with pytest.raises(ValidationError):
        StudioRecorderStatus.model_validate({'success': True, 'sessionId': 'session', 'recording': False, 'nextSeq': 0, **patch})


@pytest.mark.parametrize('value', [
    {}, {'sessionId': ''}, {'sessionId': ' '}, {'sessionId': 1},
    {'sessionId': 's', 'afterSeq': -1}, {'sessionId': 's', 'afterSeq': '1'},
    {'sessionId': 's', 'afterSeq': True}, {'sessionId': 's', 'afterSeq': 1.5},
    {'sessionId': 's', 'afterSeq': 9007199254740992},
])
def test_invalid_read_identity_or_cursor(value):
    with pytest.raises(ValidationError):
        StudioRecorderReadRequest.model_validate(value)


@pytest.mark.parametrize('stopped', [False, True])
def test_batch_roundtrip(stopped):
    events = [{'sequence': 1, 'type': 'input', 'selector': '#name', 'value': '中文'}]
    value = {'success': True, 'sessionId': 's', 'nextSeq': 1, 'data': {'events': events} if stopped else events}
    if stopped:
        value['commandId'] = 'stop-1'
    model = StudioRecorderStopped if stopped else StudioRecorderBatch
    assert model.model_validate(value).model_dump(by_alias=True, exclude_unset=True) == value


def test_pause_control_requires_an_active_recording_and_keeps_tail():
    value = {'success': True, 'commandId': 'pause-1', 'sessionId': 's', 'recording': True, 'paused': True, 'nextSeq': 1, 'data': {'events': [{'sequence': 1, 'type': 'click'}]}}
    assert StudioRecorderControl.model_validate(value).model_dump(by_alias=True, exclude_unset=True) == value
    with pytest.raises(ValidationError):
        StudioRecorderControl.model_validate({**value, 'recording': False})


def test_recorder_command_lookup_distinguishes_pending_completed_and_failed():
    base = {'success': True, 'commandId': 'cmd', 'sessionId': 's', 'action': 'pause', 'httpStatus': 202}
    StudioRecorderCommandState.model_validate({**base, 'status': 'pending'})
    StudioRecorderCommandState.model_validate({**base, 'status': 'completed', 'httpStatus': 200, 'result': {'success': True}})
    StudioRecorderCommandState.model_validate({**base, 'status': 'failed', 'httpStatus': 409, 'error': '冲突', 'errorCode': 'CONFLICT'})
    with pytest.raises(ValidationError):
        StudioRecorderCommandState.model_validate({**base, 'status': 'completed'})


@pytest.mark.parametrize('events,next_seq', [
    ([{'sequence': 1, 'type': 'click'}], 2),
    ([{'sequence': 1, 'type': 'click'}, {'sequence': 3, 'type': 'click'}], 3),
    ([{'sequence': 1, 'type': 'click'}, {'sequence': 1, 'type': 'click'}], 1),
    ([{'sequence': '1', 'type': 'click'}], 1),
    ([{'sequence': 0, 'type': 'click'}], 0),
    ([{'sequence': 1, 'type': 'unknown'}], 1),
    ([None], 1),
])
def test_invalid_batch(events, next_seq):
    with pytest.raises(ValidationError):
        StudioRecorderBatch.model_validate({'success': True, 'sessionId': 's', 'nextSeq': next_seq, 'data': events})


def test_review_keeps_user_order_and_extra_action_fields():
    from autoflow.adapters.http.workflow_studio_schemas import (
        StudioRecordingReviewWrite,
    )

    payload = {'expectedRevision': 0, 'autoWait': False, 'events': [
        {'sequence': 2, 'type': 'input', 'selector': '#name', 'value': '中文', 'variableName': 'name'},
        {'sequence': 1, 'type': 'navigate', 'url': 'https://local.test'},
    ]}
    assert StudioRecordingReviewWrite.model_validate(payload).model_dump(by_alias=True) == payload


@pytest.mark.parametrize('patch', [{'expectedRevision': -1}, {'expectedRevision': True}, {'autoWait': 'false'}, {'events': [{'sequence': 0, 'type': 'input'}]}, {'events': [{'sequence': 1, 'type': 'unknown'}]}, {'unexpected': 1}])
def test_review_rejects_invalid_contract(patch):
    from autoflow.adapters.http.workflow_studio_schemas import (
        StudioRecordingReviewWrite,
    )

    with pytest.raises(ValidationError):
        StudioRecordingReviewWrite.model_validate({'expectedRevision': 0, 'autoWait': True, 'events': [], **patch})
