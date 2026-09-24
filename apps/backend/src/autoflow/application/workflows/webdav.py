from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any

from autoflow.domain.credentials import CredentialStore, CredentialStoreUnavailableError
from autoflow.domain.workflows.models import WorkflowError
from autoflow.providers.integrations.webdav import WebDavClient

_DEFAULT: dict[str, Any] = {
    "enabled": False,
    "url": "",
    "username": "",
    "remoteDir": "",
}


class WebDavWorkflowService:
    def __init__(
        self, workspace: Path, credentials: CredentialStore, client: WebDavClient | None = None
    ) -> None:
        self._workspace = workspace.resolve()
        self._settings = self._workspace / "studio-webdav.json"
        self._credentials = credentials
        self._client = client or WebDavClient()
        self._lock = RLock()
        digest = hashlib.sha256(str(self._workspace).encode()).hexdigest()
        self._secret_key = f"studio-webdav:{digest}"

    def config(self) -> dict[str, Any]:
        with self._lock:
            if not self._settings.exists():
                return {**_DEFAULT, "password": ""}
            try:
                value = json.loads(self._settings.read_text("utf-8"))
            except (OSError, UnicodeDecodeError, ValueError) as error:
                raise WorkflowError("WEB_DAV_CONFIG_INVALID", "WebDAV 配置无法读取", 500) from error
            try:
                config = self._validate({**_DEFAULT, **value})
            except (TypeError, WorkflowError) as error:
                raise WorkflowError(
                    "WEB_DAV_CONFIG_INVALID", "WebDAV 配置格式无效", 500
                ) from error
            return {**config, "password": ""}

    def save_config(self, value: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            config = self._validate(value)
            old_secret = self._read_secret()
            password = value["password"]
            if password:
                self._write_secret(password.encode())
            try:
                self._write_json(config)
            except OSError as error:
                self._restore_secret(old_secret)
                raise WorkflowError(
                    "WEB_DAV_CONFIG_WRITE_FAILED", "WebDAV 配置无法写入", 507
                ) from error
            except BaseException:
                self._restore_secret(old_secret)
                raise
            return {**config, "password": ""}

    def test(self, value: dict[str, Any]) -> dict[str, bool]:
        config = self._runtime_config(value)
        self._client.test(config)
        return {"success": True}

    def enabled(self) -> bool:
        config = self.config()
        return config["enabled"] is True and bool(config["url"])

    def list_workflows(self) -> list[dict[str, Any]]:
        return self._client.list_workflows(self._stored_runtime_config())

    def read(self, filename: str) -> dict[str, Any] | None:
        return self._client.read(self._stored_runtime_config(), filename)

    def exists(self, filename: str) -> bool:
        return self._client.exists(self._stored_runtime_config(), filename)

    def save(self, filename: str, content: dict[str, Any]) -> str:
        return self._client.save(self._stored_runtime_config(), filename, content)

    def delete(self, filename: str) -> None:
        self._client.delete(self._stored_runtime_config(), filename)

    def _stored_runtime_config(self) -> dict[str, Any]:
        config = self.config()
        if not config["enabled"]:
            raise WorkflowError("WEB_DAV_DISABLED", "WebDAV 未启用", 409)
        return self._runtime_config(config)

    def _runtime_config(self, value: dict[str, Any]) -> dict[str, Any]:
        config = self._validate(value)
        password = value.get("password") or ""
        if not password:
            secret = self._read_secret()
            try:
                password = secret.decode() if secret is not None else ""
            except UnicodeDecodeError as error:
                raise WorkflowError(
                    "WEB_DAV_SECRET_INVALID", "WebDAV 密码数据已损坏", 500
                ) from error
        return {**config, "password": password}

    @staticmethod
    def _validate(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) - {*_DEFAULT, "password"}:
            raise WorkflowError("WEB_DAV_CONFIG_INVALID", "WebDAV 配置格式无效", 422)
        config = {**_DEFAULT, **{key: value.get(key) for key in _DEFAULT}}
        if type(config["enabled"]) is not bool or any(
            not isinstance(config[key], str) for key in ("url", "username", "remoteDir")
        ) or not isinstance(value.get("password", ""), str):
            raise WorkflowError("WEB_DAV_CONFIG_INVALID", "WebDAV 配置格式无效", 422)
        if config["enabled"]:
            WebDavClient._base_url({**config, "password": ""})
        elif config["remoteDir"]:
            remote = config["remoteDir"].replace("\\", "/")
            if any(part in {".", ".."} for part in remote.split("/") if part):
                raise WorkflowError("WEB_DAV_DIRECTORY_INVALID", "WebDAV 远程目录无效", 422)
        return config

    def _read_secret(self) -> bytes | None:
        try:
            return self._credentials.read(self._secret_key)
        except CredentialStoreUnavailableError as error:
            raise WorkflowError("CREDENTIAL_STORE_UNAVAILABLE", "系统凭据库当前不可用", 503) from error

    def _write_secret(self, value: bytes) -> None:
        try:
            self._credentials.write(self._secret_key, value)
        except CredentialStoreUnavailableError as error:
            raise WorkflowError("CREDENTIAL_STORE_UNAVAILABLE", "系统凭据库当前不可用", 503) from error

    def _restore_secret(self, value: bytes | None) -> None:
        try:
            if value is None:
                self._credentials.delete(self._secret_key)
            else:
                self._credentials.write(self._secret_key, value)
        except CredentialStoreUnavailableError as error:
            raise WorkflowError("CREDENTIAL_STORE_UNAVAILABLE", "系统凭据库当前不可用", 503) from error

    def _write_json(self, value: dict[str, Any]) -> None:
        self._settings.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{self._settings.name}.", suffix=".tmp", dir=self._settings.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self._settings)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
