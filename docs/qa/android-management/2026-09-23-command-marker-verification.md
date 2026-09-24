# 安卓应用操作完成标记：持久回执与客体清理

- 日期：2026-09-23；来源：`codex/android-management-complete` 隔离 worktree 的生产 Mac/Lima/ReDroid 运行时及自建实例 `ae1ea169-9b7c-4751-96a0-c896fffd5c13`。
- 状态：`confirmed`（成功应用操作的新标记清理）；T19 整体仍为 `partial`。

上一轮真实 APK 安装、启动、停止、清数据和卸载均成功，但客体 `/data/local/tmp` 留下 5 个 `autoflow-operation-*` 标记。根因是运行时收到成功 ADB 响应后立刻清除了设备记录中的 `pendingCommand`，而会话的成功回执尚未持久化，导致既无法安全地确认删除客体标记，也可能在回执保存失败时失去完成证据。

新增的 RED 测试覆盖运行时成功响应后的保留、会话成功回执落盘后的确认，以及回执落盘失败时禁止提前确认。执行 `uv run pytest -q tests/unit/test_android_runtime.py::test_successful_app_response_keeps_marker_until_receipt_acknowledgement tests/unit/test_android_console_lifecycle.py::test_successful_app_command_acknowledges_marker_after_terminal_receipt` 得 `4 failed`。GREEN 后执行 `uv run pytest -q tests/contract/test_android_apps.py tests/unit/test_android_console_lifecycle.py tests/unit/test_android_runtime.py` 得 `69 passed, 1 warning`。完整后端回归 `3976 passed, 26 skipped, 2 warnings in 885.29s`；Ruff、compileall、OpenAPI check、Alembic 单 head 和 `git diff --check` 均通过。

修复后，手动应用命令要求运行时将标记保留到会话写入终态回执，随后按同一个标记确认并删除。安装路径也不再在成功响应时提前丢弃标记；如果终态回执保存失败，同一会话可通过原请求核实，设备也不会因标记丢失而假装可用。退役工作流的 `command` 调用保留原默认语义，本次不复活工作流执行入口。

在同一自建实例上用生产 HTTP sidecar 重跑本地 APK：安装并核对 versionCode `1086`，启动、停止、清数据、卸载，最终包不存在，脚本退出 0 且 JSON `status=passed`。客体 `autoflow-operation-*` 数量从修复前的 `5` 保持为 `5`，没有新增；`autoflow-apk-*` 为 `0`。只读复核发现数据库内有 5 个新成功回执的 `commandMarker` 引用，与 5 个客体旧文件的交集为 `0`。旧标记尚未通过产品清理预览处理，不能写成已清零。上传中断的 APK 临时文件、恢复中断和高级日志仍属 T19 未完成范围。

本切片完整后端命令为 `cd apps/backend && uv run pytest -q`，exit 0；两条 warning 分别为 Starlette/AnyIO 废弃别名和故意重复 Manifest 的 ZIP 夹具。真实脚本及原始 APK 均留在本机 `/tmp` 和用户本地下载目录，未加入仓库。前端代码未随本切片改动；前一 AM1 切片的完整前端回归在 Node `v22.23.2` 下为 `424` 文件、`5621` 项通过。
