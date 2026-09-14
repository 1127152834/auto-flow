import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioCredentialConfirmed,
    StudioCredentialList,
    StudioCredentialRenameRequest,
    StudioCredentialSaved,
    StudioCredentialUpsertRequest,
)


def test_metadata_preserves_wire_names_and_does_not_require_secret_values():
    data = {'success': True, 'mock': True, 'credentials': [{
        'name': 'fixture', 'description': '', 'fields': [{'key': 'value', 'masked': '***'}],
        'created_at': '2026-09-14', 'updated_at': '2026-09-14',
    }]}
    assert StudioCredentialList.model_validate(data).model_dump(by_alias=True) == data


@pytest.mark.parametrize('value', [False, 1, 'true', None])
def test_confirmation_requires_a_true_boolean(value):
    with pytest.raises(ValidationError):
        StudioCredentialConfirmed.model_validate({'success': value})


@pytest.mark.parametrize('data', [
    {'name': 1, 'fields': {'value': 'x'}}, {'name': 'x', 'fields': []},
    {'name': 'x', 'fields': {'value': 1}}, {'name': '', 'fields': {'value': 'x'}},
    {'name': ' ', 'fields': {'value': 'x'}}, {'name': 'x', 'fields': {}},
    {'name': 'x', 'fields': {'value': ''}, 'description': 1},
])
def test_invalid_upsert_rejected(data):
    with pytest.raises(ValidationError):
        StudioCredentialUpsertRequest.model_validate(data)


@pytest.mark.parametrize('name', ['names', 'rename', '__proto__', 'constructor', '中文 凭据'])
def test_literal_names_and_blank_values_remain_compatible(name):
    data = {'name': name, 'fields': {'value': ''}, 'description': None}
    assert StudioCredentialUpsertRequest.model_validate(data).model_dump(by_alias=True) == data


def test_rename_preserves_snake_case():
    data = {'old_name': 'one', 'new_name': 'two'}
    assert StudioCredentialRenameRequest.model_validate(data).model_dump(by_alias=True) == data


@pytest.mark.parametrize('data', [
    {'old_name': 1, 'new_name': 'two'}, {'old_name': 'one', 'new_name': ' '},
    {'old_name': '', 'new_name': 'two'},
])
def test_invalid_rename_rejected(data):
    with pytest.raises(ValidationError):
        StudioCredentialRenameRequest.model_validate(data)


def test_saved_receipt_requires_name():
    with pytest.raises(ValidationError):
        StudioCredentialSaved.model_validate({'success': True})
