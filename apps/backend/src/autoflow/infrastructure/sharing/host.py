from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from autoflow.domain.workflows.execution import DesktopActionResult

from . import file_share, screen_share


class NetworkShareHost:
    ACTIONS = frozenset(
        {
            "start_file_share",
            "stop_file_share",
            "start_screen_share",
            "stop_screen_share",
        }
    )

    def supports(self, action: object) -> bool:
        return isinstance(action, str) and action in self.ACTIONS

    async def perform(
        self, action: str, payload: Mapping[str, Any]
    ) -> DesktopActionResult:
        try:
            if action == "start_file_share":
                result = await asyncio.to_thread(
                    file_share.start_file_share,
                    str(payload.get("path") or ""),
                    int(payload.get("port", 8080)),
                    str(payload.get("shareType") or "folder"),
                    str(payload.get("name") or "共享"),
                    bool(payload.get("allowWrite", True)),
                )
            elif action == "stop_file_share":
                result = await asyncio.to_thread(
                    file_share.stop_file_share, int(payload.get("port", 8080))
                )
            elif action == "start_screen_share":
                result = await asyncio.to_thread(
                    screen_share.start_screen_share,
                    int(payload.get("port", 9000)),
                    int(payload.get("fps", 30)),
                    int(payload.get("quality", 70)),
                    float(payload.get("scale", 1.0)),
                )
            elif action == "stop_screen_share":
                result = await asyncio.to_thread(
                    screen_share.stop_screen_share, int(payload.get("port", 9000))
                )
            else:
                return DesktopActionResult(False, error="不支持的共享服务操作")
        except (TypeError, ValueError) as error:
            return DesktopActionResult(False, error=f"共享服务参数无效: {error}")
        if not result.get("success"):
            return DesktopActionResult(
                False, error=str(result.get("error") or "共享服务操作失败")
            )
        return DesktopActionResult(True, value=result)

    def busy(self) -> bool:
        return bool(file_share.get_active_shares() or screen_share.get_all_screen_shares())

    async def shutdown(self) -> None:
        await asyncio.gather(
            asyncio.to_thread(file_share.stop_all_file_shares),
            asyncio.to_thread(screen_share.stop_all_screen_shares),
        )
