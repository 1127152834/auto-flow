from collections.abc import Iterable

from .management_models import ActionPolicy, DeviceFacts

_OPERATION_LABELS = {
    "create": "正在创建",
    "start": "正在启动",
    "stop": "正在停止",
    "restart": "正在重启",
    "delete": "正在删除",
    "recover": "正在核实",
}
_RUNTIME_LABELS = {
    "stopped": "已停止",
    "starting": "启动中",
    "ready": "已就绪",
    "retained": "数据已保留",
    "missing": "资源缺失",
    "unknown": "待核实",
}


def display_state(facts: DeviceFacts) -> str:
    if facts.operation_state in {"queued", "running", "waiting_capacity"} and facts.operation_action:
        return _OPERATION_LABELS.get(facts.operation_action, "操作中")
    if facts.last_error or facts.control == "recovery_required" or facts.owner_kind in {"unknown", "legacyWorkflow"}:
        return "待核实"
    if facts.owner_kind == "manualSession" or facts.control in {"manual", "opening_manual", "closing_manual"}:
        return "手动控制中"
    if facts.stale:
        return "待核实"
    return _RUNTIME_LABELS[facts.runtime_state]


def _blocked(actions: Iterable[str], reason: str) -> dict[str, str]:
    return {action: reason for action in actions}


def policy_for(facts: DeviceFacts) -> ActionPolicy:
    all_mutations = ("start", "stop", "restart", "delete", "restore", "open")
    if facts.operation_state in {"queued", "running", "waiting_capacity"}:
        return ActionPolicy(
            ("view_operation", "verify"),
            _blocked(all_mutations, "设备已有未结束的管理操作"),
        )
    if facts.owner_kind in {"unknown", "legacyWorkflow"} or facts.control == "recovery_required" or facts.stale or facts.runtime_state == "unknown":
        return ActionPolicy(("verify",), _blocked(all_mutations, "设备状态或归属尚未核实"))
    if facts.owner_kind == "manualSession" or facts.control in {"manual", "opening_manual", "closing_manual"}:
        return ActionPolicy(("return_to_console", "end_control"), _blocked(("start", "stop", "restart", "delete", "restore"), "请先结束当前控制会话"))
    if facts.runtime_state == "retained" or facts.retained:
        return ActionPolicy(("restore", "delete"), _blocked(("start", "open", "stop", "restart"), "保留数据实例必须先恢复"))
    if facts.runtime_state == "stopped":
        return ActionPolicy(("start", "delete"), {"open": "设备尚未启动", "restore": "设备没有待恢复数据"})
    if facts.runtime_state == "ready":
        return ActionPolicy(("open", "stop", "restart", "delete"), {"restore": "设备没有待恢复数据"})
    return ActionPolicy(("verify",), _blocked(all_mutations, "设备状态不支持管理操作"))
