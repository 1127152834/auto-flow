"""Stable project input references; original snapshots never become mutable globals."""
from collections.abc import Iterator, Mapping
from copy import deepcopy
from typing import Any

from autoflow.domain.project_automations.models import AutomationRecord


def input_context(
    inputs: list[dict[str, Any]], parameters: dict[str, Any], processing_input_id: str | None = None,
) -> dict[str, Any]:
    objects: dict[str, Any] = {}
    # Remediation M2 R2-19/20: signature-bound inputs are also reachable as input.<key>.<field>.
    groups: dict[str, Any] = {}
    record: dict[str, Any] | None = None
    record_group: str | None = None
    for item in inputs:
        group = item.get('signatureInput')
        if item.get('recordRef') is None:
            objects[item['inputId']] = None
            if isinstance(group, str):
                groups[group] = None
            continue
        cells = {cell['fieldId']: cell['value'] for cell in item.get('values', [])}
        objects[item['inputId']] = {**deepcopy(item), 'values': {binding['inputFieldId']: deepcopy(cells[binding['fieldRef']['fieldId']]) for binding in item.get('fieldMappings', []) if binding['fieldRef']['fieldId'] in cells}}
        if isinstance(group, str):
            groups[group] = {
                binding['signatureField']: deepcopy(cells[binding['fieldRef']['fieldId']])
                for binding in item.get('fieldMappings', [])
                if isinstance(binding.get('signatureField'), str) and binding['fieldRef']['fieldId'] in cells
            }
            if item['inputId'] == processing_input_id:
                record, record_group = groups[group], group
    context: dict[str, Any] = {'PROJECT_INPUTS': objects, 'PROJECT_PARAMETERS': deepcopy(parameters)}
    if groups:
        context['input'] = groups
    if record is not None:
        context['$record'] = deepcopy(record)
        context['$recordInput'] = record_group
    return context


def validate_references(
    document: dict[str, Any],
    automation: AutomationRecord,
    field_types: Mapping[str, str],
) -> None:
    import re

    from autoflow.domain.project_runs.models import ProjectRunError
    inputs = {item['inputId']: item for item in automation.input_plan['inputs']}
    parameters = {item['parameterId']: item for item in automation.parameter_schema}
    pattern = re.compile(r"PROJECT_INPUTS\[['\"]([^'\"]+)['\"]\](?:\[['\"]values['\"]\]\[['\"]([^'\"]+)['\"]\])?|PROJECT_PARAMETERS\[['\"]([^'\"]+)['\"]\]")
    def strings(value: Any) -> Iterator[str]:
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, child in value.items():
                if key not in {'projectInputTypes', 'label', 'note'}:
                    yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)
    validate_signature_bindings(document, automation, field_types)
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


def validate_signature_bindings(
    document: dict[str, Any], automation: AutomationRecord, field_types: Mapping[str, str],
) -> None:
    """Remediation M2 R2-18/20: a signature workflow starts only with complete, type-compatible bindings."""
    from autoflow.domain.project_runs.models import ProjectRunError
    from autoflow.domain.workflows.signature import (
        document_signature,
        parse_signature,
        reference_issues,
    )

    signature, issues = parse_signature(document_signature(document))
    if issues:
        raise ProjectRunError('PROJECT_SIGNATURE_INVALID', f'工作流的流程输入设置有误：{issues[0].message}', 422, {'path': issues[0].path})
    if signature is None:
        return
    for node_id, message in reference_issues(document, signature):
        raise ProjectRunError('PROJECT_INPUT_REFERENCE_INVALID', message, 422, {'nodeId': node_id})
    inputs = automation.input_plan['inputs']
    for group in signature.inputs:
        bound = next((item for item in inputs if item.get('signatureInput') == group.key), None)
        if bound is None:
            raise ProjectRunError('PROJECT_SIGNATURE_UNBOUND', f'流程输入「{group.name}」还没有绑定数据', 422, {'signatureInput': group.key})
        bindings = {item['signatureField']: item for item in bound['fieldBindings'] if isinstance(item.get('signatureField'), str)}
        for field in group.fields:
            binding = bindings.get(field.key)
            if binding is None:
                if field.required:
                    raise ProjectRunError('PROJECT_SIGNATURE_UNBOUND', f'流程输入「{group.name}」缺少字段「{field.name}」的绑定', 422,
                                          {'signatureInput': group.key, 'signatureField': field.key, 'inputId': bound['inputId']})
                continue
            actual = field_types.get(binding['fieldRef']['fieldId'])
            if field.type != 'any' and actual != field.type:
                raise ProjectRunError('PROJECT_SIGNATURE_TYPE_MISMATCH', f'流程输入「{group.name}」的字段「{field.name}」需要{_TYPE_NAMES.get(field.type, field.type)}，绑定的数据字段是{_TYPE_NAMES.get(actual or "", "未知类型")}', 422,
                                  {'signatureInput': group.key, 'signatureField': field.key, 'inputId': bound['inputId']})
        unknown = set(bindings) - {field.key for field in group.fields}
        if unknown:
            raise ProjectRunError('PROJECT_SIGNATURE_UNBOUND', f'流程输入「{group.name}」没有字段「{min(unknown)}」', 422,
                                  {'signatureInput': group.key, 'inputId': bound['inputId']})
    declared = {group.key for group in signature.inputs}
    for item in inputs:
        if isinstance(item.get('signatureInput'), str) and item['signatureInput'] not in declared:
            raise ProjectRunError('PROJECT_SIGNATURE_UNBOUND', f'工作流没有名为「{item["signatureInput"]}」的流程输入', 422, {'inputId': item['inputId']})


_TYPE_NAMES = {'string': '文本', 'number': '数字', 'boolean': '是/否', 'date': '日期'}
