"""Freeze and verify one explicit source identity initialization; never infer a resend."""
from typing import Any
from uuid import UUID, uuid4

from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_sync import digest

IDENTITY_HEADER = "_autoflow_id"
IDENTITY_METADATA = "autoflow.systemIdentity"


def _rows(values: list[list[Any]]) -> list[list[Any]]:
    # Sheets omits trailing empty cells and rows from value reads.
    rows = []
    for source in values:
        row = list(source)
        while row and row[-1] in (None, ""):
            row.pop()
        rows.append(row)
    while rows and not rows[-1]:
        rows.pop()
    return rows


def identity_plan(values: list[list[Any]], *, column: int, sheet_id: int, owner: str) -> dict[str, Any]:
    rows = _rows(values)
    if column < max((len(row) for row in rows), default=0) or (rows and IDENTITY_HEADER in rows[0]):
        raise ProjectError("SHEETS_IDENTITY_COLUMN_OWNERSHIP", "初始化只能创建一列新的系统身份，不能接管已有同名列。", 409)
    fingerprints = [digest(row) for row in rows[1:] if row]
    if len(fingerprints) != len(set(fingerprints)):
        raise ProjectError("SHEETS_IDENTITY_ROWS_AMBIGUOUS", "存在无法区分的同内容行，请先在来源中增加可区分内容。", 409)
    return {
        "sheetId": sheet_id, "columnIndex": column, "owner": owner,
        "beforeDigest": digest(rows), "rowCount": max(len(rows), 1),
        "values": [IDENTITY_HEADER] + [str(uuid4()) if row else "" for row in rows[1:]],
    }


def verify_identity(plan: dict[str, Any], values: list[list[Any]], metadata: list[dict[str, Any]]) -> bool:
    markers = [item for item in metadata if item.get("metadataKey") == IDENTITY_METADATA and item.get("metadataValue") == plan["owner"]]
    if len(markers) != 1:
        return False
    column = plan["columnIndex"]
    expected = {"sheetId": plan["sheetId"], "dimension": "COLUMNS", "startIndex": column, "endIndex": column + 1}
    if markers[0].get("location", {}).get("dimensionRange") != expected:
        return False
    if len(values) != plan["rowCount"]:
        return False
    original = []
    for row, identity in zip(values, plan["values"], strict=True):
        if (row[column] if column < len(row) else "") != identity:
            return False
        original.append(row[:column] + row[column + 1:])
    return digest(_rows(original)) == plan["beforeDigest"]


def identity_requests(plan: dict[str, Any], column_count: int) -> list[dict[str, Any]]:
    column, sheet = plan["columnIndex"], plan["sheetId"]
    dimension = {"sheetId": sheet, "dimension": "COLUMNS", "startIndex": column, "endIndex": column + 1}
    if column > column_count:
        raise ProjectError("SHEETS_IDENTITY_COLUMN_INVALID", "请选择紧邻现有列的新身份列。", 422)
    grow = {"appendDimension": {"sheetId": sheet, "dimension": "COLUMNS", "length": 1}} if column == column_count else {"insertDimension": {"range": dimension, "inheritFromBefore": False}}
    return [grow, {"updateCells": {
        "start": {"sheetId": sheet, "rowIndex": 0, "columnIndex": column},
        "rows": [{"values": [{"userEnteredValue": {"stringValue": value}}]} for value in plan["values"]],
        "fields": "userEnteredValue",
    }}, {"createDeveloperMetadata": {"developerMetadata": {
        "metadataKey": IDENTITY_METADATA, "metadataValue": plan["owner"],
        "visibility": "DOCUMENT", "location": {"dimensionRange": dimension},
    }}}]


def owned_identity(plan: dict[str, Any], header: list[str], metadata: list[dict[str, Any]]) -> bool:
    column = plan["columnIndex"]
    markers = [item for item in metadata if item.get("metadataKey") == IDENTITY_METADATA and item.get("metadataValue") == plan["owner"]]
    return (column < len(header) and header[column] == IDENTITY_HEADER and len(markers) == 1
            and markers[0].get("location", {}).get("dimensionRange") == {
                "sheetId": plan["sheetId"], "dimension": "COLUMNS", "startIndex": column, "endIndex": column + 1})


def canonical_uuid(value: Any) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        return False


def source_digest(values: list[list[Any]]) -> str:
    return digest(_rows(values))
