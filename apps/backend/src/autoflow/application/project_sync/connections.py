"""Google connections owned by a project.

Credentials are handed over by the desktop host, held in memory until the
renderer redeems the one shot authorization, and then written straight into the
operating system credential store. A service restart drops unredeemed
authorizations, which is exactly the intended boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from autoflow.domain.credentials import CredentialStore, CredentialStoreUnavailableError
from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.database.project_sync import (
    SqlAlchemyProjectSync,
    connection_view,
    digest,
)
from autoflow.providers.data import google_auth

AUTHORIZATION_TTL = timedelta(minutes=10)
_ACCOUNT_LABEL_LIMIT = 120


@dataclass(frozen=True)
class PendingAuthorization:
    project_id: str
    account_label: str
    credential: google_auth.GoogleCredential
    expires_at: datetime


class AuthorizationRegistry:
    """One shot authorizations registered by the trusted desktop host."""

    def __init__(self, ttl: timedelta = AUTHORIZATION_TTL) -> None:
        self._items: dict[str, PendingAuthorization] = {}
        self._ttl = ttl

    def register(
        self, project_id: str, credential: google_auth.GoogleCredential
    ) -> str:
        token = str(uuid4())
        self._items[token] = PendingAuthorization(
            project_id,
            credential.account_label,
            credential,
            datetime.now(UTC) + self._ttl,
        )
        return token

    def redeem(self, project_id: str, token: str) -> PendingAuthorization:
        item = self._items.pop(token, None)
        if item is None:
            raise ProjectError(
                "GOOGLE_AUTHORIZATION_UNKNOWN",
                "授权结果不存在或已被使用，请重新授权。",
                410,
            )
        if item.expires_at <= datetime.now(UTC):
            raise ProjectError(
                "GOOGLE_AUTHORIZATION_EXPIRED", "授权结果已过期，请重新授权。", 410
            )
        if item.project_id != project_id:
            raise ProjectError("GOOGLE_AUTHORIZATION_UNKNOWN", "授权结果不存在。", 410)
        return item


class SheetsConnectionService:
    def __init__(
        self,
        sync: SqlAlchemyProjectSync,
        credentials: CredentialStore,
        tokens: google_auth.TokenTransport,
        authorizations: AuthorizationRegistry,
    ) -> None:
        self._sync, self._credentials = sync, credentials
        self._tokens, self._authorizations = tokens, authorizations

    # -------------------------------------------------------------- host handover

    def register_authorization(self, payload: dict[str, Any]) -> dict[str, Any]:
        required = {"projectId", "accountLabel", "authMethod", "credential"}
        if not required <= set(payload):
            raise _invalid("payload", "缺少授权信息")
        project_id = payload["projectId"]
        label = payload["accountLabel"]
        if not isinstance(project_id, str) or not isinstance(label, str):
            raise _invalid("payload", "授权信息格式不正确")
        label = label.strip()
        if not label or len(label) > _ACCOUNT_LABEL_LIMIT:
            raise _invalid("accountLabel", "账号名称必须为 1–120 个字符")
        credential = payload["credential"]
        if isinstance(credential, str):
            try:
                import json

                credential = json.loads(credential)
            except ValueError as error:
                raise _invalid("credential", "凭据不是合法 JSON") from error
        if not isinstance(credential, dict):
            raise _invalid("credential", "凭据格式不正确")
        method = payload["authMethod"]
        if method not in {"oauth", "service_account"}:
            raise _invalid("authMethod", "授权方式不受支持")
        try:
            parsed = google_auth.GoogleCredential.from_payload(
                {**credential, "authMethod": method, "accountLabel": label}
            )
        except google_auth.GoogleAuthError as error:
            raise ProjectError(error.code, error.message, 422) from error
        self._verify(parsed)
        token = self._authorizations.register(project_id, parsed)
        return {
            "authorizationToken": token,
            "accountLabel": parsed.account_label,
            "writable": parsed.writable,
        }

    def _verify(self, credential: google_auth.GoogleCredential) -> None:
        try:
            google_auth.access_token(credential, self._tokens)
        except google_auth.GoogleAuthError as error:
            raise ProjectError(error.code, error.message, 422) from error

    # ------------------------------------------------------------------- directory

    def list_connections(self, project_id: str) -> dict[str, Any]:
        self._sync.require_project(project_id)
        items = []
        for row in self._sync.connections(project_id):
            items.append(connection_view(row, self._state(row.credential_key)))
        return {"items": items}

    def _state(self, credential_key: str) -> str:
        try:
            raw = self._credentials.read(credential_key)
        except CredentialStoreUnavailableError:
            return "invalid"
        if raw is None:
            return "missing"
        try:
            google_auth.GoogleCredential.from_secret(raw)
        except google_auth.GoogleAuthError:
            return "invalid"
        return "available"

    # ------------------------------------------------------------------- lifecycle

    def create_connection(
        self, project_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if set(payload) != {"accountLabel", "authorizationToken"}:
            raise _invalid("payload", "意外的字段")
        label = payload.get("accountLabel")
        token = payload.get("authorizationToken")
        if not isinstance(label, str) or not isinstance(token, str):
            raise _invalid("payload", "缺少账号名称或授权令牌")
        if label.strip() != label or not label.strip():
            raise _invalid("accountLabel", "账号名称格式不正确")
        _uuid(project_id, "projectId")
        _uuid(key, "Idempotency-Key")
        view, existing = self._sync.accept_project_operation(
            project=project_id,
            kind="connectSheets",
            key=key,
            request={"accountLabel": label, "authorizationToken": digest(token)},
            resource={"type": "project", "projectId": project_id},
        )
        if existing:
            return {"operation": view}
        operation_id = view["operationId"]
        try:
            pending = self._authorizations.redeem(project_id, token)
            if pending.account_label != label:
                raise ProjectError(
                    "GOOGLE_AUTHORIZATION_UNKNOWN", "授权结果不存在。", 410
                )
            credential = pending.credential
            credential_key = f"sheets/{project_id}/{uuid4()}"
            try:
                self._credentials.write(credential_key, credential.to_secret())
            except CredentialStoreUnavailableError as error:
                raise ProjectError(
                    "CREDENTIAL_STORE_UNAVAILABLE", "当前系统凭据存储不可用。", 503
                ) from error
            row = self._sync.add_connection(
                project_id,
                account_label=credential.account_label,
                credential_key=credential_key,
                auth_method=credential.auth_method,
                state="available",
                readable=True,
                writable=credential.writable,
            )
            result = connection_view(row, "available")
        except ProjectError as error:
            self._sync.fail_operation(operation_id, {"code": error.code, "message": error.message, "details": error.details})
            raise
        self._sync.finish_operation(operation_id, result)
        return {"operation": self._sync.operation_view(operation_id)}

    def delete_connection(
        self, project_id: str, connection_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if set(payload) != {"impactRevision", "mode"}:
            raise _invalid("payload", "意外的字段")
        mode = payload["mode"]
        if mode not in {"disconnect", "forgetCredential"}:
            raise _invalid("mode", "mode 必须是 disconnect 或 forgetCredential")
        impact = payload["impactRevision"]
        if type(impact) is not int or impact < 1:
            raise _invalid("impactRevision", "impactRevision 必须是正整数")
        _uuid(project_id, "projectId")
        _uuid(connection_id, "connectionId")
        _uuid(key, "Idempotency-Key")
        view, existing = self._sync.accept_project_operation(
            project=project_id,
            kind="disconnectSheets",
            key=key,
            request={
                "connectionId": connection_id,
                "mode": mode,
                "impactRevision": impact,
            },
            resource={
                "type": "sheetsConnection",
                "projectId": project_id,
                "connectionId": connection_id,
            },
        )
        if existing:
            return {"operation": view}
        operation_id = view["operationId"]
        try:
            # The confirmation is re-derived inside the revoke transaction, so a
            # binding created after the preview is reported instead of lost.
            row = self._sync.revoke_connection(project_id, connection_id, mode, impact)
            credential_key = row.credential_key
            if mode == "forgetCredential":
                try:
                    self._credentials.delete(credential_key)
                except CredentialStoreUnavailableError as error:
                    raise ProjectError(
                        "CREDENTIAL_STORE_UNAVAILABLE",
                        "连接已解除，但本机凭据删除失败。",
                        503,
                    ) from error
            result = {
                "connectionId": connection_id,
                "mode": mode,
                "disconnected": True,
            }
        except ProjectError as error:
            self._sync.fail_operation(
                operation_id,
                {"code": error.code, "message": error.message, "details": error.details},
            )
            raise
        self._sync.finish_operation(operation_id, result)
        return {"operation": self._sync.operation_view(operation_id)}


def _uuid(value: str, field: str) -> str:
    from uuid import UUID

    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise _invalid(field, "Must be a UUID") from error


def _invalid(field: str, message: str) -> ProjectError:
    return ProjectError(
        "INVALID_PROJECT_DATA", message, 422, {"field": field, "domainCode": "sheets"}
    )
