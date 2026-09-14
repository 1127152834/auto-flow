from uuid import uuid4

from fastapi.testclient import TestClient

from autoflow.application.workflows.service import WorkflowService
from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.infrastructure.database.session import create_session_factory
from autoflow.infrastructure.database.workflows import SqlAlchemyWorkflowRepository
from autoflow.infrastructure.filesystem.paths import AppPaths
from tests.fixtures.workflows import workflow_payload


def test_real_application_configuration_and_operation_recovery(tmp_path):
    settings = Settings(data_dir=str(tmp_path), instance_id='automation-integration', instance_token='test-token')
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get('/api/v1/projects').status_code == 401
        assert client.get('/api/v1/workflows').status_code == 401
        client.headers['x-autoflow-token'] = 'test-token'
        project = client.post('/api/v1/projects', headers={'Idempotency-Key': str(uuid4())}, json={'name': '自动化管理验收', 'description': ''}).json()
        project_id = project['projectId']
        paths = AppPaths.from_data_dir(tmp_path)
        factory = create_session_factory(paths.database)
        try:
            workflow = WorkflowService(SqlAlchemyWorkflowRepository(factory)).create(workflow_payload(), str(uuid4()))
        finally:
            factory.dispose()
        catalog = client.get('/api/v1/workflows')
        assert catalog.status_code == 200
        assert catalog.json()['items'][0]['workflowId'] == workflow.workflow_id
        assert client.get(f'/api/v1/workflows/{workflow.workflow_id}').json()['revision'] == workflow.revision
        missing = client.get(f'/api/v1/workflows/{uuid4()}')
        assert missing.status_code == 404 and missing.json()['error']['code'] == 'WORKFLOW_NOT_FOUND'
        body = {
            'name': '资料整理', 'description': '配置真实保存', 'workflowId': workflow.workflow_id,
            'inputPlan': {'inputs': []}, 'parameterSchema': [{'parameterId': str(uuid4()), 'name': '关键词', 'type': 'string', 'required': False}],
            'environmentPolicy': {'source': 'newFromProfile'},
            'runPolicy': {'maxTasks': 1, 'concurrency': 1, 'maxLiveInstances': 1, 'continueAfterFailure': False, 'automaticExecutionTimeoutSeconds': 60, 'manualDeadlineSeconds': 300},
        }
        path = f'/api/v1/projects/{project_id}/automations'
        key = str(uuid4())
        created = client.post(path, json=body, headers={'Idempotency-Key': key})
        assert created.status_code == 201, created.text
        automation = created.json()
        assert client.get(path).json()['items'][0]['automationId'] == automation['automationId']
        recovered = client.get(f'/api/v1/projects/{project_id}/operations/by-idempotency-key/{key}')
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()['resource'] == {'type': 'automation', 'projectId': project_id, 'automationId': automation['automationId']}
        assert recovered.json()['result']['name'] == '资料整理'
        assert recovered.json()['result'] == automation
        assert recovered.json()['result']['parameterSchema'] == body['parameterSchema']
        assert recovered.json()['result']['environmentPolicy'] == body['environmentPolicy']
        replay = client.post(path, json=body, headers={'Idempotency-Key': key})
        assert replay.status_code == 200 and replay.json() == automation
        updated = client.put(f"{path}/{automation['automationId']}", json={**body, 'name': '整理二版', 'expectedManagementRevision': 1}, headers={'Idempotency-Key': str(uuid4())})
        assert updated.status_code == 200, updated.text
        assert updated.json()['managementRevision'] == 2
        assert client.get(f'/api/v1/projects/{project_id}/operations/by-idempotency-key/{key}').json()['result']['name'] == '资料整理'
        operations = client.get(f'/api/v1/projects/{project_id}/operations?kind=createAutomation&resourceType=automation')
        assert operations.status_code == 200, operations.text
        assert operations.json()['total'] == 1
        operation_id = recovered.json()['operationId']
        recovered_paths = [
            f'/api/v1/projects/{project_id}/operations/{operation_id}',
        ]
        for lookup in recovered_paths:
            result = client.get(lookup).json()['result']
            assert result['parameterSchema'] == body['parameterSchema']
            assert result['environmentPolicy'] == body['environmentPolicy']
        assert operations.json()['items'][0]['result']['parameterSchema'] == body['parameterSchema']
        # Workspace recovery is intentionally reserved for createProject.
        assert client.get(f'/api/v1/workspace/operations/by-idempotency-key/{key}').status_code == 404
        # No consumer is allowed to infer runnable from a saved draft.
        assert not client.get(f"{path}/{automation['automationId']}/validation").json()['runnable']
