"""Impact confirmations for Sheets connections and bindings.

Every Sheets command that changes what is stored quotes a confirmation the
shared `/mutation-impact` report issued. The row binds the project, the exact
action, the complete target and the digest of the intended change; the writer
re-derives the same facts inside its own transaction, so a stale confirmation
can never slip through and a change that appeared in between is reported
instead of being silently overwritten.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.projects.models import ProjectError

from .project_claims import source_record_leases
from .project_data_models import DataImpactRow, DataRecordRow, DataTableRow
from .project_sync_models import SheetsBindingRow, SheetsConnectionRow, SyncOperationRow
from .project_sync_sends import require_source_idle, unresolved_structure

IMPACT_TTL = timedelta(minutes=10)
_OPEN_KINDS = ("push",)
_OPEN_STATUSES = ("pending", "sending", "verifying", "unknown", "paused")


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _stale(blockers: list[dict[str, Any]] | None = None) -> ProjectError:
    return ProjectError(
        "PRECONDITION_FAILED",
        "请重新计算该项变更的影响后再提交。",
        412,
        {"blockers": blockers or [], "retryable": False},
    )


def _table_locator(project_id: str, table_id: str) -> dict[str, Any]:
    return {"type": "table", "projectId": project_id, "tableId": table_id}


def _connection_locator(project_id: str, connection_id: str) -> dict[str, Any]:
    return {
        "type": "sheetsConnection",
        "projectId": project_id,
        "connectionId": connection_id,
    }


class SqlAlchemySheetsImpacts:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    # ------------------------------------------------------------- disconnect

    def preview_disconnect(
        self, project_id: str, connection_id: str, mode: str
    ) -> dict[str, Any]:
        with self._sessions() as session:
            report, facts = self._disconnect_facts(
                session, project_id, connection_id, mode
            )
        return self._save(
            project_id, "disconnectSheets", report["target"], {"mode": mode}, report, facts
        )

    def require_disconnect(
        self,
        session: Session,
        project_id: str,
        connection_id: str,
        mode: str,
        impact_revision: int,
    ) -> dict[str, Any]:
        target = _connection_locator(project_id, connection_id)
        self._require(
            session,
            project_id,
            "disconnectSheets",
            target,
            {"mode": mode},
            impact_revision,
            lambda: self._disconnect_facts(session, project_id, connection_id, mode),
        )
        return target

    def _disconnect_facts(
        self, session: Session, project_id: str, connection_id: str, mode: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if mode not in {"disconnect", "forgetCredential"}:
            raise _invalid("mode", "mode 必须是 disconnect 或 forgetCredential")
        row = session.get(SheetsConnectionRow, connection_id)
        if row is None or row.project_id != project_id or row.revoked_at is not None:
            raise ProjectError(
                "SHEETS_CONNECTION_NOT_FOUND", "Google 连接不存在。", 404
            )
        if any(item.project_id == project_id and item.request.get("connectionId") == connection_id for item in unresolved_structure(session)):
            raise ProjectError("SHEETS_SOURCE_SEND_IN_PROGRESS", "该连接仍有未确认的来源结构操作，请先核验。", 409)
        bound = sorted(
            session.scalars(
                select(SheetsBindingRow.table_id).where(
                    SheetsBindingRow.connection_id == connection_id
                )
            ).all()
        )
        blockers = [
            {
                "code": "SHEETS_CONNECTION_IN_USE",
                "resource": _table_locator(project_id, table_id),
                "state": "blocked",
                "message": "仍有数据表绑定使用该连接，请先解除绑定。",
            }
            for table_id in bound
        ]
        impacts: list[dict[str, Any]] = []
        if mode == "forgetCredential":
            impacts.append(
                {
                    "code": "SHEETS_CREDENTIAL_REMOVED",
                    "resource": _connection_locator(project_id, connection_id),
                    "message": "本机保存的 Google 凭据会被删除，需要重新授权才能再次连接。",
                    "blocking": False,
                }
            )
        report = {
            "target": _connection_locator(project_id, connection_id),
            "expectedRevisions": {},
            "impacts": impacts,
            "blockers": blockers,
        }
        facts = {
            "connectionId": connection_id,
            "state": row.state,
            "boundTables": bound,
        }
        return report, facts

    # ---------------------------------------------------------------- binding

    def preview_binding(
        self, project_id: str, table_id: str, change: dict[str, Any], *, own: str | None = None
    ) -> dict[str, Any]:
        with self._sessions() as session:
            report, facts = self._binding_facts(session, project_id, table_id, change, own=own)
        return self._save(
            project_id, "changeSheetsBinding", report["target"], change, report, facts
        )

    def require_binding(
        self,
        session: Session,
        project_id: str,
        table_id: str,
        change: dict[str, Any],
        impact_revision: int,
        *, own: str | None = None,
    ) -> dict[str, Any]:
        self._require(
            session,
            project_id,
            "changeSheetsBinding",
            _table_locator(project_id, table_id),
            change,
            impact_revision,
            lambda: self._binding_facts(session, project_id, table_id, change, own=own),
        )
        return change

    def _binding_facts(
        self, session: Session, project_id: str, table_id: str, change: dict[str, Any], *, own: str | None = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        table = session.get(DataTableRow, table_id)
        if table is None or table.project_id != project_id:
            raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
        connection_id = change["connectionId"]
        connection = session.get(SheetsConnectionRow, connection_id)
        if (
            connection is None
            or connection.project_id != project_id
            or connection.revoked_at is not None
        ):
            raise ProjectError(
                "SHEETS_CONNECTION_NOT_FOUND", "Google 连接不存在。", 404
            )
        existing = session.get(SheetsBindingRow, table_id)
        epoch = existing.binding_epoch if existing else 0
        columns = {str(entry["columnId"]).upper() for entry in change["mapping"]}
        overlaps = _overlaps(session, project_id, table_id, change, columns)
        require_source_idle(session, change["spreadsheetId"], own=own)
        targets = {(change["spreadsheetId"], change["sheetId"])}
        if existing is not None:
            require_source_idle(session, existing.spreadsheet_id, own=own)
            targets.add((existing.spreadsheet_id, existing.sheet_id))
        leases = {lease.id: lease for spreadsheet, sheet in targets for lease in source_record_leases(session, spreadsheet, sheet)}
        blockers: list[dict[str, Any]] = _source_blockers(project_id, table_id, bool(leases))
        if connection.state != "available":
            blockers.append(
                {
                    "code": "SHEETS_CONNECTION_UNAVAILABLE",
                    "resource": _connection_locator(project_id, connection_id),
                    "state": "blocked",
                    "message": "连接的授权已失效，请重新授权后再绑定。",
                }
            )
        impacts: list[dict[str, Any]] = []
        if existing is not None:
            impacts.append(
                {
                    "code": "SHEETS_BINDING_REBOUND",
                    "resource": _table_locator(project_id, table_id),
                    "message": "改绑会建立新的数据代次，原记录状态与关联不会继承。",
                    "blocking": False,
                }
            )
        for overlap in overlaps:
            impacts.append(
                {
                    "code": "SHEETS_MAPPING_OVERLAP",
                    "resource": _table_locator(project_id, table_id),
                    "message": (
                        f"与项目 {overlap['projectId']} 的表 {overlap['tableId']} "
                        f"共用列 {', '.join(overlap['columnIds'])}；"
                        "两端写入同一物理列，请确认后再保存。"
                    ),
                    "blocking": False,
                }
            )
        expected = {"tableRevision": table.table_revision}
        if epoch >= 1:
            expected["bindingEpoch"] = epoch
        report = {
            "target": _table_locator(project_id, table_id),
            "expectedRevisions": expected,
            "impacts": impacts,
            "blockers": blockers,
        }
        facts = {
            "tableRevision": table.table_revision,
            "bindingEpoch": epoch,
            "connectionId": connection_id,
            "connectionState": connection.state,
            "spreadsheetId": change["spreadsheetId"],
            "sheetId": change["sheetId"],
            "identityStrategy": change["identityStrategy"],
            "mapping": sorted(change["mapping"], key=lambda entry: str(entry["fieldId"])),
            "overlaps": overlaps,
            "sourceLeases": sorted((lease.id, lease.state, lease.lease_generation) for lease in leases.values()),
        }
        return report, facts

    # ----------------------------------------------------------------- unbind

    def preview_unbind(self, project_id: str, table_id: str) -> dict[str, Any]:
        change = {"mode": "remove"}
        with self._sessions() as session:
            report, facts = self._unbind_facts(session, project_id, table_id)
        return self._save(
            project_id, "removeSheetsBinding", report["target"], change, report, facts
        )

    def require_unbind(
        self, session: Session, project_id: str, table_id: str, impact_revision: int
    ) -> None:
        self._require(
            session,
            project_id,
            "removeSheetsBinding",
            _table_locator(project_id, table_id),
            {"mode": "remove"},
            impact_revision,
            lambda: self._unbind_facts(session, project_id, table_id),
        )

    def _unbind_facts(
        self, session: Session, project_id: str, table_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        table = session.get(DataTableRow, table_id)
        if table is None or table.project_id != project_id:
            raise ProjectError("TABLE_NOT_FOUND", "Table was not found", 404)
        binding = session.get(SheetsBindingRow, table_id)
        if binding is None or binding.project_id != project_id:
            raise ProjectError(
                "SHEETS_BINDING_NOT_FOUND", "该表未绑定 Sheets。", 404
            )
        require_source_idle(session, binding.spreadsheet_id)
        open_rows = session.scalars(
            select(SyncOperationRow).where(
                SyncOperationRow.table_id == table_id,
                SyncOperationRow.kind.in_(_OPEN_KINDS),
                SyncOperationRow.operation_id.is_(None),
                SyncOperationRow.status.in_(_OPEN_STATUSES),
            )
        ).all()
        unsent = sum(1 for row in open_rows if row.status != "unknown")
        unknown = len(open_rows) - unsent
        records = session.scalar(
            select(func.count())
            .select_from(DataRecordRow)
            .where(
                DataRecordRow.table_id == table_id,
                DataRecordRow.dataset_generation == table.current_generation,
                DataRecordRow.deleted.is_(False),
            )
        )
        impacts = [
            {
                "code": "SHEETS_LOCAL_COPY_KEPT",
                "resource": _table_locator(project_id, table_id),
                "message": "本地记录、状态和同步历史都会保留，表回到待配置状态。",
                "blocking": False,
            },
            {
                "code": "SHEETS_UNSENT_INTENTS_STOPPED",
                "resource": _table_locator(project_id, table_id),
                "message": (
                    f"停止向该来源发送；{unsent} 条未发送修改、{unknown} 条结果未知的发送"
                    f"与 {int(records or 0)} 条本地记录都会保留为历史证据。"
                ),
                "blocking": False,
            },
        ]
        leases = source_record_leases(session, binding.spreadsheet_id, binding.sheet_id)
        expected = {"tableRevision": table.table_revision, "bindingEpoch": binding.binding_epoch}
        report = {
            "target": _table_locator(project_id, table_id),
            "expectedRevisions": expected,
            "impacts": impacts,
            "blockers": _source_blockers(project_id, table_id, bool(leases)),
        }
        facts = {
            "tableRevision": table.table_revision,
            "bindingEpoch": binding.binding_epoch,
            "connectionId": binding.connection_id,
            "identityStrategy": binding.identity_strategy,
            "sourceLeases": sorted((lease.id, lease.state, lease.lease_generation) for lease in leases),
        }
        return report, facts

    # ------------------------------------------------------------- persistence

    def _save(
        self,
        project_id: str,
        action: str,
        target: dict[str, Any],
        change: dict[str, Any],
        report: dict[str, Any],
        facts: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self._sessions() as session:
            row = DataImpactRow(
                project_id=project_id,
                action=action,
                target=target,
                change_digest=_digest(change),
                expected_revisions=report["expectedRevisions"],
                facts_digest=_digest(facts),
                report={},
                expires_at=now + IMPACT_TTL,
            )
            session.add(row)
            session.flush()
            report.update(impactRevision=row.id, calculatedAt=now.isoformat())
            report["changeDigest"] = row.change_digest
            row.report = report
            session.commit()
            return report

    def _require(
        self,
        session: Session,
        project_id: str,
        action: str,
        target: dict[str, Any],
        change: dict[str, Any],
        impact_revision: int,
        recompute: Any,
    ) -> None:
        if type(impact_revision) is not int or impact_revision < 1:
            raise _stale()
        saved = session.get(DataImpactRow, impact_revision)
        if (
            saved is None
            or saved.project_id != project_id
            or saved.action != action
            or saved.target != target
            or saved.change_digest != _digest(change)
            or _utc(saved.expires_at) <= datetime.now(UTC)
        ):
            raise _stale()
        report, facts = recompute()
        if (
            saved.expected_revisions != report["expectedRevisions"]
            or saved.facts_digest != _digest(facts)
        ):
            raise _stale(report["blockers"])
        if report["blockers"] or saved.report.get("blockers"):
            raise _stale(report["blockers"] or saved.report["blockers"])


def _source_blockers(project_id: str, table_id: str, occupied: bool) -> list[dict[str, Any]]:
    if not occupied:
        return []
    return [{"code": "SHEETS_SOURCE_IN_USE", "resource": _table_locator(project_id, table_id),
             "state": "blocked", "message": "共享来源仍被任务占用，请等待任务完成或恢复占用后重试。"}]


def _overlaps(
    session: Session,
    project_id: str,
    table_id: str,
    change: dict[str, Any],
    columns: set[str],
) -> list[dict[str, Any]]:
    others = session.scalars(
        select(SheetsBindingRow).where(
            SheetsBindingRow.spreadsheet_id == change["spreadsheetId"],
            SheetsBindingRow.sheet_id == change["sheetId"],
            SheetsBindingRow.table_id != table_id,
        )
    ).all()
    found = []
    for row in others:
        shared = sorted(
            {
                str(entry["columnId"]).upper()
                for entry in row.mapping
                if str(entry["columnId"]).upper() in columns
            }
        )
        if shared:
            found.append(
                {
                    "projectId": row.project_id,
                    "tableId": row.table_id,
                    "columnIds": shared,
                }
            )
    return sorted(found, key=lambda item: (item["projectId"], item["tableId"]))


def _invalid(field: str, message: str) -> ProjectError:
    return ProjectError(
        "INVALID_PROJECT_DATA", message, 422, {"field": field, "domainCode": "sheets"}
    )
