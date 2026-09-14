import pytest
from pydantic import ValidationError

from autoflow.adapters.http.workflow_studio_schemas import (
    StudioMcpConfig,
    StudioMcpReloaded,
    StudioMcpSaved,
    StudioMcpStatus,
)


@pytest.mark.parametrize('transport', [None, '', 'stdio', 'sse', 'http', 'HTTP', 'Streamable_HTTP', 'streamable-http'])
def test_mcp_config_preserves_wire_fields_and_extensions(transport):
    data = {'mcpServers': {'fixture': {'transport': transport, 'env': {'KEY': 'a=b'}, 'autoApprove': ['read'], 'extensionSetting': {'enabled': True}}}, 'extensionRoot': 1}
    assert StudioMcpConfig.model_validate(data).model_dump(by_alias=True, exclude_unset=True) == data


@pytest.mark.parametrize('server', [{'transport': 'ftp'}, {'args': 1}, {'args': [1]}, {'headers': {'A': 1}}, {'disabled': 'false'}, {'autoApprove': 'read'}])
def test_invalid_mcp_fields_rejected(server):
    with pytest.raises(ValidationError):
        StudioMcpConfig.model_validate({'mcpServers': {'fixture': server}})


@pytest.mark.parametrize('data', [{}, {'mcpServers': []}, {'mcpServers': {'': {}}}, {'mcpServers': {'fixture': None}}])
def test_invalid_mcp_configuration_rejected(data):
    with pytest.raises(ValidationError):
        StudioMcpConfig.model_validate(data)


def test_mcp_status_preserves_snake_case_wire_fields():
    data = {'servers': [{'name': 'fixture', 'transport': 'http', 'disabled': False, 'connected': False, 'tool_count': 0, 'tools': [], 'last_error': 'offline', 'connected_at': None, 'auto_approve': []}], 'total_tools_injected': 0}
    assert StudioMcpStatus.model_validate(data).model_dump(by_alias=True) == data


@pytest.mark.parametrize('value', [-1, True, '1', 1.5])
def test_mcp_status_count_is_nonnegative_integer(value):
    with pytest.raises(ValidationError):
        StudioMcpStatus.model_validate({'servers': [], 'total_tools_injected': value})


@pytest.mark.parametrize('data', [{}, {'success': True}, {'success': False, 'saved': True}, {'success': 1, 'saved': True}, {'success': True, 'saved': 'true'}])
def test_save_requires_explicit_true_booleans(data):
    with pytest.raises(ValidationError):
        StudioMcpSaved.model_validate(data)


def test_mcp_reload_preserves_partial_failure_without_success_fabrication():
    data = {'connected': [], 'failed': [{'name': 'fixture', 'error': 'mock does not connect'}], 'disabled': ['off'], 'total_servers': 2}
    assert StudioMcpReloaded.model_validate(data).model_dump(by_alias=True) == data
