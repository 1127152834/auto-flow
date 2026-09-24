"""Network sharing nodes migrated from WebRPA@5ccb900e.

Sources: backend/app/executors/advanced.py and screen_share.py.
License: LICENSE.WebRPA.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from autoflow.domain.workflows.execution import ExecutionContext

from .base import ModuleExecutor, ModuleResult
from .type_utils import to_bool, to_float, to_int


async def _perform(
    context: ExecutionContext, action: str, payload: dict[str, Any]
) -> Mapping[str, Any] | ModuleResult:
    if context.desktop_actions is None:
        return ModuleResult(success=False, error="共享服务不可用")
    result = await context.desktop_actions.perform(action, payload, timeout_seconds=15)
    if not result.success:
        return ModuleResult(success=False, error=result.error or "共享服务操作失败")
    if not isinstance(result.value, Mapping):
        return ModuleResult(success=False, error="共享服务返回结果无效")
    return result.value


class ShareFolderExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "share_folder"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        folder_path = str(context.resolve_value(config.get("folderPath", "")))
        if not folder_path:
            return ModuleResult(success=False, error="文件夹路径不能为空")
        folder = Path(folder_path)
        if not folder.exists():
            return ModuleResult(success=False, error=f"文件夹不存在: {folder_path}")
        if not folder.is_dir():
            return ModuleResult(success=False, error=f"路径不是文件夹: {folder_path}")
        port = to_int(config.get("port", 8080), 8080, context)
        share_name = str(context.resolve_value(config.get("shareName", "")) or "共享文件夹")
        allow_write = to_bool(config.get("allowWrite", True), True, context)
        result = await _perform(
            context,
            "start_file_share",
            {
                "path": str(folder.resolve()),
                "port": port,
                "shareType": "folder",
                "name": share_name,
                "allowWrite": allow_write,
            },
        )
        if isinstance(result, ModuleResult):
            return result
        url = str(result["url"])
        variable_name = str(config.get("resultVariable", "share_url"))
        if variable_name:
            context.set_variable(variable_name, url)
        write_mode = "可上传/删除" if allow_write else "仅下载"
        return ModuleResult(
            success=True,
            message=(
                "📂 文件夹共享已启动！\n"
                f"共享名称: {share_name}\n共享路径: {folder_path}\n"
                f"访问地址: {url}\n权限模式: {write_mode}\n"
                "💡 同局域网的设备可以使用浏览器访问上述地址来浏览和下载文件"
            ),
            data={
                "url": url,
                "ip": result["ip"],
                "port": port,
                "path": str(folder.resolve()),
                "name": share_name,
                "allowWrite": allow_write,
            },
        )


class ShareFileExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "share_file"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        file_path = str(context.resolve_value(config.get("filePath", "")))
        if not file_path:
            return ModuleResult(success=False, error="文件路径不能为空")
        file = Path(file_path)
        if not file.exists():
            return ModuleResult(success=False, error=f"文件不存在: {file_path}")
        if not file.is_file():
            return ModuleResult(success=False, error=f"路径不是文件: {file_path}")
        port = to_int(config.get("port", 8080), 8080, context)
        result = await _perform(
            context,
            "start_file_share",
            {
                "path": str(file.resolve()),
                "port": port,
                "shareType": "file",
                "name": file.name,
                "allowWrite": False,
            },
        )
        if isinstance(result, ModuleResult):
            return result
        url = str(result["url"])
        variable_name = str(config.get("resultVariable", "share_url"))
        if variable_name:
            context.set_variable(variable_name, url)
        size = file.stat().st_size
        return ModuleResult(
            success=True,
            message=(
                "📄 文件共享已启动！\n"
                f"文件名: {file.name}\n文件大小: {_format_size(size)}\n"
                f"访问地址: {url}\n"
                "💡 同局域网的设备可以使用浏览器访问上述地址来下载此文件"
            ),
            data={
                "url": url,
                "ip": result["ip"],
                "port": port,
                "path": str(file.resolve()),
                "name": file.name,
                "size": size,
            },
        )


class StopShareExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "stop_share"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        port = to_int(config.get("port", 8080), 8080, context)
        result = await _perform(context, "stop_file_share", {"port": port})
        if isinstance(result, ModuleResult):
            return result
        return ModuleResult(
            success=True,
            message=f"端口 {port} 的共享服务已停止",
            data={"port": port},
        )


class StartScreenShareExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "start_screen_share"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        port = to_int(config.get("port", 9000), 9000, context)
        fps = min(max(to_int(config.get("fps", 30), 30, context), 1), 60)
        quality = min(max(to_int(config.get("quality", 70), 70, context), 10), 100)
        scale = min(max(to_float(config.get("scale", 1.0), 1.0, context), 0.1), 1.0)
        result = await _perform(
            context,
            "start_screen_share",
            {"port": port, "fps": fps, "quality": quality, "scale": scale},
        )
        if isinstance(result, ModuleResult):
            return result
        url = str(result["url"])
        variable_name = str(config.get("resultVariable", "screen_share_url"))
        if variable_name:
            context.set_variable(variable_name, url)
        bandwidth = _estimate_bandwidth(fps, quality, scale)
        return ModuleResult(
            success=True,
            message=(
                "🖥️ 屏幕共享已启动！\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📡 访问地址: {url}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚙️ 参数设置:\n   帧率: {fps} FPS\n   画质: {quality}%\n"
                f"   缩放: {int(scale * 100)}%\n   预估带宽: {bandwidth}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 同局域网的设备可以使用浏览器访问上述地址\n"
                "   实时观看此电脑的屏幕画面"
            ),
            data={
                "url": url,
                "ip": result["ip"],
                "port": port,
                "fps": fps,
                "quality": quality,
                "scale": scale,
            },
        )


class StopScreenShareExecutor(ModuleExecutor):
    @property
    def module_type(self) -> str:
        return "stop_screen_share"

    async def execute(
        self, config: dict[str, Any], context: ExecutionContext
    ) -> ModuleResult:
        port = to_int(config.get("port", 9000), 9000, context)
        result = await _perform(context, "stop_screen_share", {"port": port})
        if isinstance(result, ModuleResult):
            return result
        return ModuleResult(
            success=True,
            message=f"🖥️ 屏幕共享已停止 (端口 {port})",
            data={"port": port},
        )


def _format_size(size: int) -> str:
    amount = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024:
            return f"{int(amount)} B" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} PB"


def _estimate_bandwidth(fps: int, quality: int, scale: float) -> str:
    mbps = (200 * 1024 * (quality / 100) * (scale**2) * fps * 8) / (1024 * 1024)
    return f"{int(mbps * 1000)} Kbps" if mbps < 1 else f"{mbps:.1f} Mbps"


NETWORK_SHARING_EXECUTORS: tuple[type[ModuleExecutor], ...] = (
    ShareFolderExecutor,
    ShareFileExecutor,
    StopShareExecutor,
    StartScreenShareExecutor,
    StopScreenShareExecutor,
)
