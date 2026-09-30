from autoflow.domain.workflows.execution import ExecutionContext


def test_project_input_context_is_separate_and_returns_copies():
    context = ExecutionContext(variables={'PROJECT_INPUTS': {'account': 'wrong'}}, project_input_context={
        'PROJECT_INPUTS': {'account': {'values': {'email': 'one@example.test'}}},
        'PROJECT_PARAMETERS': {'flag': False},
    })
    reference = "{PROJECT_INPUTS['account']['values']['email']}"
    assert context.resolve_value(reference) == 'one@example.test'
    assert context.resolve_value("{PROJECT_PARAMETERS['flag']}", preserve_types=True) is False
    value = context.resolve_value("{PROJECT_INPUTS['account']}", preserve_types=True)
    value['values']['email'] = 'mutated'
    assert context.resolve_value(reference) == 'one@example.test'


def test_reference_rename_survives_but_removal_and_type_change_are_node_errors():
    from types import SimpleNamespace

    import pytest

    from autoflow.domain.project_runs.models import ProjectRunError
    from autoflow.domain.workflows.project_inputs import validate_references
    automation = SimpleNamespace(input_plan={'inputs': [{'inputId': 'account', 'alias': 'renamed', 'fieldBindings': [{'inputFieldId': 'email', 'inputFieldAlias': 'renamed field', 'fieldRef': {'fieldId': 'physical'}}]}]}, parameter_schema=[{'parameterId': 'flag', 'name': 'renamed flag', 'type': 'boolean'}])
    reference = "PROJECT_INPUTS['account']['values']['email']"
    doc = {'nodes': [{'id': 'node', 'data': {'value': '{' + reference + '}', 'projectInputTypes': {reference: 'string'}}}]}
    validate_references(doc, automation, {'physical': 'string'})
    for types in ({'physical': 'number'}, {}):
        with pytest.raises(ProjectRunError) as error:
            validate_references(doc, automation, types)
        assert error.value.details['nodeId'] == 'node'
    doc['nodes'][0]['data']['value'] = '{' + reference.replace("'", '"') + '}'
    with pytest.raises(ProjectRunError):
        validate_references(doc, automation, {'physical': 'number'})
    automation.input_plan = {'inputs': []}
    with pytest.raises(ProjectRunError):
        validate_references(doc, automation, {'physical': 'string'})
    doc['nodes'][0]['data'] = {'label': '{' + reference + '}', 'value': reference}
    validate_references(doc, automation, {})
