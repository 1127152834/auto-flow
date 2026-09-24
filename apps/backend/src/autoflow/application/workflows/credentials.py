from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from autoflow.domain.credentials import CredentialStore, CredentialStoreUnavailableError
from autoflow.domain.workflows.models import WorkflowError
from autoflow.infrastructure.database.studio_credentials import (
    SqlAlchemyStudioCredentials,
)


class StudioCredentialService:
    def __init__(
        self, metadata: SqlAlchemyStudioCredentials, secrets: CredentialStore
    ) -> None:
        self._metadata = metadata
        self._secrets = secrets
        self._mutation_lock = RLock()

    def list_items(self) -> list[dict[str, Any]]:
        return self._metadata.list_items()

    def names(self) -> list[str]:
        return [item["name"] for item in self.list_items()]

    def upsert(
        self, name: str, fields: Mapping[str, str], description: str | None
    ) -> dict[str, Any]:
        with self._mutation_lock:
            return self._upsert(name, fields, description)

    def _upsert(
        self, name: str, fields: Mapping[str, str], description: str | None
    ) -> dict[str, Any]:
        name = self._name(name)
        incoming = self._fields(fields)
        old = self._read_raw(name)
        merged = self._decode(old) if old is not None else {}
        merged.update(incoming)
        self._write(name, merged)
        try:
            self._metadata.upsert(
                name, description, list(incoming), datetime.now(UTC)
            )
        except BaseException:
            self._restore(name, old)
            raise
        return {"success": True, "name": name}

    def mutate_fields(self, request: Mapping[str, Any]) -> dict[str, Any]:
        with self._mutation_lock:
            return self._mutate_fields(request)

    def _mutate_fields(self, request: Mapping[str, Any]) -> dict[str, Any]:
        command_id = str(request["commandId"])
        name = self._name(str(request["name"]))
        expected_revision = int(request["expectedRevision"])
        operations = list(request["operations"])
        digest = hashlib.sha256(
            json.dumps(
                {
                    "name": name,
                    "expectedRevision": expected_revision,
                    "operations": operations,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        previous = self._metadata.command(command_id, digest)
        if previous is not None:
            return previous
        item = self._metadata.get(name)
        if item is None:
            raise WorkflowError("CREDENTIAL_NOT_FOUND", "凭据不存在", 404)
        if item["revision"] != expected_revision:
            raise WorkflowError(
                "CREDENTIAL_REVISION_CONFLICT",
                "凭据已被修改，请重新读取后编辑字段",
                409,
            )
        old = self._read_raw(name)
        values = self._decode(old)
        next_values = self._apply_operations(values, operations)
        self._write(name, next_values)
        try:
            response, _ = self._metadata.apply_fields(
                name=name,
                expected_revision=expected_revision,
                field_names=list(next_values),
                command_id=command_id,
                request_hash=digest,
                now=datetime.now(UTC),
            )
        except BaseException:
            self._restore(name, old)
            raise
        return response

    def rename(self, old_name: str, new_name: str) -> dict[str, bool]:
        with self._mutation_lock:
            return self._rename(old_name, new_name)

    def _rename(self, old_name: str, new_name: str) -> dict[str, bool]:
        old_name, new_name = self._name(old_name), self._name(new_name)
        if self._metadata.get(old_name) is None:
            raise WorkflowError("CREDENTIAL_NOT_FOUND", "凭据不存在", 404)
        if old_name != new_name and self._metadata.get(new_name) is not None:
            raise WorkflowError("CREDENTIAL_EXISTS", "凭据名称已存在", 409)
        old = self._read_raw(old_name)
        if old is None:
            raise WorkflowError("CREDENTIAL_SECRET_MISSING", "凭据秘密不存在", 409)
        if old_name != new_name:
            self._write_raw(new_name, old)
            try:
                self._delete_secret(old_name)
            except BaseException:
                self._delete_secret(new_name)
                raise
        try:
            self._metadata.rename(old_name, new_name, datetime.now(UTC))
        except BaseException:
            if old_name != new_name:
                self._write_raw(old_name, old)
                self._delete_secret(new_name)
            raise
        return {"success": True}

    def delete(self, name: str) -> dict[str, bool]:
        with self._mutation_lock:
            return self._delete(name)

    def _delete(self, name: str) -> dict[str, bool]:
        name = self._name(name)
        if self._metadata.get(name) is None:
            raise WorkflowError("CREDENTIAL_NOT_FOUND", "凭据不存在", 404)
        old = self._read_raw(name)
        self._delete_secret(name)
        try:
            self._metadata.delete(name)
        except BaseException:
            if old is not None:
                self._write_raw(name, old)
            raise
        return {"success": True}

    def resolve(self, name: str) -> dict[str, str]:
        if self._metadata.get(name) is None:
            raise WorkflowError("CREDENTIAL_NOT_FOUND", "凭据不存在", 404)
        return self._decode(self._read_raw(name))

    @staticmethod
    def _name(value: str) -> str:
        value = value.strip()
        if not value or len(value) > 120:
            raise WorkflowError("CREDENTIAL_NAME_INVALID", "凭据名称无效", 422)
        return value

    @staticmethod
    def _fields(value: Mapping[str, str]) -> dict[str, str]:
        result = {str(key).strip(): field for key, field in value.items()}
        if not result or any(not key for key in result) or len(result) != len(value):
            raise WorkflowError("CREDENTIAL_FIELDS_INVALID", "凭据字段无效", 422)
        return result

    @staticmethod
    def _apply_operations(
        values: dict[str, str], operations: list[Any]
    ) -> dict[str, str]:
        sources: set[str] = set()
        targets = set(values)
        for operation in operations:
            kind, key = operation["kind"], operation["key"]
            if key in sources or key not in values:
                raise WorkflowError("CREDENTIAL_FIELD_CONFLICT", "字段不存在或重复修改", 409)
            sources.add(key)
            if kind == "rename":
                new_key = operation["newKey"]
                if new_key != key and new_key in targets:
                    raise WorkflowError("CREDENTIAL_FIELD_CONFLICT", "目标字段已存在", 409)
                targets.add(new_key)
        result = dict(values)
        for operation in operations:
            key = operation["key"]
            if operation["kind"] == "remove":
                result.pop(key)
            else:
                result[operation["newKey"]] = result.pop(key)
        if not result:
            raise WorkflowError("CREDENTIAL_FIELDS_EMPTY", "至少需要一个字段", 400)
        return result

    @staticmethod
    def _key(name: str) -> str:
        digest = hashlib.sha256(name.encode()).hexdigest()
        return f"studio-credential:{digest}"

    def _read_raw(self, name: str) -> bytes | None:
        try:
            return self._secrets.read(self._key(name))
        except CredentialStoreUnavailableError as error:
            raise WorkflowError(
                "CREDENTIAL_STORE_UNAVAILABLE", "系统凭据库当前不可用", 503
            ) from error

    def _write_raw(self, name: str, value: bytes) -> None:
        try:
            self._secrets.write(self._key(name), value)
        except CredentialStoreUnavailableError as error:
            raise WorkflowError(
                "CREDENTIAL_STORE_UNAVAILABLE", "系统凭据库当前不可用", 503
            ) from error

    def _delete_secret(self, name: str) -> None:
        try:
            self._secrets.delete(self._key(name))
        except CredentialStoreUnavailableError as error:
            raise WorkflowError(
                "CREDENTIAL_STORE_UNAVAILABLE", "系统凭据库当前不可用", 503
            ) from error

    def _write(self, name: str, value: Mapping[str, str]) -> None:
        self._write_raw(
            name,
            json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode(),
        )

    def _restore(self, name: str, value: bytes | None) -> None:
        if value is None:
            self._delete_secret(name)
        else:
            self._write_raw(name, value)

    @staticmethod
    def _decode(value: bytes | None) -> dict[str, str]:
        if value is None:
            return {}
        try:
            decoded = json.loads(value)
        except (UnicodeDecodeError, ValueError) as error:
            raise WorkflowError("CREDENTIAL_SECRET_INVALID", "凭据秘密已损坏", 500) from error
        if not isinstance(decoded, dict) or not all(
            isinstance(key, str) and isinstance(field, str)
            for key, field in decoded.items()
        ):
            raise WorkflowError("CREDENTIAL_SECRET_INVALID", "凭据秘密已损坏", 500)
        return decoded
