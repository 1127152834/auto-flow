import pytest

from autoflow.domain.projects.models import ProjectError


def test_manual_resume_validates_declared_values_target_and_required_context():
    from autoflow.domain.workflows.manual_contract import validate_resume
    contract = {'inputSchema': [{'name': 'code', 'type': 'string', 'required': True, 'enum': ['001', '002']}], 'resumeTargets': [{'nodeId': 'next', 'requiredVariables': ['code', 'session']}], 'availableVariables': ['session']}
    assert validate_resume(contract, {'inputs': {'code': '001'}, 'targetNodeId': 'next'}) == {'code': '001'}
    for body in [{'inputs': {}}, {'inputs': {'code': 1}}, {'inputs': {'code': '003'}}, {'inputs': {'code': '001', 'extra': 1}}, {'inputs': {'code': '001'}, 'targetNodeId': 'foreign'}]:
        with pytest.raises(ProjectError): validate_resume(contract, body)
    with pytest.raises(ProjectError, match='session'):
        validate_resume({**contract, 'availableVariables': []}, {'inputs': {'code': '001'}, 'targetNodeId': 'next'})


@pytest.mark.parametrize(('kind', 'value'), [('number', True), ('integer', 1.5), ('boolean', 'false'), ('array', {}), ('object', []), ('number', float('nan'))])
def test_manual_declared_json_types_are_strict(kind, value):
    from autoflow.domain.workflows.manual_contract import validate_resume
    with pytest.raises(ProjectError): validate_resume({'inputSchema': [{'name': 'value', 'type': kind}], 'resumeTargets': []}, {'inputs': {'value': value}})
