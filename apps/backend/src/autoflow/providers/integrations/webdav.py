from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import httpx

from autoflow.domain.workflows.models import WorkflowError


class WebDavClient:
    def test(self, config: dict[str, Any]) -> None:
        response = self._request(
            "PROPFIND", self._base_url(config), config, headers={"Depth": "0"}, timeout=15
        )
        if response.status_code in {200, 207, 301, 405}:
            return
        self._raise_status(response)

    def list_workflows(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        response = self._request(
            "PROPFIND", self._base_url(config), config, headers={"Depth": "1"}, timeout=20
        )
        if response.status_code not in {200, 207}:
            self._raise_status(response)
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as error:
            raise WorkflowError(
                "WEB_DAV_RESPONSE_INVALID", "WebDAV 列表响应格式无效", 502
            ) from error
        items: list[dict[str, Any]] = []
        namespace = {"d": "DAV:"}
        for element in root.findall("d:response", namespace):
            href = element.find("d:href", namespace)
            filename = unquote((href.text or "").rstrip("/").rsplit("/", 1)[-1]) if href is not None else ""
            if not filename.lower().endswith(".json") or not self._filename(filename):
                continue
            prop = element.find("d:propstat/d:prop", namespace)
            length = prop.find("d:getcontentlength", namespace) if prop is not None else None
            modified = prop.find("d:getlastmodified", namespace) if prop is not None else None
            length_text = length.text if length is not None else None
            items.append(
                {
                    "filename": filename,
                    "name": filename[:-5],
                    "modifiedTime": modified.text if modified is not None and modified.text else "",
                    "size": int(length_text) if length_text and length_text.isdigit() else 0,
                }
            )
        return sorted(items, key=lambda item: item["modifiedTime"], reverse=True)

    def read(self, config: dict[str, Any], filename: str) -> dict[str, Any] | None:
        response = self._request("GET", self._file_url(config, filename), config, timeout=20)
        if response.status_code == 404:
            return None
        if response.status_code not in {200, 206}:
            self._raise_status(response)
        try:
            value = response.json()
        except (UnicodeDecodeError, ValueError) as error:
            raise WorkflowError(
                "WEB_DAV_WORKFLOW_INVALID", "远程工作流文件格式无效", 422
            ) from error
        if not isinstance(value, dict):
            raise WorkflowError(
                "WEB_DAV_WORKFLOW_INVALID", "远程工作流文件格式无效", 422
            )
        return value

    def exists(self, config: dict[str, Any], filename: str) -> bool:
        response = self._request("HEAD", self._file_url(config, filename), config, timeout=15)
        if response.status_code == 200:
            return True
        if response.status_code == 404:
            return False
        response = self._request("GET", self._file_url(config, filename), config, timeout=15)
        if response.status_code in {200, 206}:
            return True
        if response.status_code == 404:
            return False
        self._raise_status(response)
        return False

    def save(self, config: dict[str, Any], filename: str, content: dict[str, Any]) -> str:
        self._ensure_directory(config)
        response = self._request(
            "PUT",
            self._file_url(config, filename),
            config,
            content=json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode(),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=30,
        )
        if response.status_code not in {200, 201, 204}:
            self._raise_status(response)
        return self._filename(filename)

    def delete(self, config: dict[str, Any], filename: str) -> None:
        response = self._request("DELETE", self._file_url(config, filename), config, timeout=20)
        if response.status_code not in {200, 204, 404}:
            self._raise_status(response)

    def _ensure_directory(self, config: dict[str, Any]) -> None:
        response = self._request("MKCOL", self._base_url(config), config, timeout=15)
        if response.status_code not in {200, 201, 204, 301, 405}:
            self._raise_status(response)

    @staticmethod
    def _request(method: str, url: str, config: dict[str, Any], **kwargs: Any) -> httpx.Response:
        username, password = config["username"], config["password"]
        auth = httpx.BasicAuth(username, password) if username or password else None
        try:
            return httpx.request(
                method,
                url,
                auth=auth,
                follow_redirects=False,
                trust_env=False,
                **kwargs,
            )
        except httpx.HTTPError as error:
            raise WorkflowError(
                "WEB_DAV_CONNECTION_FAILED", "WebDAV 连接失败", 502
            ) from error

    @classmethod
    def _file_url(cls, config: dict[str, Any], filename: str) -> str:
        return urljoin(cls._base_url(config), quote(cls._filename(filename), safe=""))

    @staticmethod
    def _filename(value: str) -> str:
        value = value.strip()
        if not value or value in {".", ".."} or "/" in value or "\\" in value:
            raise WorkflowError("WEB_DAV_FILENAME_INVALID", "远程工作流文件名无效", 422)
        return value if value.lower().endswith(".json") else f"{value}.json"

    @staticmethod
    def _base_url(config: dict[str, Any]) -> str:
        value = config["url"].strip()
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise WorkflowError("WEB_DAV_URL_INVALID", "WebDAV 地址无效", 422)
        base = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + "/", "", ""))
        remote = config["remoteDir"].strip().replace("\\", "/")
        parts = [part for part in remote.split("/") if part]
        if any(part in {".", ".."} for part in parts):
            raise WorkflowError("WEB_DAV_DIRECTORY_INVALID", "WebDAV 远程目录无效", 422)
        return urljoin(base, "/".join(quote(part, safe="") for part in parts) + ("/" if parts else ""))

    @staticmethod
    def _raise_status(response: httpx.Response) -> None:
        if response.status_code in {401, 403}:
            raise WorkflowError("WEB_DAV_AUTH_FAILED", "WebDAV 认证失败", 502)
        raise WorkflowError(
            "WEB_DAV_REQUEST_FAILED",
            f"WebDAV 请求失败：HTTP {response.status_code}",
            502,
        )
