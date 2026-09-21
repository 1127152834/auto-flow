from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

CheckStatus = Literal["pass", "fail", "unknown", "unsupported"]
CHECK_NAMES = ("platform", "adb", "lima", "ssh", "scrcpy", "vm", "docker", "binder", "images", "capacity", "disk")


@dataclass(frozen=True)
class EnvironmentCheck:
    status: CheckStatus
    code: str | None
    message: str
    action: str | None = None


@dataclass(frozen=True)
class EnvironmentCheckResult:
    checked_at: datetime
    runtime_id: str
    checks: dict[str, EnvironmentCheck]
    capabilities: dict[str, bool | str]
    legacy: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "checkedAt": self.checked_at.isoformat(),
            "runtimeId": self.runtime_id,
            "checks": {
                name: {
                    "status": check.status,
                    "code": check.code,
                    "message": check.message,
                    "action": check.action,
                }
                for name, check in self.checks.items()
            },
            "capabilities": self.capabilities,
            "legacy": self.legacy,
        }


class EnvironmentCheckService:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    async def check(self, _request_id: str) -> EnvironmentCheckResult:
        environment = await self.runtime.environment()
        supported = environment.get("platformSupported")
        available = environment.get("available")
        checks = {name: self._check(name, environment, supported, available) for name in CHECK_NAMES}
        return EnvironmentCheckResult(
            checked_at=datetime.now(UTC),
            runtime_id=str(environment.get("runtimeId") or "unknown"),
            checks=checks,
            capabilities={
                "management": available is True,
                "control": available is True,
                "images": bool(environment.get("images")) if "images" in environment else "unknown",
                "workflow": False,
            },
            legacy=environment,
        )

    @staticmethod
    def _check(name: str, environment: dict[str, Any], supported: Any, available: Any) -> EnvironmentCheck:
        if name == "platform":
            if supported is False:
                return EnvironmentCheck("unsupported", "ANDROID_PLATFORM_UNSUPPORTED", "当前平台不支持安卓运行时")
            if supported is True:
                return EnvironmentCheck("pass", None, "平台支持")
            return EnvironmentCheck("unknown", "ANDROID_PLATFORM_UNKNOWN", "平台支持情况未核实")
        checks = environment.get("checks")
        if isinstance(checks, dict) and name in checks:
            value = checks[name]
            if isinstance(value, dict):
                status = value.get("status", "unknown")
                if status in {"pass", "fail", "unknown", "unsupported"}:
                    return EnvironmentCheck(status, value.get("code"), value.get("message", ""), value.get("action"))
            if isinstance(value, bool):
                return EnvironmentCheck("pass" if value else "fail", None, "检查通过" if value else "检查失败")
        if name == "images" and "images" in environment:
            return EnvironmentCheck("pass" if environment["images"] else "fail", None if environment["images"] else "ANDROID_IMAGE_MISSING", "已发现兼容镜像" if environment["images"] else "未发现兼容镜像")
        if available is False:
            return EnvironmentCheck("unknown", "ANDROID_CHECK_UNAVAILABLE", "运行环境不可访问")
        return EnvironmentCheck("unknown", "ANDROID_CHECK_NOT_COLLECTED", "尚未采集")
