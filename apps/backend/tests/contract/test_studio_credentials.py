import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioCredentialConfirmed,
    StudioCredentialFieldsCommand,
    StudioCredentialFieldsConfirmed,
    StudioCredentialList,
    StudioCredentialRenameRequest,
    StudioCredentialSaved,
    StudioCredentialUpsertRequest,
)


def test_metadata_preserves_wire_names_and_does_not_require_secret_values():
    data = {'success': True, 'mock': True, 'credentials': [{
        'name': 'fixture', 'description': '', 'fields': [{'key': 'value', 'masked': '***'}],
        'created_at': '2026-09-14', 'updated_at': '2026-09-14', 'revision': 1,
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


def test_atomic_fields_wire_contract_has_no_secret_value():
    data = {'commandId': 'stable-id', 'name': 'fixture', 'expectedRevision': 1,
            'operations': [{'kind': 'rename', 'key': 'old', 'newKey': 'new'},
                           {'kind': 'remove', 'key': 'obsolete'}]}
    assert StudioCredentialFieldsCommand.model_validate(data).model_dump(by_alias=True) == data


@pytest.mark.parametrize('change', [
    {'expectedRevision': True}, {'expectedRevision': 0}, {'expectedRevision': 1.5},
    {'commandId': ''}, {'operations': []},
    {'operations': [{'kind': 'remove', 'key': 'value', 'secret': 'forbidden'}]},
    {'operations': [{'kind': 'rename', 'key': 'value'}]},
])
def test_atomic_fields_rejects_malformed_commands(change):
    data = {'commandId': 'stable-id', 'name': 'fixture', 'expectedRevision': 1,
            'operations': [{'kind': 'remove', 'key': 'old'}], **change}
    with pytest.raises(ValidationError):
        StudioCredentialFieldsCommand.model_validate(data)


def test_fields_confirmation_requires_command_and_masked_credential():
    with pytest.raises(ValidationError):
        StudioCredentialFieldsConfirmed.model_validate({'success': True, 'commandId': 'stable'})
