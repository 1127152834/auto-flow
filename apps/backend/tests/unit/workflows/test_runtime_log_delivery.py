from __future__ import annotations

import ast
from pathlib import Path

import pytest

from autoflow.application.workflows.executors.logging import PrintLogExecutor
from autoflow.application.workflows.executors.registry import ExecutorRegistry
from autoflow.application.workflows.runtime import WorkflowRuntime
from autoflow.domain.workflows.execution import ExecutionContext


@pytest.mark.asyncio
async def test_real_print_executor_marks_user_log_at_each_execution():
    class Events:
        def __init__(self): self.items = []
        async def publish(self, event): self.items.append(dict(event))

    events = Events()
    registry = ExecutorRegistry()
    registry.register(PrintLogExecutor)
    result = await WorkflowRuntime(registry).execute({'nodes': [{
        'id': 'print', 'data': {'moduleType': 'print_log', 'config': {'logMessage': '可见的用户日志', 'logLevel': 'warning'}},
    }], 'edges': []}, ExecutionContext(events=events))
    assert result.success
    completed = next(item for item in events.items if item['type'] == 'execution:node_complete')
    assert completed['isUserLog'] is True
    assert completed['isSystemLog'] is False
    assert completed['logLevel'] == 'warning'
    assert completed['message'] == '可见的用户日志'


def test_log_classification_is_exact_approved_subset_of_frozen_source():
    from autoflow.application.workflows.runtime import (
        IMPORTANT_LOG_NODE_TYPES,
        SYSTEM_LOG_NODE_TYPES,
    )
    from autoflow.domain.workflows.scope import APPROVED_NODE_TYPES

    root = Path(__file__).resolve().parents[5]
    source = root / 'reference/WebRPA/backend/app/services/workflow_executor.py'
    tree = ast.parse(source.read_text())
    source_sets = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Set):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {'important_modules', 'trigger_modules'}:
                    source_sets[target.id] = ast.literal_eval(node.value)
    assert IMPORTANT_LOG_NODE_TYPES == source_sets['important_modules'] & APPROVED_NODE_TYPES
    assert SYSTEM_LOG_NODE_TYPES == source_sets['trigger_modules'] & APPROVED_NODE_TYPES


@pytest.mark.asyncio
async def test_coordinator_preserves_user_level_and_wraps_standalone_warning(tmp_path):
    from autoflow.adapters.events.workflows import StudioEventJournal, _scope_log_event
    from autoflow.application.workflows.coordinator import WorkflowRunCoordinator
    from autoflow.application.workflows.documents import WorkflowDocumentService
    from autoflow.application.workflows.runs import WorkflowRunService
    from autoflow.infrastructure.database.session import (
        create_session_factory,
        migrate_database,
    )
    from autoflow.infrastructure.database.workflow_runs import SqlAlchemyWorkflowRuns
    from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowDocuments
    from tests.unit.workflows.test_run_coordinator import (
        FakeProfiles,
        FakeResources,
        FakeWorkers,
        _none,
        _profile,
    )

    database = tmp_path / 'logs.sqlite3'
    migrate_database(database)
    sessions = create_session_factory(database)
    documents = WorkflowDocumentService(SqlAlchemyWorkflowDocuments(sessions))
    documents.create({'id': 'log-doc', 'name': '用户日志', 'nodes': [{
        'id': 'print', 'data': {'moduleType': 'print_log', 'config': {'logMessage': 'warning'}},
    }], 'edges': [], 'variables': []}, client_request_id='create')
    repository = SqlAlchemyWorkflowRuns(sessions)
    runs = WorkflowRunService(repository)
    journal = StudioEventJournal()
    registry = ExecutorRegistry()
    registry.register(PrintLogExecutor)
    coordinator = WorkflowRunCoordinator(
        documents=documents, runs=runs, run_repository=repository, runtime=WorkflowRuntime(registry),
        profiles=FakeProfiles(_profile()), installed_kernels=list, resolve_proxy=lambda _p, _r: _none(),
        read_license=lambda: None, workers=FakeWorkers(), resources=FakeResources(), events=journal,
        artifact_root=tmp_path / 'workspace',
    )
    await coordinator.start('log-doc', {'runId': 'logs', 'documentId': 'log-doc', 'profileId': 'profile-1'})
    await coordinator.on_worker_event({'type': 'execution:node_complete', 'runId': 'logs', 'nodeId': 'print',
        'executionId': 'exec', 'success': True, 'message': '用户警告', 'logLevel': 'warning', 'duration': 12,
        'isUserLog': True, 'isSystemLog': False})
    await coordinator.on_worker_event({'type': 'execution:log', 'runId': 'logs', 'level': 'warning', 'message': '未到达目标'})
    live = [event for event in journal.replay(after_sequence=0) if event.event == 'execution:log']
    assert len(live) == 2
    assert live[0].data['log']['level'] == 'warning'
    assert live[0].data['log']['isUserLog'] is True
    assert live[0].data['log']['duration'] == 12
    assert live[1].data['log']['level'] == 'warning'
    assert live[1].data['log']['message'] == '未到达目标'
    assert all(_scope_log_event(event, False) is event for event in live)
    historical, count, _ = runs.logs('logs', cursor=0, limit=20, query=None, levels=(), node_id=None)
    assert count == 2
    assert [log['message'] for log in historical] == ['用户警告', '未到达目标']
    assert [log['level'] for log in historical] == ['warning', 'warning']
