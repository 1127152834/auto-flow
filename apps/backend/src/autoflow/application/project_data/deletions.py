from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from autoflow.application.project_data.catalog import _catalog_operation, _revision
from autoflow.application.project_data.records import _ids, _key_type, _record_operation
from autoflow.application.project_data.tables import _canonical_uuid, _validation
from autoflow.domain.project_data.deletions import ProjectDataDeletions, WriteResult
from autoflow.domain.project_data.identity import decode_record_key


class DataDeletionService:
    def __init__(self, repository: ProjectDataDeletions):
        self.repository = repository

    def preview_status(
        self, project_id: str, table_id: str, status_id: str
    ) -> dict[str, Any]:
        _ids(project_id, table_id)
        status_id = _canonical_uuid(status_id, "statusId")
        return self.repository.preview_status(project_id, table_id, status_id)

    def preview_record(
        self,
        project_id: str,
        table_id: str,
        dataset_generation: str,
        encoded_record_key: str,
        record_key_type: str,
    ) -> dict[str, Any]:
        _ids(project_id, table_id)
        generation = _canonical_uuid(dataset_generation, "datasetGeneration")
        key = decode_record_key(encoded_record_key, _key_type(record_key_type))
        return self.repository.preview_record(project_id, table_id, generation, key)

    def delete_status(
        self,
        project_id: str,
        table_id: str,
        status_id: str,
        key: str,
        payload: dict[str, Any],
    ) -> WriteResult:
        _ids(project_id, table_id)
        status_id = _canonical_uuid(status_id, "statusId")
        idem = _canonical_uuid(key, "Idempotency-Key")
        required = {
            "expectedStatusRevision",
            "expectedTableRevision",
            "impactRevision",
        }
        if not isinstance(payload, dict) or set(payload) != required:
            raise _validation("form", "Invalid status deletion request")
        status_revision = _revision(
            payload["expectedStatusRevision"], "expectedStatusRevision"
        )
        table_revision = _revision(
            payload["expectedTableRevision"], "expectedTableRevision"
        )
        impact_revision = _revision(payload["impactRevision"], "impactRevision")
        request = {
            "action": "delete",
            "target": {
                "projectId": project_id,
                "tableId": table_id,
                "statusId": status_id,
            },
            **payload,
        }
        operation = _catalog_operation(
            idem,
            "mutateStatus",
            request,
            project_id,
            table_id,
            "status",
            status_id,
            datetime.now(UTC),
        )
        return self.repository.delete_status(
            project_id,
            table_id,
            status_id,
            status_revision,
            table_revision,
            impact_revision,
            operation,
        )

    def delete_record(
        self,
        project_id: str,
        table_id: str,
        encoded_record_key: str,
        key: str,
        payload: dict[str, Any],
    ) -> WriteResult:
        _ids(project_id, table_id)
        idem = _canonical_uuid(key, "Idempotency-Key")
        required = {
            "datasetGeneration",
            "recordKeyType",
            "expectedContentRevision",
            "expectedStatusRevision",
            "expectedLinkRevision",
            "impactRevision",
        }
        if not isinstance(payload, dict) or set(payload) != required:
            raise _validation("form", "Invalid record deletion request")
        generation = _canonical_uuid(payload["datasetGeneration"], "datasetGeneration")
        record_key = decode_record_key(
            encoded_record_key, _key_type(payload["recordKeyType"])
        )
        values = {
            name: _revision(payload[name], name)
            for name in required
            if name.startswith("expected") or name == "impactRevision"
        }
        request = {
            "action": "delete",
            "datasetGeneration": generation,
            "recordKeyType": record_key.type,
            "recordKey": record_key.value,
            **values,
        }
        operation = _record_operation(
            idem, "deleteRecord", project_id, table_id, request, record_key
        )
        return self.repository.delete_record(
            project_id,
            table_id,
            generation,
            record_key,
            values["expectedContentRevision"],
            values["expectedStatusRevision"],
            values["expectedLinkRevision"],
            values["impactRevision"],
            operation,
        )
