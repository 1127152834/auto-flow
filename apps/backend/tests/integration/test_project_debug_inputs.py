from copy import deepcopy

import pytest
from sqlalchemy import select

from autoflow.application.project_runs.debug_inputs import (
    debug_inputs,
    validate_debug_selection,
)
from autoflow.application.project_runs.scheduler import ProjectBatchScheduler
from autoflow.domain.project_runs.models import ProjectRunError
from autoflow.infrastructure.database.project_data_models import DataRecordRow
from autoflow.infrastructure.database.project_run_models import ProjectRecordLeaseRow
from tests.integration.test_project_run_data_start import _setup, uid


def test_debug_selection_is_exact_and_rechecked_at_claim(tmp_path):
    factory, project, automation, coordinator = _setup(tmp_path)
    plan = automation.input_plan
    with factory.begin() as session:
        source = session.scalar(select(DataRecordRow).where(DataRecordRow.table_id == plan['inputs'][0]['tableId']))
        for key in ['second', 'third']:
            data = {c.name: deepcopy(getattr(source, c.name)) for c in DataRecordRow.__table__.columns}
            data.update(key_type='text', key_value=key)
            session.add(DataRecordRow(**data))
    with factory() as session:
        first = debug_inputs(session, project, plan, {})
        input_id = plan['inputs'][0]['inputId']
        page = debug_inputs(session, project, plan, {}, input_id=input_id, page_size=1)
        assert len(page['items']) == 1
        assert page['nextCursor'] is not None
        selection = first['selection']
        third = debug_inputs(session, project, plan, {}, input_id=input_id, search='third')
        assert len(third['items']) == 1
        selection[input_id] = third['items'][0]['selection']
        validate_debug_selection(session, project, plan, selection)
    batch, _, _ = coordinator.start(project, automation.automation_id, uid(), {
        'expectedAutomationRevision': automation.management_revision, 'parameters': {},
        'maxTasks': 1, 'concurrency': 1, 'debugSelection': selection,
    })
    with factory.begin() as session:
        row = session.scalar(select(DataRecordRow).where(DataRecordRow.key_value == 'third'))
        row.content_revision += 1
    assert ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id) == 'configurationError'
    assert coordinator.list_tasks(project, batch.batch_id) == []
    with factory() as session, pytest.raises(ProjectRunError, match='变化'):
        validate_debug_selection(session, project, plan, selection)


@pytest.mark.asyncio
@pytest.mark.parametrize("later_failure", [False, True])
async def test_selected_third_record_real_worker_writes_then_normal_run_selects_next(tmp_path, later_failure):
    from pathlib import Path

    from autoflow.application.project_data.catalog import DataCatalogService
    from autoflow.application.project_runs.worker_capabilities import (
        ProjectWorkerCapabilities,
    )
    from autoflow.application.settings.runtime import QuiesceGate
    from autoflow.application.workflows.service import WorkflowService
    from autoflow.infrastructure.database.project_automation_models import (
        ProjectAutomationRow,
    )
    from autoflow.infrastructure.database.project_data_catalog import (
        SqlAlchemyProjectDataCatalog,
    )
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
    from autoflow.infrastructure.process.project_workflow_worker import (
        ProjectWorkflowWorkerManager,
    )
    from tests.fixtures.workflows import workflow_payload
    from tests.integration.test_project_data_worker import (
        _dispatcher,
        _NoBrowserResources,
    )
    factory, project, automation, coordinator = _setup(tmp_path)
    source = automation.input_plan['inputs'][0]
    iid = source['inputId']; fid = source['fieldBindings'][0]['fieldRef']['fieldId']
    mapped = source['fieldBindings'][0]['inputFieldId']
    catalog = DataCatalogService(SqlAlchemyProjectDataCatalog(factory))
    unregistered = catalog.create_status(project, source['tableId'], uid(), {'name': '未注册', 'color': '#123456', 'order': 0, 'expectedTableRevision': 2})[0]['status']['statusId']
    registered = catalog.create_status(project, source['tableId'], uid(), {'name': '已注册', 'color': '#123456', 'order': 1, 'expectedTableRevision': 3})[0]['status']['statusId']
    with factory.begin() as session:
        row = session.scalar(select(DataRecordRow).where(DataRecordRow.table_id == source['tableId']))
        row.status_id = unregistered
        for key in ['second', 'third']:
            values = {column.name: deepcopy(getattr(row, column.name)) for column in DataRecordRow.__table__.columns}
            values.update(key_type='text', key_value=key)
            session.add(DataRecordRow(**values))
        owned = session.get(ProjectAutomationRow, automation.automation_id)
        plan = deepcopy(owned.input_plan)
        plan['inputs'][0]['filter'] = {'type': 'status', 'operator': 'eq', 'statusId': unregistered}
        owned.input_plan = plan
    root = f"PROJECT_INPUTS['{iid}']"
    grant = {'tableId': source['tableId'], 'datasetGeneration': source['datasetGeneration'], 'fieldIds': [fid], 'readPurposes': ['condition', 'derivedWrite']}
    steps = [
        ('copy', 'set_variable', {'variableName': 'original', 'variableValue': '{' + root + "['values']['" + mapped + "']}"}),
        ('write', 'project_data', {'operation': 'updateRecord', 'arguments': {'recordRef': '{' + root + "['recordRef']}", 'expectedContentRevision': '{' + root + "['contentRevision']}", 'changes': {fid: 'changed'}}, 'variableName': 'written', 'tableGrant': {**grant, 'operations': ['updateRecord']}}),
        ('status', 'project_data', {'operation': 'setRecordStatus', 'arguments': {'recordRef': '{' + root + "['recordRef']}", 'expectedStatusRevision': '{' + root + "['statusRevision']}", 'statusId': registered}, 'variableName': 'status', 'tableGrant': {**grant, 'operations': ['setRecordStatus']}}),
    ]
    if later_failure:
        steps.append(('fail', 'assert_checkpoint', {'actualValue': 'no', 'expectedValue': 'yes', 'variableName': 'checked'}))
    document = workflow_payload(automation.workflow_id)
    document['content']['nodes'] = [{'id': name, 'type': kind, 'position': {'x': 0, 'y': index * 100}, 'data': {'moduleType': kind, 'label': name, **config}} for index, (name, kind, config) in enumerate(steps)]
    document['content']['edges'] = [{'id': f'e{i}', 'source': steps[i][0], 'target': steps[i+1][0]} for i in range(len(steps)-1)]
    WorkflowService(SqlAlchemyWorkflowRepository(factory)).save(automation.workflow_id, document, 1, uid())
    with factory() as session:
        initial = debug_inputs(session, project, plan, {})
        candidate = debug_inputs(session, project, plan, {}, input_id=iid, search='third')['items'][0]
        choices = {**initial['selection'], iid: candidate['selection']}
    batch, _, _ = coordinator.start(project, automation.automation_id, uid(), {'expectedAutomationRevision': 1, 'parameters': {}, 'maxTasks': 1, 'concurrency': 1, 'debugSelection': choices})
    assert ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id) == 'ready'
    task = coordinator.list_tasks(project, batch.batch_id)[0]
    capabilities = ProjectWorkerCapabilities(factory)
    worker = ProjectWorkflowWorkerManager(tmp_path / 'worker', on_capability=capabilities.handle, worker_env={'PYTHONPATH': str(Path(__file__).resolve().parents[2] / 'src')})
    dispatcher = _dispatcher(factory, worker, _NoBrowserResources())
    try:
        run = dispatcher.query_run(task.run_id)
        await dispatcher.dispatch(task.run_id, expected_status_revision=run.status_revision, execution_generation=run.execution_generation)
        await dispatcher.wait_idle()
        finished = dispatcher.query_run(task.run_id)
        assert finished.status == ('failed' if later_failure else 'succeeded'), finished.error
        await ProjectBatchScheduler(factory, dispatcher, QuiesceGate()).tick()
        with factory() as session:
            leases = session.scalars(select(ProjectRecordLeaseRow).where(ProjectRecordLeaseRow.task_id == task.task_id)).all()
            assert leases and all(lease.state == 'released' and lease.released_at is not None for lease in leases)
        snapshot = coordinator.get_snapshot(project, task.task_id)
        assert snapshot.inputs[0]['recordRef']['recordKey']['value'] == 'third'
        assert snapshot.inputs[0]['statusId'] == unregistered
        assert snapshot.inputs[0]['values'][0]['value'] == '张三'
        with factory() as session:
            row = session.scalar(select(DataRecordRow).where(DataRecordRow.key_value == 'third'))
            assert row.status_id == registered
            assert row.values_json[fid] == 'changed'
            following = debug_inputs(session, project, plan, {})
            assert following['selection'][iid]['recordRef']['recordKey']['value'] != 'third'
        assert len(coordinator.list_tasks(project, batch.batch_id)) == 1
        normal, _, _ = coordinator.start(project, automation.automation_id, uid(), {'expectedAutomationRevision': 1, 'parameters': {}, 'maxTasks': 1, 'concurrency': 1})
        assert ProjectBatchScheduler.claim_data_task(factory, project, normal.batch_id) == 'ready'
        next_task = coordinator.list_tasks(project, normal.batch_id)[0]
        assert coordinator.get_snapshot(project, next_task.task_id).inputs[0]['recordRef']['recordKey']['value'] != 'third'
        assert coordinator.get_snapshot(project, task.task_id) == snapshot
    finally:
        await dispatcher.shutdown()
        factory.dispose()


def test_optional_empty_fixed_record_and_busy_choices_are_not_silently_replaced(tmp_path):
    factory, project, automation, coordinator = _setup(tmp_path)
    plan = deepcopy(automation.input_plan)
    with factory() as session:
        initial = debug_inputs(session, project, plan, {})
        first_id, second_id = [item['inputId'] for item in plan['inputs']]
        plan['inputs'][1].update(required=False, mode='fixedRecord', fixedRecord=initial['selection'][second_id]['recordRef'])
        optional = {**initial['selection'], second_id: None}
        preview = debug_inputs(session, project, plan, optional)
        assert preview['selection'][second_id] is None
        assert len(validate_debug_selection(session, project, plan, optional).inputs) == 1
        foreign = deepcopy(initial['selection'])
        foreign[first_id]['recordRef']['projectId'] = uid()
        with pytest.raises(ProjectRunError):
            validate_debug_selection(session, project, automation.input_plan, foreign)
    batch, _, _ = coordinator.start(project, automation.automation_id, uid(), {'expectedAutomationRevision': 1, 'parameters': {}, 'maxTasks': 1, 'concurrency': 1, 'debugSelection': initial['selection']})
    assert ProjectBatchScheduler.claim_data_task(factory, project, batch.batch_id) == 'ready'
    with factory() as session:
        busy = debug_inputs(session, project, automation.input_plan, {}, input_id=first_id)
        assert busy['selectionStatus'] == 'temporarilyBusy'
        assert busy['items'] and not busy['items'][0]['selectable']
        optional_plan = {'inputs': [{**automation.input_plan['inputs'][1], 'required': False}]}
        optional_busy = debug_inputs(session, project, optional_plan, {}, input_id=second_id)
        assert optional_busy['items'] and not optional_busy['items'][0]['selectable']
        assert '占用' in optional_busy['items'][0]['reason']
        with pytest.raises(ProjectRunError, match='占用'):
            validate_debug_selection(session, project, automation.input_plan, initial['selection'])


def test_related_candidates_follow_selected_parent_and_search_cannot_bypass_filter(tmp_path):
    factory, project, automation, _ = _setup(tmp_path)
    plan = deepcopy(automation.input_plan)
    parent, child = plan['inputs']
    parent_field = parent['fieldBindings'][0]['fieldRef']['fieldId']
    child_field = child['fieldBindings'][0]['fieldRef']['fieldId']
    child.update(mode='related', relation={'type': 'fieldEquals', 'sourceInputId': parent['inputId'], 'sourceFieldRef': parent['fieldBindings'][0]['fieldRef'], 'targetFieldRef': child['fieldBindings'][0]['fieldRef']})
    with factory.begin() as session:
        for definition, field in [(parent, parent_field), (child, child_field)]:
            row = session.scalar(select(DataRecordRow).where(DataRecordRow.table_id == definition['tableId']))
            row.values_json = {field: 'first'}
            for key, value in [('second', 'second'), ('excluded', 'excluded')]:
                data = {c.name: deepcopy(getattr(row, c.name)) for c in DataRecordRow.__table__.columns}
                data.update(key_type='text', key_value=key, values_json={field: value})
                session.add(DataRecordRow(**data))
        parent['filter'] = {'type': 'compare', 'fieldId': parent_field, 'operator': 'neq', 'value': 'excluded'}
    with factory() as session:
        first_parent = debug_inputs(session, project, plan, {}, input_id=parent['inputId'], search='first')['items'][0]['selection']
        initial = debug_inputs(session, project, plan, {parent['inputId']: first_parent})
        parent_choice = debug_inputs(session, project, plan, {}, input_id=parent['inputId'], search='second')['items'][0]['selection']
        changed = debug_inputs(session, project, plan, {parent['inputId']: parent_choice})
        assert changed['selection'][child['inputId']]['recordRef']['recordKey']['value'] == 'second'
        assert debug_inputs(session, project, plan, {}, input_id=parent['inputId'], search='excluded')['items'] == []
        with pytest.raises(ProjectRunError):
            validate_debug_selection(session, project, plan, {**initial['selection'], parent['inputId']: parent_choice})
        # Following the server cursor really reaches the third matching row without changing the filter.
        page = debug_inputs(session, project, automation.input_plan, {}, input_id=parent['inputId'], page_size=1)
        second = debug_inputs(session, project, automation.input_plan, {}, input_id=parent['inputId'], page_size=1, cursor=page['nextCursor'])
        third = debug_inputs(session, project, automation.input_plan, {}, input_id=parent['inputId'], page_size=1, cursor=second['nextCursor'])
        assert len({str(item['items'][0]['selection']['recordRef']) for item in (page, second, third)}) == 3
