"""Recorded stand-in for the Google Sheets REST surface.

The transport is the only component that would touch the network, so a fake
recorded transport lets every Sheets test run offline while the rest of the
stack (HTTP, operation envelope, DB, transactions) stays real.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoflow.bootstrap.app import create_app
from autoflow.bootstrap.config import Settings
from autoflow.providers.data import google_auth
from autoflow.providers.data.google_sheets import API_ROOT, SheetsApiError
from tests.fixtures.model_management import FakeCredentialStore, FakeModelGateway

HOST_TOKEN = "sheets-host"
RENDERER_TOKEN = "sheets-renderer"

_REFERENCE = re.compile(r"^\$?([A-Za-z]*)\$?(\d*)$")
_RANGE = re.compile(r"^(?:'(?P<sheet>(?:[^']|'')*)'!)?(?P<body>.+)$")


def column_index(letters: str) -> int:
    """A1 letters to a 0-based column index."""
    index = 0
    for letter in letters.upper():
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def _column(reference: str) -> int | None:
    match = _REFERENCE.match(reference)
    return None if not match or not match.group(1) else column_index(match.group(1))


def _row(reference: str) -> int | None:
    match = _REFERENCE.match(reference)
    return None if not match or not match.group(2) else int(match.group(2)) - 1


def parse_range(text: str) -> tuple[str, int | None, int | None, int | None, int | None]:
    match = _RANGE.match(text)
    assert match is not None, text
    sheet = (match.group("sheet") or "").replace("''", "'")
    start, _, end = match.group("body").partition(":")
    end = end or start
    return sheet, _row(start), _column(start), _row(end), _column(end)


class FakeSheetsTransport:
    """A spreadsheet held in memory, addressed by the same A1 ranges we send."""

    def __init__(
        self,
        sheets: dict[str, list[list[Any]]],
        *,
        spreadsheet_id: str = "spreadsheet-1",
        title: str = "来源表",
        formulas: dict[str, list[list[Any]]] | None = None,
    ) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.title = title
        self.ids: dict[str, int] = {}
        self.grids: dict[int, list[list[Any]]] = {}
        self.formulas: dict[int, list[list[Any]]] = {}
        for index, (name, grid) in enumerate(sheets.items()):
            sheet_id = 1000 + index
            self.ids[name] = sheet_id
            self.grids[sheet_id] = [list(row) for row in grid]
            if formulas and name in formulas:
                self.formulas[sheet_id] = [list(row) for row in formulas[name]]
        self.calls: list[tuple[str, str, Any]] = []
        self.fail_next: SheetsApiError | None = None
        self.fail_writes: list[SheetsApiError] = []

    # ------------------------------------------------------------------ transport

    def send(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append((method, url, json))
        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error
        if self.fail_writes and method != "GET":
            raise self.fail_writes.pop(0)
        if url == f"{API_ROOT}/{self.spreadsheet_id}":
            return self._metadata()
        if "/values/" in url:
            render = (params or {}).get("valueRenderOption")
            if method == "GET":
                return {"values": self._read(url.rsplit("/values/", 1)[1], render)}
            return self._write(url.rsplit("/values/", 1)[1], json or {})
        if url.endswith("/values:batchUpdate"):
            for entry in (json or {}).get("data", []):
                self._write(str(entry["range"]), entry)
            return {"totalUpdatedCells": 1}
        if url.endswith(":batchUpdate"):
            return {"replies": [{} for _ in (json or {}).get("requests", [])]}
        raise AssertionError(f"unexpected Sheets call {method} {url}")

    # ------------------------------------------------------------------- grid ops

    def grid(self, sheet: str) -> list[list[Any]]:
        return self.grids[self.ids[sheet]]

    def changes(self) -> int:
        return sum(1 for method, _, _ in self.calls if method != "GET")

    def _metadata(self) -> dict[str, Any]:
        return {
            "properties": {"title": self.title, "timeZone": "Asia/Shanghai"},
            "sheets": [
                {
                    "properties": {
                        "sheetId": sheet_id,
                        "title": name,
                        "gridProperties": {"rowCount": 1000, "columnCount": 26},
                    }
                }
                for name, sheet_id in self.ids.items()
            ],
        }

    def _read(self, text: str, render: str | None) -> list[list[Any]]:
        sheet, start_row, start_col, end_row, end_col = parse_range(text)
        sheet_id = self.ids[sheet]
        source = (
            self.formulas.get(sheet_id, self.grids[sheet_id])
            if render == "FORMULA"
            else self.grids[sheet_id]
        )
        first_row = start_row or 0
        last_row = len(source) - 1 if end_row is None else end_row
        width = max((len(row) for row in source), default=0)
        first_col = start_col or 0
        last_col = width - 1 if end_col is None else end_col
        rows = []
        for row in source[first_row : last_row + 1]:
            padded = list(row) + [""] * (last_col + 1 - len(row))
            rows.append(padded[first_col : last_col + 1])
        return rows

    def _write(self, text: str, payload: dict[str, Any]) -> dict[str, Any]:
        sheet, start_row, start_col, _, _ = parse_range(text)
        grid = self.grids[self.ids[sheet]]
        for offset, row in enumerate(payload.get("values", [])):
            index = (start_row or 0) + offset
            while len(grid) <= index:
                grid.append([])
            for position, value in enumerate(row):
                column = (start_col or 0) + position
                target = grid[index]
                while len(target) <= column:
                    target.append("")
                target[column] = value
        return {"updatedCells": 1}


class FakeTokenTransport:
    """Stands in for the Google OAuth token endpoint."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        self.calls.append(url)
        if url == google_auth.REVOKE_URL:
            return {}
        return {"access_token": "access-token", "expires_in": 3600}


def oauth_credential(*, label: str = "测试账号", writable: bool = True) -> dict[str, Any]:
    return {
        "authMethod": "oauth",
        "accountLabel": label,
        "grantedScope": (
            google_auth.SHEETS_SCOPE if writable else google_auth.READONLY_SHEETS_SCOPE
        ),
        "refreshToken": "refresh-token",
        "clientId": "client-id",
        "clientSecret": "client-secret",
    }


def sheets_app(
    tmp_path: Path,
    transport: FakeSheetsTransport,
    *,
    credentials: FakeCredentialStore | None = None,
    tokens: FakeTokenTransport | None = None,
) -> FastAPI:
    return create_app(
        Settings(
            data_dir=str(tmp_path),
            instance_id="sheets-test",
            instance_token=RENDERER_TOKEN,
            host_token=HOST_TOKEN,
            api_version="v1",
        ),
        credential_store=credentials or FakeCredentialStore(),
        model_gateway=FakeModelGateway(),
        google_tokens=tokens or FakeTokenTransport(),
        google_transports=lambda _token: transport,
    )


def authorize(client, project: str, *, label: str = "测试账号", writable: bool = True) -> str:
    """Hand a credential to the host endpoint and return the one shot token."""
    response = client.post(
        "/internal/google-authorizations",
        json={
            "projectId": project,
            "accountLabel": label,
            "authMethod": "oauth",
            "credential": oauth_credential(label=label, writable=writable),
        },
        headers={"x-autoflow-host-token": HOST_TOKEN},
    )
    assert response.status_code == 201, response.text
    return response.json()["authorizationToken"]


def connect(
    client, project: str, key: dict[str, str], *, label: str = "测试账号", writable: bool = True
) -> dict:
    token = authorize(client, project, label=label, writable=writable)
    accepted = client.post(
        f"/api/v1/projects/{project}/sheets/connections",
        json={"accountLabel": label, "authorizationToken": token},
        headers=key,
    )
    assert accepted.status_code == 202, accepted.text
    return operation(client, project, key)


def operation(client, project: str, key: dict[str, str]) -> dict:
    response = client.get(
        f"/api/v1/projects/{project}/operations/by-idempotency-key/{key['Idempotency-Key']}"
    )
    assert response.status_code == 200, response.text
    return response.json()


BINDING_KEYS = (
    "connectionId",
    "spreadsheetId",
    "sheetId",
    "identityStrategy",
    "mapping",
)


def impacted(client, project: str, action: str, body: dict, locator: dict) -> int:
    """Quote the shared impact confirmation the way the wizard does.

    Every Sheets command that changes stored state re-derives its facts inside
    the write transaction, so a test that wants to exercise the write has to
    ask ``/mutation-impact`` first. The preview is the only source of a valid
    ``impactRevision``; a made up number is a stale confirmation.
    """
    preview = client.post(
        f"/api/v1/projects/{project}/mutation-impact",
        json={"action": action, "target": locator, "change": body},
    )
    assert preview.status_code == 200, preview.text
    return preview.json()["impactRevision"]


def binding_impact(client, project: str, table: str, body: dict) -> dict:
    """Return the binding body with a freshly issued ``impactRevision``."""
    locator = {"type": "table", "projectId": project, "tableId": table}
    change = {key: body[key] for key in BINDING_KEYS}
    return {
        **body,
        "impactRevision": impacted(
            client, project, "changeSheetsBinding", change, locator
        ),
    }


def unbind_impact(client, project: str, table: str) -> int:
    locator = {"type": "table", "projectId": project, "tableId": table}
    return impacted(
        client, project, "removeSheetsBinding", {"mode": "remove"}, locator
    )


def disconnect_impact(client, project: str, connection: str, mode: str) -> int:
    locator = {
        "type": "sheetsConnection",
        "projectId": project,
        "connectionId": connection,
    }
    return impacted(client, project, "disconnectSheets", {"mode": mode}, locator)


def new_project(client, name: str = "P") -> str:
    from uuid import uuid4

    response = client.post(
        "/api/v1/projects",
        json={"name": name},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code in {200, 201}, response.text
    return response.json()["projectId"]


def new_table(client, project: str, name: str = "T") -> dict:
    from uuid import uuid4

    response = client.post(
        f"/api/v1/projects/{project}/tables",
        json={"name": name},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code in {200, 201}, response.text
    return response.json()


def new_field(client, project: str, table: str, key: str, name: str, **extra: Any) -> dict:
    from uuid import uuid4

    body = {
        "definition": {
            "key": key,
            "name": name,
            "type": extra.pop("type", "string"),
            "required": extra.pop("required", False),
            "validation": {},
        },
        "expectedTableRevision": extra.pop("expectedTableRevision"),
        "sourceColumnPolicy": extra.pop("sourceColumnPolicy", "localOnly"),
    }
    response = client.post(
        f"/api/v1/projects/{project}/tables/{table}/fields",
        json=body,
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    return response.json()["field"]


@dataclass
class SheetsTable:
    """A bound table plus the handles a test needs to drive it."""

    client: Any
    transport: FakeSheetsTransport
    project: str
    table: str
    connection: str
    fields: dict[str, dict]
    binding: dict

    def url(self, suffix: str = "") -> str:
        return f"/api/v1/projects/{self.project}/tables/{self.table}{suffix}"

    def field_id(self, key: str) -> str:
        return self.fields[key]["ref"]["fieldId"]

    def table_revision(self) -> int:
        return self.client.get(
            f"/api/v1/projects/{self.project}/tables/{self.table}"
        ).json()["tableRevision"]

    def dataset_generation(self) -> str:
        return self.client.get(
            f"/api/v1/projects/{self.project}/tables/{self.table}"
        ).json()["datasetGeneration"]

    def records(self) -> list[dict]:
        response = self.client.get(
            self.url("/records"),
            params={
                "datasetGeneration": self.dataset_generation(),
                "pageSize": 100,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()["items"]


def new_key() -> dict[str, str]:
    from uuid import uuid4

    return {"Idempotency-Key": str(uuid4())}


@contextmanager
def open_sheets_table(
    tmp_path: Path,
    transport: FakeSheetsTransport,
    columns: list[tuple[str, str, str]],
    *,
    mapping_columns: dict[str, str] | None = None,
    identity_key: str = "code",
    writable: bool = True,
    credentials: FakeCredentialStore | None = None,
) -> Iterator[SheetsTable]:
    """Create project → connection → table → fields → inspected binding.

    ``columns`` are ``(fieldKey, displayName, type)`` in table order; the source
    column for each is the same A1 letter the fake grid uses.
    """
    app = sheets_app(tmp_path, transport, credentials=credentials)
    with TestClient(app, headers={"x-autoflow-token": RENDERER_TOKEN}) as client:
        project = new_project(client)
        connection = connect(client, project, new_key(), writable=writable)["result"]
        table = new_table(client, project)
        fields: dict[str, dict] = {}
        revision = 1
        for key, name, kind in columns:
            fields[key] = new_field(
                client,
                project,
                table["tableId"],
                key,
                name,
                type=kind,
                expectedTableRevision=revision,
            )
            revision += 1
        columns_for = {
            key: mapping_columns[key] if mapping_columns and key in mapping_columns else chr(
                65 + index
            )
            for index, (key, _, _) in enumerate(columns)
        }
        body = {
            "connectionId": connection["connectionId"],
            "spreadsheetId": transport.spreadsheet_id,
            "sheetId": next(iter(transport.ids.values())),
            "identityStrategy": {"kind": "column", "columnId": columns_for[identity_key]},
            "mapping": [
                {
                    "fieldId": fields[key]["ref"]["fieldId"],
                    "columnId": columns_for[key],
                    "direction": "both",
                    "formula": False,
                }
                for key, _, _ in columns
            ],
            "expectedTableRevision": revision,
        }
        body["impactRevision"] = binding_impact(
            client, project, table["tableId"], body
        )["impactRevision"]
        accepted = client.put(
            f"/api/v1/projects/{project}/tables/{table['tableId']}/sheets/binding",
            json=body,
            headers=new_key(),
        )
        assert accepted.status_code == 202, accepted.text
        binding = accepted.json()["operation"]["result"]
        yield SheetsTable(
            client, transport, project, table["tableId"], connection["connectionId"], fields, binding
        )
