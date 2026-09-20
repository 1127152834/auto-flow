from __future__ import annotations

import asyncio
import io
import json
import smtplib
from collections.abc import Mapping
from email.message import EmailMessage
from typing import Any

import httpx
import paramiko

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_SSH_FILE_BYTES = 64 * 1024 * 1024


class WorkflowIntegrationGateway:
    def __init__(self) -> None:
        self._ssh_clients: dict[str, paramiko.SSHClient] = {}

    async def call(self, integration: str, payload: Mapping[str, Any]) -> Any:
        if integration.startswith("ssh_"):
            return await asyncio.to_thread(self._ssh, integration, payload)
        if integration == "telegram":
            return await self._telegram(payload)
        if integration == "smtp_qq":
            return await asyncio.to_thread(self._smtp_qq, payload)
        if integration != "http":
            raise RuntimeError("不支持的外部服务")
        return await self._http(payload)

    async def close(self) -> None:
        clients, self._ssh_clients = self._ssh_clients, {}
        await asyncio.gather(
            *(asyncio.to_thread(client.close) for client in clients.values()),
            return_exceptions=True,
        )

    def _ssh(self, integration: str, payload: Mapping[str, Any]) -> Any:
        name = str(payload.get("connectionName") or "ssh_conn")
        if integration == "ssh_connect":
            return self._ssh_connect(name, payload)
        client = self._ssh_clients.get(name)
        if client is None:
            raise RuntimeError(f"SSH连接 {name} 不存在")
        try:
            if integration == "ssh_execute":
                return self._ssh_execute(client, payload)
            if integration == "ssh_upload":
                return self._ssh_upload(client, payload)
            if integration == "ssh_download":
                return self._ssh_download(client, payload)
            if integration == "ssh_disconnect":
                self._ssh_clients.pop(name, None)
                client.close()
                return {"ok": True}
        except RuntimeError:
            raise
        except (OSError, paramiko.SSHException) as error:
            raise RuntimeError("SSH操作失败") from error
        raise RuntimeError("不支持的SSH操作")

    def _ssh_connect(
        self, name: str, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        host = str(payload.get("host") or "")
        username = str(payload.get("username") or "")
        password = str(payload.get("password") or "")
        key_content = payload.get("keyContent")
        pkey = None
        if isinstance(key_content, bytes):
            pkey = self._load_private_key(key_content, password or None)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        previous = self._ssh_clients.pop(name, None)
        if previous is not None:
            previous.close()
        try:
            client.connect(
                hostname=host,
                port=int(payload.get("port", 22)),
                username=username,
                password=None if pkey is not None else password,
                pkey=pkey,
                timeout=float(payload.get("timeoutSeconds", 30)),
                allow_agent=False,
                look_for_keys=False,
            )
        except paramiko.AuthenticationException as error:
            client.close()
            raise RuntimeError("SSH认证失败") from error
        except (OSError, paramiko.SSHException) as error:
            client.close()
            raise RuntimeError("SSH连接失败") from error
        self._ssh_clients[name] = client
        return {"connected": True}

    @staticmethod
    def _load_private_key(content: bytes, password: str | None) -> paramiko.PKey:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RuntimeError("SSH密钥格式不受支持") from error
        for key_type in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey):
            try:
                return key_type.from_private_key(io.StringIO(text), password=password)
            except (paramiko.PasswordRequiredException, paramiko.SSHException):
                continue
        raise RuntimeError("SSH密钥格式不受支持")

    @staticmethod
    def _ssh_execute(
        client: paramiko.SSHClient, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        _stdin, stdout, stderr = client.exec_command(
            str(payload.get("command") or ""),
            timeout=float(payload.get("timeoutSeconds", 30)),
        )
        return {
            "output": stdout.read().decode("utf-8", errors="replace"),
            "error": stderr.read().decode("utf-8", errors="replace"),
            "exitCode": stdout.channel.recv_exit_status(),
        }

    @staticmethod
    def _ssh_upload(
        client: paramiko.SSHClient, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        content = payload.get("content")
        if not isinstance(content, bytes):
            raise TypeError("SSH上传内容无效")
        with client.open_sftp() as sftp, sftp.file(
            str(payload.get("remotePath") or ""), "wb"
        ) as remote:
            remote.write(content)
        return {"uploaded": len(content)}

    @staticmethod
    def _ssh_download(
        client: paramiko.SSHClient, payload: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        max_bytes = min(int(payload.get("maxBytes", MAX_SSH_FILE_BYTES)), MAX_SSH_FILE_BYTES)
        with client.open_sftp() as sftp, sftp.file(
            str(payload.get("remotePath") or ""), "rb"
        ) as remote:
            content = remote.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise RuntimeError("SSH下载文件超过64 MiB限制")
        return {"content": bytes(content)}

    async def _telegram(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        token = str(payload.get("botToken") or "")
        chat_id = str(payload.get("chatId") or "")
        message = str(payload.get("message") or "")
        title = str(payload.get("title") or "")
        response = await self._http(
            {
                "url": f"https://api.telegram.org/bot{token}/sendMessage",
                "method": "POST",
                "json": {
                    "chat_id": chat_id,
                    "text": f"{title}\n{message}" if title else message,
                },
                "timeoutSeconds": payload.get("timeoutSeconds", 30),
                "followRedirects": False,
                "verifySSL": True,
            }
        )
        body = response.get("body")
        if (
            response.get("statusCode") != 200
            or not isinstance(body, Mapping)
            or body.get("ok") is not True
        ):
            raise RuntimeError("Telegram通知失败")
        return {"ok": True}

    @staticmethod
    def _smtp_qq(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        sender = str(payload.get("senderEmail") or "")
        recipient = str(payload.get("recipientEmail") or "")
        auth_code = str(payload.get("authCode") or "")
        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = str(payload.get("subject") or "(无标题)")
        message.set_content(str(payload.get("content") or ""))
        try:
            with smtplib.SMTP_SSL(
                "smtp.qq.com", 465, timeout=float(payload.get("timeoutSeconds", 30))
            ) as client:
                client.login(sender, auth_code)
                client.send_message(message)
        except smtplib.SMTPAuthenticationError as error:
            raise RuntimeError("邮箱认证失败，请检查邮箱地址和授权码") from error
        except (OSError, smtplib.SMTPException) as error:
            raise RuntimeError("发送邮件失败") from error
        return {"accepted": True}

    async def _http(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        url = payload.get("url")
        method = payload.get("method")
        if not isinstance(url, str) or not url:
            raise RuntimeError("HTTP请求地址不能为空")
        if not isinstance(method, str) or not method:
            raise RuntimeError("HTTP请求方法不能为空")
        timeout = float(payload.get("timeoutSeconds", 30))
        try:
            async with (
                httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=bool(payload.get("followRedirects", False)),
                    verify=bool(payload.get("verifySSL", True)),
                    trust_env=False,
                    cookies=dict(payload.get("cookies") or {}),
                ) as client,
                client.stream(
                    method,
                    url,
                    headers=dict(payload.get("headers") or {}),
                    json=payload.get("json"),
                    content=payload.get("content"),
                    data=payload.get("form"),
                ) as response,
            ):
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise RuntimeError("HTTP响应超过8 MiB限制")
                raw = bytes(content)
                try:
                    body: Any = json.loads(raw) if raw else ""
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body = raw.decode(response.encoding or "utf-8", errors="replace")
                return {
                    "statusCode": response.status_code,
                    "body": body,
                    "headers": dict(response.headers),
                    "cookies": dict(response.cookies),
                }
        except httpx.TimeoutException as error:
            raise RuntimeError(f"HTTP请求超时 ({timeout:g}秒)") from error
        except httpx.RequestError as error:
            raise RuntimeError("无法连接到HTTP服务") from error
