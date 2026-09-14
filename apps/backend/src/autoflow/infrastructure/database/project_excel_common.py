from datetime import UTC, datetime

from .models import ProjectOperationRow


def instant(value: datetime) -> str:
    return (value.replace(tzinfo=UTC) if value.tzinfo is None else value).isoformat()


def operation_view(row: ProjectOperationRow) -> dict:
    return {
        "operationId": row.id,
        "projectId": row.project_id,
        "idempotencyKey": row.idempotency_key,
        "kind": row.kind,
        "status": row.status,
        "statusRevision": row.status_revision,
        "resource": row.resource,
        "result": row.result,
        "error": row.error,
        "createdAt": instant(row.created_at),
        "updatedAt": instant(row.updated_at),
        "completedAt": instant(row.completed_at) if row.completed_at else None,
    }
