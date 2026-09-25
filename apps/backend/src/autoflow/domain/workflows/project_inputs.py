"""Stable project input references; original snapshots never become mutable globals."""
from copy import deepcopy
from typing import Any


def input_context(inputs: list[dict[str, Any]], parameters: dict[str, Any]) -> dict[str, Any]:
    objects: dict[str, Any] = {}
    for item in inputs:
        if item.get('recordRef') is None:
            objects[item['inputId']] = None
            continue
        cells = {cell['fieldId']: cell['value'] for cell in item.get('values', [])}
        objects[item['inputId']] = {**deepcopy(item), 'values': {binding['inputFieldId']: deepcopy(cells[binding['fieldRef']['fieldId']]) for binding in item.get('fieldMappings', []) if binding['fieldRef']['fieldId'] in cells}}
    return {'PROJECT_INPUTS': objects, 'PROJECT_PARAMETERS': deepcopy(parameters)}


def validate_references(document, automation, field_types):
    import re

    from autoflow.domain.project_runs.models import ProjectRunError
    inputs = {item['inputId']: item for item in automation.input_plan['inputs']}
    parameters = {item['parameterId']: item for item in automation.parameter_schema}
    pattern = re.compile(r"PROJECT_INPUTS\[['\"]([^'\"]+)['\"]\](?:\[['\"]values['\"]\]\[['\"]([^'\"]+)['\"]\])?|PROJECT_PARAMETERS\[['\"]([^'\"]+)['\"]\]")
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, child in value.items():
                if key not in {'projectInputTypes', 'label', 'note'}:
                    yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)
    for node in document.get('content', document).get('nodes', []):
        data = node.get('data', {})
        expected_types = data.get('projectInputTypes', {})
        for value in strings(data):
            expressions = re.findall(r"(?<!\$)\{([^{}]+)\}", value)
            for match in pattern.finditer(" ".join(expressions)):
                input_id, field_id, parameter_id = match.groups()
                kind = None
                if parameter_id:
                    kind = parameters.get(parameter_id, {}).get('type')
                elif input_id in inputs:
                    kind = 'object'
                    if field_id:
                        binding = next((item for item in inputs[input_id]['fieldBindings'] if item['inputFieldId'] == field_id), None)
                        kind = field_types.get(binding['fieldRef']['fieldId']) if binding else None
                reference = f"PROJECT_PARAMETERS['{parameter_id}']" if parameter_id else f"PROJECT_INPUTS['{input_id}']" + (f"['values']['{field_id}']" if field_id else '')
                if kind is None or (reference in expected_types and expected_types[reference] != kind):
                    raise ProjectRunError('PROJECT_INPUT_REFERENCE_INVALID', '节点引用的项目输入已删除或类型发生变化', 422, {'nodeId': node['id'], 'reference': match.group()})
