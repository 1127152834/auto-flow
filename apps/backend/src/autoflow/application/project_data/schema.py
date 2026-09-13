"""Application boundary for previewing and committing complete schema drafts."""

from datetime import UTC, datetime

from autoflow.application.project_data.catalog import _ids, _revision
from autoflow.application.project_data.tables import (
    _canonical_uuid,
    _operation,
    _validation,
)
from autoflow.domain.project_data.schema import validate_candidate


class DataSchemaService:
    def __init__(self, schema):
        self.schema = schema

    def preview(self, project_id: str, table_id: str, candidate: object) -> dict:
        _ids(project_id, table_id)
        return self.schema.preview(project_id, table_id, validate_candidate(candidate))

    def commit(self, project_id: str, table_id: str, key: str, payload: dict):
        _ids(project_id, table_id)
        key = _canonical_uuid(key, "Idempotency-Key")
        if not isinstance(payload, dict) or set(payload) != {
            "candidate",
            "impactRevision",
        }:
            raise _validation("form", "Must contain candidate and impactRevision")
        candidate = validate_candidate(payload["candidate"])
        impact = _revision(payload["impactRevision"], "impactRevision")
        operation = _operation(
            key,
            "saveTableSchema",
            {
                "scope": "table",
                "target": {"projectId": project_id, "tableId": table_id},
                "request": {"candidate": candidate, "impactRevision": impact},
            },
            project_id,
            table_id,
            datetime.now(UTC),
        )
        return self.schema.commit(project_id, table_id, candidate, impact, operation)
