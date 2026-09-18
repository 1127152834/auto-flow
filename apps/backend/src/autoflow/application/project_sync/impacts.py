"""Read-only impact previews for the Sheets connection and binding commands.

The report never touches Google: it only re-states local facts and the intended
change so the command that follows can quote a confirmation instead of
inventing one.
"""

from __future__ import annotations

from typing import Any

from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_sync_impacts import (
    SqlAlchemySheetsImpacts,
)


class SheetsImpactService:
    def __init__(self, impacts: SqlAlchemySheetsImpacts) -> None:
        self._impacts = impacts

    def disconnect(self, project_id: str, body: dict[str, Any]) -> dict[str, Any]:
        connection_id = _uuid(body["connectionId"], "connectionId")
        mode = body["mode"]
        return self._impacts.preview_disconnect(project_id, connection_id, mode)

    def binding(
        self, project_id: str, table_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        table_id = _uuid(table_id, "tableId")
        change = {
            "connectionId": _uuid(body["connectionId"], "connectionId"),
            "spreadsheetId": body["spreadsheetId"],
            "sheetId": body["sheetId"],
            "identityStrategy": body["identityStrategy"],
            "mapping": body["mapping"],
        }
        return self._impacts.preview_binding(project_id, table_id, change)

    def unbind(self, project_id: str, table_id: str) -> dict[str, Any]:
        return self._impacts.preview_unbind(project_id, _uuid(table_id, "tableId"))


def _uuid(value: str, field: str) -> str:
    from uuid import UUID

    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise ProjectError(
            "INVALID_PROJECT_DATA",
            f"{field} 必须是 UUID",
            422,
            {"field": field, "domainCode": "sheets"},
        ) from error
