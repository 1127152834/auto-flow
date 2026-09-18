from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DataTable:
    project_id: str
    table_id: str
    name: str
    description: str
    source_kind: str
    dataset_generation: str
    table_revision: int
    identity: dict[str, str]
    slot_definitions: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    record_count: int = 0
    source: dict[str, Any] | None = None

    def patched(self, patch: dict[str, Any], now: datetime) -> DataTable:
        name = patch.get("name", self.name)
        description = patch.get("description", self.description)
        if name == self.name and description == self.description:
            return self
        return replace(
            self,
            name=name,
            description=description,
            table_revision=self.table_revision + 1,
            updated_at=now,
        )


def table_to_dict(
    value: DataTable, sync_summary: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "projectId": value.project_id,
        "tableId": value.table_id,
        "name": value.name,
        "description": value.description,
        "sourceKind": value.source_kind,
        "source": value.source or {"kind": value.source_kind},
        "datasetGeneration": value.dataset_generation,
        "tableRevision": value.table_revision,
        "identity": value.identity,
        "slotDefinitions": value.slot_definitions,
        "recordCount": value.record_count,
        "syncSummary": sync_summary
        or {"status": "notApplicable", "pendingCount": 0, "unknownCount": 0},
        "createdAt": value.created_at.isoformat(),
        "updatedAt": value.updated_at.isoformat(),
    }
