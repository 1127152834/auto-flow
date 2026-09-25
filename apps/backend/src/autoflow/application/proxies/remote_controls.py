"""Remote proxy commands: persist once, send once, then confirm by reading."""

import asyncio
import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import uuid4

from autoflow.domain.credentials import CredentialStore
from autoflow.domain.proxies.errors import (
    CapabilityUnavailableError,
    InvalidProxyGroupError,
    OperationInProgressError,
    ProviderError,
    ProxyError,
    RevisionConflictError,
)
from autoflow.domain.proxies.models import Health
from autoflow.domain.proxies.ports import ProxyUnitOfWork
from autoflow.domain.proxies.remote import (
    ROTATION_INTERVALS,
    OperationRepository,
    OperationStatus,
    RemoteKind,
    RemoteOperation,
    RemoteProvider,
    RemoteState,
)

from .connections import ConnectionService
from .projections import ProjectionService
from .sync import provider_error
from .usage import ProxyUsage


class ProxyRemoteControls:
    def __init__(
        self,
        uow: Callable[[], ProxyUnitOfWork],
        operations: OperationRepository,
        credentials: CredentialStore,
        provider: RemoteProvider,
        *,
        confirmation_seconds: float = 120,
        poll_seconds: float = 2,
    ):
        self._uow, self.operations = uow, operations
        self._credentials, self._provider = credentials, provider
        self._budget, self._poll = confirmation_seconds, poll_seconds
        self._tasks: dict[str, asyncio.Task] = {}
        self._closing = False
        self.usage = ProxyUsage()

    def _context(self, proxy_id: str, secret_ref: str | None = None):
        with self._uow() as uow:
            proxy = ProjectionService(uow.repository).get(proxy_id)
            service = ConnectionService(uow.repository, self._credentials)
            connection = service.get(proxy.connection_id)
            if secret_ref is not None and secret_ref != connection.secret_ref:
                raise RevisionConflictError("连接已替换，旧操作不会覆盖当前数据")
            if proxy.stale or proxy.remote_missing:
                raise RevisionConflictError("代理连接信息已过期，请先刷新代理列表")
            return proxy, connection, service.read_key(connection)

    async def state(self, proxy_id: str):
        proxy, connection, key = self._context(proxy_id)
        value = await self._provider.get_state(key, proxy.provider_id)
        if value.proxy.provider_id != proxy.provider_id:
            raise RevisionConflictError("ProxyPanel 返回的代理身份不匹配")
        self._context(proxy_id, connection.secret_ref)
        return value, self.operations.active(proxy_id) or self.operations.latest(
            proxy_id
        )

    async def locations(self, connection_id: str):
        with self._uow() as uow:
            service = ConnectionService(uow.repository, self._credentials)
            connection = service.get(connection_id)
            key = service.read_key(connection)
        result = await self._provider.get_locations(key)
        with self._uow() as uow:
            current = ConnectionService(uow.repository, self._credentials).get(
                connection_id
            )
            if current.secret_ref != connection.secret_ref:
                raise RevisionConflictError("连接已替换，请重新加载地点")
        return result

    async def schedule(self, proxy_id: str):
        proxy, connection, key = self._context(proxy_id)
        value = await self._provider.get_schedule(key, proxy.provider_id)
        self._context(proxy_id, connection.secret_ref)
        return value

    def submit(
        self,
        proxy_id: str,
        kind: RemoteKind,
        payload: dict,
        expected_revision: int,
        key: str,
        *, confirmation_seconds: float | None = None, retry_if_ready: bool = False,
        owner: str | None = None,
        is_active: Callable[[], bool] | None = None,
    ) -> RemoteOperation:
        if confirmation_seconds is not None and (not math.isfinite(confirmation_seconds) or confirmation_seconds <= 0):
            raise InvalidProxyGroupError("确认时限必须为正有限数值")
        if self._closing:
            raise OperationInProgressError("本地服务正在退出")
        if kind == "save_rotation" and (
            payload.get("mode") not in ("same_city", "same_city_carriers", "full_pool")
            or payload.get("interval_minutes") not in ROTATION_INTERVALS
        ):
            raise InvalidProxyGroupError("请选择支持的轮换模式与周期")
        fingerprint = hashlib.sha256(
            json.dumps(
                [proxy_id, kind, payload, expected_revision], sort_keys=True
            ).encode()
        ).hexdigest()
        existing = self.operations.find_key(key)
        if existing:
            return self._same_request(existing, fingerprint)
        proxy, connection, _ = self._context(proxy_id)
        if proxy.revision != expected_revision:
            raise RevisionConflictError("代理已变化，请刷新后重试")
        self.usage.check(proxy, owner)
        now = datetime.now(UTC)
        operation = RemoteOperation(
            str(uuid4()),
            kind,
            proxy_id,
            connection.id,
            connection.secret_ref,
            key,
            fingerprint,
            payload,
            {},
            "queued",
            now,
            now,
        )
        reserved = self.operations.reserve(operation, expected_revision)
        self._same_request(reserved, fingerprint)
        if reserved.id == operation.id:
            if owner is None:
                self.usage.claim(proxy, None, operation.id)
            self._start(operation, send=True, budget=confirmation_seconds, retry_if_ready=retry_if_ready, is_active=is_active)
        return reserved

    @staticmethod
    def _same_request(operation, fingerprint):
        if operation.fingerprint != fingerprint:
            raise RevisionConflictError("此请求标识已用于不同操作，请刷新后重新提交")
        return operation

    def _start(self, operation: RemoteOperation, *, send: bool, budget: float | None = None, retry_if_ready: bool = False, is_active: Callable[[], bool] | None = None):
        task = asyncio.create_task(self._bounded_run(operation, send=send, budget=budget, retry_if_ready=retry_if_ready, is_active=is_active))
        self._tasks[operation.id] = task
        task.add_done_callback(lambda _task: self._tasks.pop(operation.id, None))
        task.add_done_callback(lambda _task: self.usage.unclaim(operation.id))

    def reconcile(self, operation_id: str, *, confirmation_seconds: float | None = None, retry_if_ready: bool = False) -> RemoteOperation:
        operation = self.operations.get(operation_id)
        if (
            operation.status == "unknown"
            and operation.id not in self._tasks
            and not self._closing
        ):
            self._context(operation.target_id, operation.secret_ref)
            self.operations.update(operation.id, "running", before=operation.before)
            self._start(operation, send=False, budget=confirmation_seconds, retry_if_ready=retry_if_ready)
            return self.operations.get(operation.id)
        return operation

    def acknowledge(self, operation_id: str) -> RemoteOperation:
        operation = self.operations.get(operation_id)
        if operation.id in self._tasks:
            raise OperationInProgressError("正在核实，请等待本次核实结束")
        if operation.status != "unknown":
            raise RevisionConflictError("操作状态已变化，请刷新")
        self.operations.update(
            operation_id,
            "failed",
            error={
                "code": "PROXY_OUTCOME_ACKNOWLEDGED",
                "message": "用户已确认结果仍未知；未重新发送操作",
            },
        )
        return self.operations.get(operation_id)

    async def _bounded_run(self, operation, *, send: bool, budget: float | None, retry_if_ready: bool, is_active: Callable[[], bool] | None = None):
        try:
            async with asyncio.timeout(budget if budget is not None else None):
                await self._run(operation, send=send, budget=budget, retry_if_ready=retry_if_ready, is_active=is_active)
        except TimeoutError:
            pass  # _run records whether the command may have been sent.

    async def _run(self, operation: RemoteOperation, *, send: bool, budget: float | None = None, retry_if_ready: bool = False, is_active: Callable[[], bool] | None = None):
        sent = not send
        executing = False
        before = operation.before
        try:
            proxy, _, key = self._context(operation.target_id, operation.secret_ref)
            if send:
                state = await self._provider.get_state(key, proxy.provider_id)
                if state.proxy.provider_id != proxy.provider_id:
                    raise RevisionConflictError("远程代理身份不匹配")
                if operation.kind == "change_ip" and state.rotation_blocked_reason in {"cooldown", "busy"}:
                    self.operations.update(operation.id, "failed", error={
                        "code": "PROXY_COOLDOWN" if state.rotation_blocked_reason == "cooldown" else "PROXY_BUSY",
                        "message": "代理处于冷却期" if state.rotation_blocked_reason == "cooldown" else "代理正在切换",
                        "retry_after_seconds": state.retry_after_seconds,
                    })
                    return
                capability = (
                    "rotation_schedule"
                    if operation.kind in ("save_rotation", "clear_rotation")
                    else operation.kind
                )
                cap = next(
                    item for item in state.capabilities if item.key == capability
                )
                # Reading or clearing an existing plan is allowed even after
                # expiry. Provider rejection remains authoritative.
                if not cap.available and operation.kind != "clear_rotation":
                    raise CapabilityUnavailableError(
                        cap.reason or "此代理当前不支持该操作"
                    )
                before = {
                    "current_ip": state.current_ip,
                    "location_generation": state.location_generation,
                }
                if operation.kind == "change_ip" and not state.current_ip:
                    raise CapabilityUnavailableError(
                        "尚未取得当前出口 IP，请刷新状态后重试"
                    )
                if operation.kind == "relocate":
                    locations = await self._provider.get_locations(key)
                    target = next(
                        (
                            item
                            for item in locations
                            if item.id == operation.payload["location_id"]
                        ),
                        None,
                    )
                    if target is None or target.available_slots <= 0:
                        raise CapabilityUnavailableError(
                            "所选地点已无可用容量，请刷新地点列表"
                        )
                    before["target"] = asdict(target)
                if operation.kind in ("save_rotation", "clear_rotation"):
                    current = await self._provider.get_schedule(key, proxy.provider_id)
                    if self._schedule_matches(operation, current):
                        self.operations.update(
                            operation.id, "succeeded", resource_revision=proxy.revision
                        )
                        return
                self._context(operation.target_id, operation.secret_ref)
                if is_active is not None and not is_active():
                    self.operations.update(operation.id, "failed", error={
                        "code": "PROXY_COMMAND_INTERRUPTED", "message": "运行已停止，未发送切换请求",
                    })
                    return
                before["write_started"] = True
                self.operations.update(operation.id, "running", before=before)
                sent = True
                executing = True
                await self._provider.execute(
                    key, proxy.provider_id, operation.kind, operation.payload
                )
                executing = False
                before["acknowledged"] = True
                self.operations.update(operation.id, "running", before=before)
            async with asyncio.timeout(budget if budget is not None else self._budget):
                await self._confirm(operation, before, budget=budget, retry_if_ready=retry_if_ready)
        except asyncio.CancelledError:
            self.operations.update(
                operation.id,
                "unknown" if sent else "failed",
                error={
                    "code": "PROXYPANEL_OUTCOME_UNKNOWN"
                    if sent
                    else "PROXY_COMMAND_INTERRUPTED",
                    "message": "操作结果尚未确认，请重新核实"
                    if sent
                    else "操作在发送前中断",
                },
            )
            raise
        except ProxyError as exc:
            rejected = isinstance(exc, ProviderError) and exc.code in (
                "PROXYPANEL_AUTH_FAILED",
                "PROXYPANEL_RATE_LIMITED",
                "PROXYPANEL_NOT_FOUND",
                "PROXYPANEL_CONFLICT",
                "PROXYPANEL_VALIDATION_ERROR",
                "PROXYPANEL_REJECTED",
            )
            status: OperationStatus = (
                "failed" if not sent or executing and rejected else "unknown"
            )
            error = provider_error(exc)
            if status == "unknown":
                error = {
                    **error,
                    "code": "PROXYPANEL_OUTCOME_UNKNOWN",
                    "outcome_unknown": True,
                    "message": "请求可能已执行，但结果尚未确认；请重新核实，不会自动重复发送",
                }
            self.operations.update(operation.id, status, error=error)
        except Exception:  # noqa: BLE001 — background boundary must finalize safely without leaking secrets.
            # Never serialize arbitrary provider exceptions, URLs or secrets.
            self.operations.update(
                operation.id,
                "unknown" if sent else "failed",
                error={
                    "code": "PROXY_COMMAND_ERROR",
                    "message": "操作结果尚未确认，请重新核实"
                    if sent
                    else "操作未发送，请刷新后重试",
                },
            )

    async def _confirm(self, operation: RemoteOperation, before: dict, *, budget: float | None = None, retry_if_ready: bool = False):
        deadline = asyncio.get_running_loop().time() + (budget if budget is not None else self._budget)
        attempt = 0
        while True:
            attempt += 1
            proxy, _, key = self._context(operation.target_id, operation.secret_ref)
            try:
                state = None
                if operation.kind in ("save_rotation", "clear_rotation"):
                    matched = self._schedule_matches(
                        operation,
                        await self._provider.get_schedule(key, proxy.provider_id),
                    )
                else:
                    state = await self._provider.get_state(key, proxy.provider_id)
                    if state.proxy.provider_id != proxy.provider_id:
                        raise RevisionConflictError("远程代理身份不匹配")
                    if operation.kind == "change_ip":
                        matched = bool(
                            before.get("current_ip")
                            and state.current_ip
                            and state.current_ip != before["current_ip"]
                        )
                    else:
                        target = before.get("target", {})
                        matched = bool(
                            target
                            and state.location_generation
                            > before.get("location_generation", 0)
                            and state.proxy.city
                            in target.get("cities", [target.get("city")])
                            and state.country == target.get("country")
                            and (
                                not target.get("carrier")
                                or state.proxy.carrier == target["carrier"]
                            )
                        )
            except ProviderError as exc:
                if exc.code not in (
                    "PROXYPANEL_UNAVAILABLE",
                    "PROXYPANEL_RATE_LIMITED",
                ):
                    raise
                delay = max(self._poll, exc.retry_after_seconds or 5)
                remaining = deadline - asyncio.get_running_loop().time()
                if delay >= remaining:
                    raise
                await asyncio.sleep(delay)
                continue
            self._context(operation.target_id, operation.secret_ref)
            if matched:
                revision = self._apply_observation(operation, proxy.revision, state)
                self.operations.update(
                    operation.id, "succeeded", resource_revision=revision
                )
                return
            if retry_if_ready and before.get("acknowledged") and state is not None:
                ready = (
                    operation.kind == "change_ip" and state.rotation_available is True
                    and state.rotation_blocked_reason is None
                ) or (
                    operation.kind == "relocate"
                    and state.location_generation > before.get("location_generation", 0)
                )
                if ready:
                    self.operations.update(operation.id, "failed", error={
                        "code": "PROXY_IP_UNCHANGED" if operation.kind == "change_ip" else "PROXY_LOCATION_MISMATCH",
                        "message": "供应商已允许继续操作，但未达到切换目标", "outcome_unknown": False,
                    })
                    return
            if asyncio.get_running_loop().time() >= deadline:
                self.operations.update(
                    operation.id,
                    "unknown",
                    error={
                        "code": "PROXYPANEL_OUTCOME_UNKNOWN",
                        "message": "观察时间已结束，结果尚未确认；可重新核实，不会重复发送",
                        "outcome_unknown": True,
                    },
                )
                return
            await asyncio.sleep(
                min(
                    self._poll if attempt < 5 else max(self._poll, 5),
                    max(0, deadline - asyncio.get_running_loop().time()),
                )
            )

    @staticmethod
    def _schedule_matches(operation, schedule):
        if operation.kind == "clear_rotation":
            return not schedule.enabled
        return (
            schedule.enabled
            and schedule.mode == operation.payload.get("mode")
            and schedule.interval_minutes == operation.payload.get("interval_minutes")
        )

    def _apply_observation(
        self, operation, observed_revision: int, state: RemoteState | None
    ):
        with self._uow() as uow:
            proxy = ProjectionService(uow.repository).get(operation.target_id)
            connection = ConnectionService(uow.repository, self._credentials).get(
                proxy.connection_id
            )
            if connection.secret_ref != operation.secret_ref:
                raise RevisionConflictError("连接已替换")
            if state is None:
                return proxy.revision
            if proxy.revision != observed_revision:
                # A concurrent sync/edit wins; never overwrite its newer fields.
                raise RevisionConflictError("代理信息更新中，请重新核实结果")
            item = state.proxy
            updated = replace(
                proxy,
                name=item.name,
                remote_status=item.remote_status,
                city=item.city,
                region=item.region,
                carrier=item.carrier,
                exit_ip=state.current_ip or item.exit_ip,
                http_endpoint=item.http_endpoint,
                socks5_endpoint=item.socks5_endpoint,
                credential_available=item.credential_available,
                subscription_expires_at=item.subscription_expires_at,
                health=Health(),
                revision=proxy.revision + 1,
                updated_at=datetime.now(UTC),
            )
            uow.repository.save_projection(updated, proxy.revision)
            uow.commit()
            return updated.revision

    async def close(self):
        self._closing = True
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
