from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect, text

from autoflow.application.workflows.service import WorkflowService
from autoflow.domain.workflows.models import WorkflowError
from autoflow.domain.workflows.run_validation import prepare_run
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)
from autoflow.infrastructure.database.workflows import (
    SqlAlchemyWorkflowRepository,
)
from tests.fixtures.workflows import transient_payload, workflow_payload


def service_for(path):
    migrate_database(path)
    factory = create_session_factory(path)
    repository = SqlAlchemyWorkflowRepository(factory)
    return WorkflowService(repository), factory


def test_documents_survive_reopen_and_store_only_projected_source_payload(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    service, factory = service_for(database)
    operation_id = str(uuid4())
    saved = service.create(transient_payload(), operation_id)
    assert "workflow_documents" in inspect(factory.kw["bind"]).get_table_names()
    assert saved.revision == 1
    assert "selected" not in saved.document["content"]["nodes"][0]
    assert "isHighlighted" not in saved.document["content"]["nodes"][0]["data"]
    factory.dispose()
    reopened = create_session_factory(database)
    assert SqlAlchemyWorkflowRepository(reopened).get(saved.document["id"]) == saved
    reopened.dispose()


@pytest.mark.parametrize(
    "bad_id",
    [
        "not-a-uuid",
        "D45F286F-129D-4E3B-A09B-995C3B491609",
        "d45f286f129d4e3ba09b995c3b491609",
        "{d45f286f-129d-4e3b-a09b-995c3b491609}",
    ],
)
def test_document_and_operation_ids_must_be_canonical_uuid(tmp_path, bad_id):
    service, factory = service_for(tmp_path / f"{uuid4()}.sqlite3")
    payload = workflow_payload(bad_id)
    with pytest.raises(WorkflowError) as caught:
        service.create(payload, str(uuid4()))
    assert caught.value.code == "VALIDATION_ERROR"
    payload = workflow_payload()
    with pytest.raises(WorkflowError) as caught:
        service.create(payload, bad_id)
    assert caught.value.code == "VALIDATION_ERROR"
    factory.dispose()


def test_exact_revision_same_content_is_noop_but_stale_and_future_always_conflict(tmp_path):
    service, factory = service_for(tmp_path / "autoflow.sqlite3")
    payload = workflow_payload()
    created = service.create(payload, str(uuid4()))
    unchanged = service.save(
        payload["id"], payload, expected_revision=1, save_operation_id=str(uuid4())
    )
    assert unchanged == created
    for revision in (0, 2):
        with pytest.raises(WorkflowError) as caught:
            service.save(
                payload["id"],
                payload,
                expected_revision=revision,
                save_operation_id=str(uuid4()),
            )
        assert caught.value.code == "WORKFLOW_REVISION_CONFLICT"
        assert caught.value.details["currentRevision"] == 1
    factory.dispose()


def test_save_operation_replays_same_request_rejects_other_payload_and_is_queryable(tmp_path):
    service, factory = service_for(tmp_path / "autoflow.sqlite3")
    payload = workflow_payload()
    service.create(payload, str(uuid4()))
    changed = deepcopy(payload)
    changed["content"]["name"] = "已修改"
    key = str(uuid4())
    saved = service.save(payload["id"], changed, 1, key)
    replay = service.save(payload["id"], changed, 1, key)
    assert replay == saved
    operation = service.query_save(key)
    assert operation.save_operation_id == key
    assert operation.workflow_id == payload["id"]
    assert operation.record == saved
    assert len(operation.request_digest) == 64
    with pytest.raises(WorkflowError) as caught:
        service.save(payload["id"], payload, 1, key)
    assert caught.value.code == "OPERATION_PAYLOAD_MISMATCH"
    factory.dispose()


def test_save_operation_result_and_digest_survive_reopen(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    service, factory = service_for(database)
    payload = workflow_payload()
    created = service.create(payload, str(uuid4()))
    changed = deepcopy(payload)
    changed["content"]["name"] = "第二版"
    key = str(uuid4())
    second = service.save(payload["id"], changed, created.revision, key)
    third_payload = deepcopy(changed)
    third_payload["content"]["name"] = "第三版"
    service.save(payload["id"], third_payload, second.revision, str(uuid4()))
    factory.dispose()

    reopened = create_session_factory(database)
    recovered = WorkflowService(SqlAlchemyWorkflowRepository(reopened))
    operation = recovered.query_save(key)
    assert operation.record == second
    assert operation.record.document["content"]["name"] == "第二版"
    assert recovered.save(payload["id"], changed, created.revision, key) == second
    reopened.dispose()


def test_save_operation_digest_uses_persisted_projection(tmp_path):
    service, factory = service_for(tmp_path / "autoflow.sqlite3")
    payload = workflow_payload()
    service.create(payload, str(uuid4()))
    changed = deepcopy(payload)
    changed["content"]["name"] = "已修改"
    key = str(uuid4())
    saved = service.save(payload["id"], changed, 1, key)
    equivalent = deepcopy(changed)
    equivalent["content"]["updatedAt"] = "2099-01-01T00:00:00.000Z"
    equivalent["content"]["nodes"][0]["selected"] = True
    equivalent["content"]["nodes"][0]["measured"] = {"width": 1, "height": 1}
    assert service.save(payload["id"], equivalent, 1, key) == saved
    factory.dispose()


def test_save_operation_query_validates_key_and_reports_unknown(tmp_path):
    service, factory = service_for(tmp_path / "autoflow.sqlite3")
    unknown = str(uuid4())
    assert str(UUID(unknown)) == unknown
    with pytest.raises(WorkflowError) as caught:
        service.query_save(unknown)
    assert caught.value.code == "WORKFLOW_SAVE_OPERATION_NOT_FOUND"
    with pytest.raises(WorkflowError) as caught:
        service.query_save("NOT-A-UUID")
    assert caught.value.code == "VALIDATION_ERROR"
    factory.dispose()


def test_current_list_skips_legacy_and_legacy_document_remains_read_only(tmp_path):
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    service = WorkflowService(SqlAlchemyWorkflowRepository(factory))
    current = service.create(workflow_payload(), str(uuid4()))
    legacy_id = "legacy-workflow"
    with factory.begin() as session:
        session.execute(
            text(
                "INSERT INTO workflow_documents VALUES "
                "(:id,:name,:document,:layout,7,:created,:updated)"
            ),
            {
                "id": legacy_id,
                "name": "旧格式",
                "document": '{"schemaVersion":2,"nodes":[]}',
                "layout": "{}",
                "created": "2026-09-13",
                "updated": "2026-09-13",
            },
        )
    repository = SqlAlchemyWorkflowRepository(factory)
    with pytest.raises(WorkflowError) as caught:
        repository.get(legacy_id)
    assert caught.value.code == "WORKFLOW_LEGACY_DOCUMENT_UNSUPPORTED"
    assert service.list() == [current]
    legacy = service.list_legacy()
    assert [record.workflow_id for record in legacy] == [legacy_id]
    assert legacy[0].document == {"schemaVersion": 2, "nodes": []}
    assert legacy[0].layout == {}
    assert service.export_legacy(legacy_id) == legacy[0]
    legacy[0].document["nodes"].append({"id": "caller-only"})
    assert service.export_legacy(legacy_id).document["nodes"] == []
    with pytest.raises(WorkflowError) as caught:
        prepare_run(legacy[0].document)
    assert caught.value.code == "WORKFLOW_INVALID"
    factory.dispose()


@pytest.mark.parametrize("workflow_id", ["", None])
def test_legacy_export_rejects_only_empty_or_non_string_ids(tmp_path, workflow_id):
    service, factory = service_for(tmp_path / f"{uuid4()}.sqlite3")
    with pytest.raises(WorkflowError) as caught:
        service.export_legacy(workflow_id)
    assert caught.value.code == "VALIDATION_ERROR"
    factory.dispose()


@pytest.mark.parametrize("document", [[], "workflow", None])
def test_service_rejects_non_object_documents_with_domain_error(tmp_path, document):
    service, factory = service_for(tmp_path / f"{uuid4()}.sqlite3")
    with pytest.raises(WorkflowError) as caught:
        service.create(document, str(uuid4()))
    assert caught.value.code == "WORKFLOW_INVALID"
    with pytest.raises(WorkflowError) as caught:
        service.save(str(uuid4()), document, 0, str(uuid4()))
    assert caught.value.code == "WORKFLOW_INVALID"
    factory.dispose()
