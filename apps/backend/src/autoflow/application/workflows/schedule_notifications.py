from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import smtplib
import time
from collections.abc import Mapping
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote_plus

import httpx

from autoflow.domain.workflows.variables import resolve_value


class _CredentialReader:
    def __init__(self, credentials: Any) -> None:
        self._credentials = credentials

    def get_field(self, name: str, field: str) -> Any | None:
        return self._credentials.resolve(name).get(field)


class WorkflowScheduleNotifier:
    """WebRPA notification behavior adapted to AutoFlow managed credentials."""

    def __init__(self, credentials: Any) -> None:
        self._credentials = _CredentialReader(credentials)

    async def notify(
        self, task: Mapping[str, Any], *, status: str, started_at: str, ended_at: str, error: str | None
    ) -> list[dict[str, Any]]:
        should_notify = (status == "success" and task.get("notify_on_success")) or (
            status == "failed" and task.get("notify_on_failure")
        )
        if not should_notify:
            return []
        status_text = "成功" if status == "success" else "失败"
        title = f"[AutoFlow] 任务「{task['name']}」执行{status_text}"
        content = "\n".join(
            filter(
                None,
                (
                    f"任务：{task['name']}",
                    f"工作流：{task.get('workflow_name') or task['workflow_id']}",
                    f"状态：{status_text}",
                    f"开始：{started_at}",
                    f"结束：{ended_at}",
                    f"错误：{error}" if error else None,
                ),
            )
        )
        results: list[dict[str, Any]] = []
        for source in task.get("notify_channels") or []:
            if not isinstance(source, Mapping) or source.get("enabled") is False:
                continue
            channel = resolve_value(dict(source), {}, self._credentials)
            kind = str(channel.get("type") or "")
            try:
                await self._send(kind, channel, title, content)
                results.append({"type": kind, "success": True})
            except Exception as exception:  # noqa: BLE001 - notifications never replace run truth
                results.append({"type": kind, "success": False, "error": str(exception)})
        return results

    async def _send(self, kind: str, channel: Mapping[str, Any], title: str, content: str) -> None:
        if kind == "email":
            await asyncio.to_thread(self._send_email, channel, title, content)
            return
        if kind == "wecom":
            key = str(channel.get("key") or "")
            url = str(channel.get("webhook") or (f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}" if key else ""))
            await self._post(url, {"msgtype": "text", "text": {"content": f"{title}\n{content}"}})
            return
        if kind == "dingtalk":
            token = str(channel.get("access_token") or "")
            url = str(channel.get("webhook") or (f"https://oapi.dingtalk.com/robot/send?access_token={token}" if token else ""))
            secret = str(channel.get("secret") or "")
            if secret:
                timestamp = str(round(time.time() * 1000))
                signature = base64.b64encode(
                    hmac.new(secret.encode(), f"{timestamp}\n{secret}".encode(), hashlib.sha256).digest()
                ).decode()
                url = f"{url}&timestamp={timestamp}&sign={quote_plus(signature)}"
            await self._post(url, {"msgtype": "text", "text": {"content": f"{title}\n{content}"}})
            return
        if kind == "serverchan":
            key = str(channel.get("sendkey") or "")
            await self._post(f"https://sctapi.ftqq.com/{key}.send" if key else "", {"title": title, "desp": content})
            return
        if kind == "webhook":
            await self._post(str(channel.get("url") or ""), {"title": title, "content": content, "source": "AutoFlow"})
            return
        raise RuntimeError("不支持的通知渠道")

    @staticmethod
    def _send_email(channel: Mapping[str, Any], title: str, content: str) -> None:
        host = str(channel.get("smtp_server") or "")
        username = str(channel.get("username") or "")
        password = str(channel.get("password") or "")
        recipients = [item.strip() for item in str(channel.get("to") or username).replace(";", ",").split(",") if item.strip()]
        if not host or not username or not recipients:
            raise RuntimeError("邮件通知配置不完整")
        message = EmailMessage()
        message["Subject"], message["From"], message["To"] = title, username, ",".join(recipients)
        message.set_content(content)
        client_type = smtplib.SMTP_SSL if channel.get("use_ssl", True) else smtplib.SMTP
        with client_type(host, int(channel.get("smtp_port") or 465), timeout=20) as client:
            if not channel.get("use_ssl", True):
                client.starttls()
            client.login(username, password)
            client.send_message(message)

    @staticmethod
    async def _post(url: str, payload: Mapping[str, Any]) -> None:
        if not url:
            raise RuntimeError("通知地址不能为空")
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.post(url, json=payload)
        if not 200 <= response.status_code < 300:
            raise RuntimeError(f"通知服务返回HTTP {response.status_code}")
