import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioRecorderBatch,
    StudioRecorderReadRequest,
    StudioRecorderStartRequest,
    StudioRecorderStatus,
    StudioRecorderStopped,
)


def test_stable_session_and_cursor():
    assert StudioRecorderStartRequest.model_validate({'sessionId': 'session'}).session_id == 'session'
    assert StudioRecorderReadRequest.model_validate({'sessionId': 'session'}).after_seq == 0


@pytest.mark.parametrize('value', [
    {'success': True, 'sessionId': None, 'recording': False, 'nextSeq': 0},
    {'success': True, 'sessionId': 'session', 'recording': True, 'nextSeq': 3},
    {'success': True, 'sessionId': 'session', 'recording': False, 'nextSeq': 3},
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
    model = StudioRecorderStopped if stopped else StudioRecorderBatch
    assert model.model_validate(value).model_dump(by_alias=True, exclude_unset=True) == value


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
