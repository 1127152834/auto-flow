"""Read-only debug choices and exact claim validation over the normal input selector."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from sqlalchemy.orm import Session

from autoflow.domain.project_runs.input_selection import (
    MAX_CANDIDATE_EVALUATIONS,
    select_required_inputs,
)
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.domain.workflows.runtime import thaw_json
from autoflow.infrastructure.database.project_claims import (
    SqlAlchemyProjectInputGroups,
    _parse_record_ref,
)

REVISIONS = ('contentRevision', 'statusRevision', 'linkRevision')


def _error(message: str, input_id: str | None = None) -> ProjectRunError:
    return ProjectRunError('DEBUG_INPUT_INVALID', message, 409, {'inputId': input_id})


def restrictions(plan: dict[str, Any], choices: dict[str, Any], *, complete: bool = False):
    definitions = {item['inputId']: item for item in plan['inputs']}
    if not isinstance(choices, dict) or set(choices) - set(definitions) or (complete and set(choices) != set(definitions)):
        raise _error('调试选择与输入定义不一致，请重新选择')
    result: dict[str, list[Any]] = {}
    for input_id, chosen in choices.items():
        definition = definitions[input_id]
        if chosen is None:
            if definition['required']:
                raise _error('必需输入不能留空', input_id)
            result[input_id] = []
            continue
        if not isinstance(chosen, dict) or set(chosen) != {'recordRef', *REVISIONS} or any(type(chosen.get(key)) is not int or chosen[key] < 1 for key in REVISIONS):
            raise _error('记录身份或版本无效', input_id)
        try:
            ref = _parse_record_ref(chosen['recordRef'])
        except (KeyError, TypeError, ValueError) as exc:
            raise _error('记录身份无效', input_id) from exc
        if ref.table_id != definition['tableId'] or ref.dataset_generation != definition['datasetGeneration']:
            raise _error('记录不属于输入的数据表', input_id)
        result[input_id] = [ref]
    return result


def choice(value):
    data = thaw_json(value)
    return {key: data[key] for key in ('recordRef', *REVISIONS)}


def validate_debug_selection(session: Session, project_id: str, plan: dict[str, Any], choices: dict[str, Any]):
    pinned = restrictions(plan, choices, complete=True)
    selected = SqlAlchemyProjectInputGroups(session).select_required(project_id, plan, candidate_restriction=pinned)
    if selected.status != 'ready':
        reasons = {'temporarilyBusy': '所选记录已被其他任务占用', 'noMatch': '所选记录已删除、不再符合筛选条件或关联已失效', 'ambiguous': '关联记录不唯一', 'configurationError': '输入配置或来源已失效', 'scanBudgetExceeded': '候选范围超出本次检查上限'}
        raise _error(reasons.get(selected.status, '所选数据不可领取') + '，请刷新后重新选择', next(iter(selected.issue_input_ids), None))
    actual = {item.input_id: choice(item.value) for item in selected.inputs}
    for input_id, expected in choices.items():
        if actual.get(input_id) != expected:
            raise _error('所选数据已变化，请刷新后重新选择', input_id)
    return selected


def debug_inputs(session: Session, project_id: str, plan: dict[str, Any], choices: dict[str, Any], *, input_id: str | None = None, cursor: str | None = None, page_size: int = 50, search: str = '') -> dict[str, Any]:
    groups = SqlAlchemyProjectInputGroups(session)
    pinned = restrictions(plan, choices)
    selected = groups.select_required(project_id, plan, candidate_restriction=pinned) if plan['inputs'] else None
    snapshots = {item.input_id: {'inputId': item.input_id, **thaw_json(item.value)} for item in selected.inputs} if selected else {}
    result: dict[str, Any] = {
        'selectionStatus': selected.status if selected else 'ready',
        'selection': {item['inputId']: choice(snapshots[item['inputId']]) if item['inputId'] in snapshots else None for item in plan['inputs']},
        'inputs': list(snapshots.values()), 'items': [], 'nextCursor': None,
    }
    if input_id is None:
        for selected_id, expected in choices.items():
            if result['selection'].get(selected_id) != expected:
                raise _error('所选记录的版本、状态或关联已变化，请刷新后重新选择', selected_id)
        return result
    definitions = {item['inputId']: item for item in plan['inputs']}
    if input_id not in definitions:
        raise _error('输入不存在', input_id)
    try:
        scan_offset, index = map(int, (cursor or '0:0').split(':'))
        if scan_offset < 0 or scan_offset % MAX_CANDIDATE_EVALUATIONS or not 0 <= index <= MAX_CANDIDATE_EVALUATIONS or not 1 <= page_size <= 100:
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise _error('分页位置无效', input_id) from exc
    source = groups._candidates(project_id, definitions[input_id], definitions, offset=scan_offset)
    if source.configuration_error:
        raise _error('输入配置或来源已失效，请刷新配置', input_id)
    other_sources = {key: groups._candidates(project_id, item, definitions, restriction=pinned.get(key)) for key, item in definitions.items() if key != input_id}
    # Selection is bounded by the same scan budget as normal runs. A cursor
    # continues the next bounded window instead of silently truncating the list.
    for position in range(index, len(source.candidates)):
        candidate = source.candidates[position]
        value = thaw_json(candidate.value)
        if search.casefold() not in (str(candidate.record_ref.record_key.value) + ' ' + ' '.join(str(cell['value']) for cell in value['values'])).casefold():
            continue
        trial = select_required_inputs([replace(source, candidates=(candidate,), required=True, scan_budget_exceeded=False) if key == input_id else other_sources[key] for key in definitions])
        trial = groups._validate_selected_values(trial)
        trial = groups.validate_relation_uniqueness(project_id, plan, trial)
        selected_target = next((item for item in trial.inputs if item.input_id == input_id), None)
        if trial.status == 'noMatch' or (trial.status == 'ready' and (selected_target is None or selected_target.record_ref != candidate.record_ref)):
            continue
        if len(result['items']) == page_size:
            result['nextCursor'] = f'{scan_offset}:{position}'
            break
        selectable = candidate.available and trial.status == 'ready' and selected_target is not None
        result['items'].append({'inputId': input_id, **value, 'selection': choice(value), 'selectable': selectable, 'reason': None if selectable else '记录被占用或无法组成完整输入组'})
    else:
        if source.scan_budget_exceeded:
            result['nextCursor'] = f'{scan_offset + MAX_CANDIDATE_EVALUATIONS}:0'
    return result
