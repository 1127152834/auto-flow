"""Project document/dispatcher/SQLite + real recognition worker; not Electron evidence."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from time import monotonic
from uuid import uuid4

import pytest

from autoflow.application.workflows.documents import WorkflowDocumentService
from autoflow.application.workflows.runtime import WorkflowRuntimeService
from autoflow.domain.workflows.catalog import runnable_module_types
from autoflow.infrastructure.database.workflow_runtime import (
    SqlAlchemyWorkflowRuntimeRepository,
)
from autoflow.infrastructure.database.workflows import (
    SqlAlchemyWorkflowDocuments,
    SqlAlchemyWorkflowRepository,
)
from autoflow.infrastructure.process.project_workflow_worker import (
    ProjectWorkflowWorkerManager,
)
from tests.integration.test_b5_media_recognition_worker import _write_fixtures
from tests.integration.test_project_data_worker import (
    _dispatcher,
    _NoBrowserResources,
    _studio_payload,
)
from tests.integration.test_project_run_start import setup, start_payload


@pytest.mark.asyncio
@pytest.mark.parametrize('scenario', ['match', 'no_face', 'missing', 'stop', 'ocr_stop', 'ocr_timeout'])
async def test_project_recognition_uses_real_models_files_branches_and_cleanup(tmp_path: Path, scenario: str):
    assert {'image_ocr', 'face_recognition', 'ocr_captcha', 'slider_captcha'} <= runnable_module_types()
    face, text = _write_fixtures(tmp_path)
    factory, _, _, coordinator, _, project, automation = setup(tmp_path)
    source = tmp_path / 'missing.png' if scenario == 'missing' else text if scenario == 'no_face' else face
    steps = [
        ('face', 'face_recognition', {'sourceImage': str(source), 'targetImage': str(face), 'timeout': 60}),
        ('ocr', 'image_ocr', {'imagePath': str(text), 'ocrType': 'general', 'timeout': .5 if scenario == 'ocr_timeout' else 60}),
        ('matched', 'print_log', {'logMessage': '识别文本:{ocr_text}'}),
        ('empty', 'print_log', {'logMessage': '没有检测到人脸'}),
    ]
    document = _studio_payload(automation.workflow_id)
    document.update(schemaVersion=3,
        nodes=[{'id': node, 'type': kind, 'position': {'x': i * 160, 'y': 0}, 'data': {'moduleType': kind, 'config': config}}
               for i, (node, kind, config) in enumerate(steps)],
        edges=[{'id': 'yes', 'source': 'face', 'sourceHandle': 'true', 'target': 'ocr'},
               {'id': 'no', 'source': 'face', 'sourceHandle': 'false', 'target': 'empty'},
               {'id': 'next', 'source': 'ocr', 'target': 'matched'}], variables=[])
    WorkflowDocumentService(SqlAlchemyWorkflowDocuments(factory)).update(
        automation.workflow_id, document, expected_revision=1, client_request_id=str(uuid4()))
    runtime = WorkflowRuntimeService(factory, SqlAlchemyWorkflowRepository(factory))
    coordinator._core = runtime
    frozen = os.environ.get('AUTOFLOW_TEST_PROJECT_WORKER')
    worker = ProjectWorkflowWorkerManager(tmp_path / 'recognition-worker',
        **({'command': (str(Path(frozen).resolve(strict=True)), '--project-workflow-worker')} if frozen else {}))
    resources = _NoBrowserResources()
    dispatcher = _dispatcher(factory, worker, resources)
    try:
        batch, _, _ = coordinator.start(project.project_id, automation.automation_id, str(uuid4()), start_payload(automation))
        task = coordinator.list_tasks(project.project_id, batch.batch_id)[0]
        run = runtime.query_run(run_id=task.run_id)
        assert run is not None
        running = await dispatcher.dispatch(run.run_id, expected_status_revision=run.status_revision, execution_generation=run.execution_generation)
        if scenario in {'stop', 'ocr_stop'}:
            async with asyncio.timeout(15):
                while True:
                    with factory() as session:
                        events = SqlAlchemyWorkflowRuntimeRepository(session).list_events(run.run_id, after_sequence=0, limit=100)
                    if any(e.kind == 'nodeAttempt' and e.node_id == ('ocr' if scenario == 'ocr_stop' else 'face') for e in events):
                        break
                    await asyncio.sleep(.01)
            if scenario == 'ocr_stop':
                # Let the real recognition thread enter its import/inference work.
                await asyncio.sleep(.2)
            started = monotonic()
            await dispatcher.cancel(run.run_id, expected_status_revision=running.status_revision, execution_generation=running.execution_generation)
        await asyncio.wait_for(dispatcher.wait_idle(), 100)
        with factory() as session:
            repository = SqlAlchemyWorkflowRuntimeRepository(session)
            final = repository.get_run(run_id=run.run_id)
            events = repository.list_events(run.run_id, after_sequence=0, limit=100)
        expected = {'missing': 'failed', 'stop': 'cancelled', 'ocr_stop': 'cancelled', 'ocr_timeout': 'failed'}.get(scenario, 'succeeded')
        assert final is not None and final.status == expected, (final, events)
        assert not resources.requests and not worker.busy()
        outputs = {e.payload['name']: e.payload['value'] for e in events if e.kind == 'output'}
        succeeded = [e.node_id for e in events if e.kind == 'nodeAttempt' and e.payload.get('status') == 'succeeded']
        if scenario == 'match':
            assert outputs['face_match_result']['matched'] is True
            assert isinstance(outputs['ocr_text'], str)
            assert 'AUTOFLOW' in outputs['ocr_text'] and '123' in outputs['ocr_text']
            assert succeeded == ['face', 'ocr', 'matched']
            assert any(e.kind == 'log' and e.payload.get('message') == f"识别文本:{outputs['ocr_text']}" for e in events)
        elif scenario == 'no_face':
            assert outputs['face_match_result']['matched'] is False
            assert outputs['face_match_result']['source_faces'] == 0
            assert succeeded == ['face', 'empty'] and 'ocr_text' not in outputs
        else:
            forbidden = {'matched', 'empty'} if scenario in {'ocr_stop', 'ocr_timeout'} else {'ocr', 'matched', 'empty'}
            assert not any(e.node_id in forbidden for e in events)
            if scenario == 'ocr_timeout':
                failure = next(e for e in events if e.kind == 'nodeAttempt' and e.node_id == 'ocr' and e.payload.get('status') == 'failed')
                assert failure.payload['error']['code'] == 'WORKFLOW_NODE_TIMEOUT'
            if scenario in {'stop', 'ocr_stop'}:
                assert monotonic() - started < 3
    finally:
        await dispatcher.shutdown()
        factory.dispose()
