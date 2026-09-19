"""Google Sheets REST access with an injectable transport.

The transport is the only piece that touches the network, so every test can
drive the client with a recorded stand-in and the production path stays one
implementation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

API_ROOT = "https://sheets.googleapis.com/v4/spreadsheets"
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RETRYABLE_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "backendError"}


class SheetsApiError(RuntimeError):
    """A Sheets failure split into retryable, unknown and hard rejections."""

    def __init__(self, status: int, reason: str, message: str) -> None:
        super().__init__(message)
        self.status, self.reason, self.message = status, reason, message

    @property
    def unsent(self) -> bool:
        """True when the request provably never left this machine."""
        return self.status == -1

    @property
    def uncertain(self) -> bool:
        """True when the request was sent but the outcome is unknown."""
        return self.status == 0

    @property
    def retryable(self) -> bool:
        # A request that never left the machine is always safe to send again.
        return (
            self.status == -1
            or self.status in _RETRYABLE_STATUS
            or self.reason in _RETRYABLE_REASONS
        )


class SheetsTransport(Protocol):
    def send(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


class HttpxSheetsTransport:
    """Attach the current access token and translate transport failures."""

    def __init__(
        self, token_source: Callable[[], str], timeout: float = 30.0
    ) -> None:
        self._token_source, self._timeout = token_source, timeout

    def send(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers={
                        "Authorization": f"Bearer {self._token_source()}",
                        "Accept": "application/json",
                    },
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as error:
            raise SheetsApiError(-1, "unreachable", "无法连接 Google Sheets。") from error
        except httpx.HTTPError as error:
            raise SheetsApiError(
                0, "timeout", "Google Sheets 未在时限内返回结果。"
            ) from error
        payload = _json(response)
        if response.status_code >= 400:
            raise _error(response.status_code, payload)
        return payload


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _error(status: int, payload: dict[str, Any]) -> SheetsApiError:
    error = payload.get("error")
    error = error if isinstance(error, dict) else {}
    reason = "unknown"
    errors = error.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        reason = str(errors[0].get("reason") or reason)
    elif error.get("status"):
        reason = str(error["status"])
    message = str(error.get("message") or f"Google Sheets 返回 HTTP {status}。")
    return SheetsApiError(status, reason, message)


@dataclass(frozen=True)
class SheetEntry:
    sheet_id: int
    title: str
    row_count: int
    column_count: int


@dataclass(frozen=True)
class Spreadsheet:
    spreadsheet_id: str
    title: str
    time_zone: str
    sheets: tuple[SheetEntry, ...]

    def sheet(self, sheet_id: int) -> SheetEntry | None:
        return next((entry for entry in self.sheets if entry.sheet_id == sheet_id), None)


class SheetsClient:
    def __init__(self, transport: SheetsTransport) -> None:
        self._transport = transport

    def metadata(self, spreadsheet_id: str) -> Spreadsheet:
        url = f"{API_ROOT}/{spreadsheet_id}"
        payload = self._transport.send(
            "GET",
            url,
            params={
                "includeGridData": "false",
                "fields": (
                    "properties(title,timeZone),"
                    "sheets(properties(sheetId,title,gridProperties(rowCount,columnCount)))"
                ),
            },
        )
        properties = payload.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        entries: list[SheetEntry] = []
        for raw in _list(payload.get("sheets")):
            sheet_properties = raw.get("properties")
            if not isinstance(sheet_properties, dict):
                continue
            grid = sheet_properties.get("gridProperties")
            grid = grid if isinstance(grid, dict) else {}
            entries.append(
                SheetEntry(
                    int(sheet_properties.get("sheetId", -1)),
                    str(sheet_properties.get("title") or ""),
                    int(grid.get("rowCount") or 0),
                    int(grid.get("columnCount") or 0),
                )
            )
        return Spreadsheet(
            spreadsheet_id,
            str(properties.get("title") or ""),
            str(properties.get("timeZone") or "UTC"),
            tuple(entries),
        )

    def values(
        self, spreadsheet_id: str, cell_range: str, render: str = "UNFORMATTED_VALUE"
    ) -> list[list[Any]]:
        payload = self._transport.send(
            "GET",
            f"{API_ROOT}/{spreadsheet_id}/values/{cell_range}",
            params={
                "majorDimension": "ROWS",
                "valueRenderOption": render,
                "dateTimeRenderOption": "SERIAL_NUMBER",
            },
        )
        return [
            [cell for cell in row] if isinstance(row, list) else []
            for row in _list(payload.get("values"))
        ]

    def update_values(
        self,
        spreadsheet_id: str,
        cell_range: str,
        values: list[list[Any]],
        input_option: str = "RAW",
    ) -> dict[str, Any]:
        return self._transport.send(
            "PUT",
            f"{API_ROOT}/{spreadsheet_id}/values/{cell_range}",
            params={"valueInputOption": input_option},
            json={"majorDimension": "ROWS", "values": values},
        )

    def batch_update_values(
        self,
        spreadsheet_id: str,
        data: list[dict[str, Any]],
        input_option: str = "RAW",
    ) -> dict[str, Any]:
        return self._transport.send(
            "POST",
            f"{API_ROOT}/{spreadsheet_id}/values:batchUpdate",
            json={
                "valueInputOption": input_option,
                "data": data,
            },
        )

    def batch_update(
        self, spreadsheet_id: str, requests: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return self._transport.send(
            "POST",
            f"{API_ROOT}/{spreadsheet_id}:batchUpdate",
            json={"requests": requests, "includeSpreadsheetInResponse": False},
        )


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def column_letter(index: int) -> str:
    """0-based column index to A1 letters."""
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def quoted(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def cell(sheet_title: str, column: int, row: int) -> str:
    """1-based row, 0-based column, always absolute."""
    return f"{quoted(sheet_title)}!${column_letter(column)}${row}"


def column_range(sheet_title: str, column: int, first_row: int = 2) -> str:
    letters = column_letter(column)
    return f"{quoted(sheet_title)}!${letters}${first_row}:${letters}"
